"""Agent 平台 API client(防禦式)。

這個平台不是標準 OpenAI 相容服務,照 SDK 慣例用會大量踩雷。
本模組把已知的每一個坑寫成程式碼:

  * 只組出唯一有效的檔案引用形狀,絕不產生 {"type":"file_id"}(會 504 卡死)
  * 不送任何靜默忽略的參數(temperature/seed/stop/n/response_format/tools/stream)
  * HTTP 200 不代表成功 —— 必須檢查 choices[0].message.content 非空
  * HTTP 500 + "No static resource" 代表路由不存在,不是服務掛掉
  * HTTP 429 可能是參數非法造成的假限流
  * 上傳後需等待索引,太快引用會拿到空回應
  * 5xx(如 database_timeout 的 504)是暫時性問題,平台自己都叫你重試 ——
    這類錯誤會進 TransientServerError,交給 _retryable() 重試,不是直接失敗
"""
from __future__ import annotations

import logging
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

# 路由不存在的指紋。看到這個字串就是 404 的意思,不要當成伺服器故障。
ROUTE_MISSING_FINGERPRINT = "No static resource"

# 平台每次呼叫的固定 prompt 開銷(工具 schema + system prompt),約略值,僅供成本估算顯示。
FIXED_PROMPT_TOKEN_OVERHEAD = 3863

# 送出前的硬性上下限。負值會讓平台回一個誤導性的 429。
MAX_TOKENS_FLOOR = 1
MAX_TOKENS_CEIL = 4096

# 絕對不可出現在 request body 的 key —— 全部靜默忽略,留著只會誤導維護者。
FORBIDDEN_PARAMS = frozenset({
    "temperature", "top_p", "top_k", "stop", "n", "seed", "presence_penalty",
    "frequency_penalty", "logit_bias", "logprobs", "response_format",
    "tools", "tool_choice", "functions", "function_call", "stream",
})


class AgentPlatformError(Exception):
    """平台呼叫失敗的基底例外。"""


class AuthError(AgentPlatformError):
    """API key 無效(這個平台的認證是真的會生效的)。"""


class TlsError(AgentPlatformError):
    """憑證無法驗證。

    這是決定性的失敗 —— 重試不會讓憑證變成受信任,所以不進重試流程。
    """


class RouteNotImplemented(AgentPlatformError):
    """路由不存在。平台在 /v1 底下是 catch-all,任何不存在的路徑都回 500。"""


class TransientServerError(AgentPlatformError):
    """5xx 且看起來是暫時性的伺服器問題(逾時、資料庫忙線等)—— 值得重試。

    平台偶爾會回類似 {"error":{"code":"database_timeout",
    "message":"Database query timeout. Please retry later."}} 的 504,
    訊息本身就講了「等一下再試」;原本 5xx 一律當成決定性失敗直接拋出,
    完全沒有機會重試,白白浪費了平台自己承認的可恢復狀況。
    """


class EmptyCompletion(AgentPlatformError):
    """HTTP 200 但沒有實際內容 —— 這個平台的 200 不等於成功。"""


class UploadFailed(AgentPlatformError):
    """檔案上傳或索引失敗。"""


class RetryExhausted(AgentPlatformError):
    """暫時性錯誤已用完單次呼叫的重試次數，交由工作層稍後重跑。"""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_payload(cls, payload: Any) -> "Usage":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            prompt_tokens=int(payload.get("prompt_tokens") or 0),
            completion_tokens=int(payload.get("completion_tokens") or 0),
            total_tokens=int(payload.get("total_tokens") or 0),
        )


@dataclass
class ChatResult:
    content: str
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = ""
    elapsed_seconds: float = 0.0
    attempts: int = 1
    file_ids: list[str] = field(default_factory=list)

    @property
    def maybe_truncated(self) -> bool:
        """輸出上限觀察值約 1825 tokens;逼近時視為可能被截斷。"""
        return self.usage.completion_tokens >= 1800


@dataclass
class UploadedFile:
    file_id: str
    filename: str
    bytes: int = 0


def build_user_content(text: str, file_ids: list[str] | None) -> list[dict[str, Any]]:
    """組出平台唯一接受的 content 陣列。

    只有 {"type":"file","file":{"file_id":...}} 有效。
    attachments / body 層 file_ids / 文字提檔名 全部無效,
    而 {"type":"file_id"} 會讓後端卡死回 504 —— 這裡結構上不可能產生它。
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for fid in file_ids or []:
        if not fid:
            continue
        content.append({"type": "file", "file": {"file_id": str(fid)}})
    return content


class AgentClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        *,
        timeout: int = 120,
        max_retries: int = 2,
        retry_backoff: float = 2.0,
        upload_settle_seconds: float = 3.0,
        verify: bool | str = True,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ) -> None:
        if not base_url:
            raise ValueError("BASE_URL 未設定")
        # BASE_URL 不含 /v1,這裡自行組合
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_id = model_id
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_backoff = retry_backoff
        self.upload_settle_seconds = upload_settle_seconds
        # verify 逐次明確傳給 requests,不設在 session 上 ——
        # requests 的 merge_environment_settings() 會讓 REQUESTS_CA_BUNDLE /
        # CURL_CA_BUNDLE 環境變數蓋掉 session 層的設定,逐次傳入才可預測。
        self.verify = verify
        self._sleep = sleep
        self._session = session or requests.Session()

        if verify is False:
            # 不抑制的話,每一次呼叫都會噴一行 InsecureRequestWarning,
            # 長時間執行的服務 log 會被洗版。改成這裡記一次就好。
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:  # pragma: no cover - urllib3 版本差異
                pass
            log.warning(
                "TLS 憑證驗證已關閉(VERIFY_SSL=false)—— 連線仍然加密,"
                "但無法確認對方身分。僅適用於受控內網。"
            )

    # --- 內部工具 -------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/v1/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    @staticmethod
    def _body_text(resp: requests.Response) -> str:
        try:
            return resp.text or ""
        except Exception:  # pragma: no cover - 極少見的解碼失敗
            return ""

    def _check_transport(self, resp: requests.Response) -> None:
        """把不可信的 HTTP 狀態碼翻譯成明確的例外。"""
        body = self._body_text(resp)

        # 路由不存在:平台回 500,不是 404。優先判斷,因為它會偽裝成伺服器錯誤。
        if ROUTE_MISSING_FINGERPRINT in body:
            raise RouteNotImplemented(
                f"平台未實作此路由({resp.request.method} {resp.request.url})。"
                f"這是路由不存在,不是服務故障。"
            )

        if resp.status_code == 401:
            raise AuthError("API key 無效(invalid_api_key)")

        if resp.status_code == 429:
            # 這個平台的錯誤映射錯亂:非法參數(如 max_tokens 為負)也會回 429。
            raise AgentPlatformError(
                "收到 429。注意此平台會把非法參數誤報為 rate_limit_exceeded,"
                f"請先確認請求參數。body={body[:400]}"
            )

        # 5xx(路由不存在的偽裝已經在上面攔掉)當成暫時性問題重試 ——
        # 資料庫逾時、閘道逾時這類狀況,平台自己都在錯誤訊息裡叫你重試。
        if resp.status_code >= 500:
            raise TransientServerError(
                f"HTTP {resp.status_code}: {body[:400]}"
            )

        if resp.status_code >= 400:
            raise AgentPlatformError(
                f"HTTP {resp.status_code}: {body[:400]}"
            )

    def _tls_error(self, exc: Exception) -> TlsError:
        """把 requests 的 SSLError 翻成使用者知道怎麼修的訊息。

        原始訊息是一長串 urllib3 堆疊,看不出要改哪個設定。
        """
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        where = parsed.netloc or self.base_url

        detail = str(exc)
        if "self-signed" in detail or "self signed" in detail:
            cause = "使用自簽憑證"
        elif "unable to get local issuer" in detail:
            cause = "的憑證簽發者不在信任清單中"
        elif "certificate has expired" in detail:
            cause = "的憑證已過期"
        elif "doesn't match" in detail or "hostname mismatch" in detail.lower():
            cause = "的憑證主體名稱與網址不符"
        else:
            cause = "的憑證無法驗證"

        return TlsError(
            f"無法建立安全連線:{where} {cause}。\n"
            f"請在 .env 二選一:\n"
            f"  CA_BUNDLE=<內部 CA 憑證檔路徑>   建議 —— 驗證仍然生效\n"
            f"  VERIFY_SSL=false                關閉驗證,僅適用於受控內網\n"
            f"原始錯誤:{detail[:200]}"
        )

    def _retryable(self, fn, *, what: str):
        """對網路錯誤 / timeout / 空回應重試;認證與路由錯誤不重試。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                return fn(), attempt
            except (AuthError, RouteNotImplemented, TlsError, ValueError):
                raise
            except requests.exceptions.SSLError as exc:
                # 憑證不受信任是決定性失敗,重試不會讓它變成受信任 ——
                # 重試只是白等 3 倍時間,還會把真正的原因埋在堆疊裡。
                raise self._tls_error(exc) from exc
            except (requests.RequestException, EmptyCompletion, UploadFailed,
                   TransientServerError) as exc:
                last_exc = exc
                if attempt > self.max_retries:
                    break
                wait = self.retry_backoff
                log.warning("%s 第 %d 次失敗(%s),%.1fs 後重試", what, attempt, exc, wait)
                self._sleep(wait)
        raise RetryExhausted(
            f"{what} 重試 {self.max_retries} 次後仍失敗: {last_exc}"
        ) from last_exc

    # --- 檔案 -----------------------------------------------------------

    def upload_file(self, path: str | Path, purpose: str = "assistants") -> UploadedFile:
        """上傳單一檔案,並等待索引完成後才回傳。"""
        uploaded = self._post_file(path, purpose)
        if self.upload_settle_seconds > 0:
            self._sleep(self.upload_settle_seconds)
        self._wait_indexed(uploaded.file_id)
        log.info("已上傳 %s -> %s (%d bytes)", uploaded.filename, uploaded.file_id,
                 uploaded.bytes)
        return uploaded

    def upload_files(self, paths: list[str | Path],
                     purpose: str = "assistants") -> list[UploadedFile]:
        """批次上傳,全部送出後只等一次索引延遲。

        逐一呼叫 upload_file 的話,20 張圖片要等 20 次(共 60 秒)。
        索引延遲是「上傳後到可引用之間」的等待,先全部送出再統一等一次,
        最後一個檔案仍然等滿,先送出的等更久 —— 語意上完全滿足,時間卻省下大半。
        """
        if not paths:
            return []
        uploaded = [self._post_file(p, purpose) for p in paths]
        if self.upload_settle_seconds > 0:
            self._sleep(self.upload_settle_seconds)
        for item in uploaded:
            self._wait_indexed(item.file_id)
        log.info("已批次上傳 %d 個檔案(共 %d bytes)",
                 len(uploaded), sum(u.bytes for u in uploaded))
        return uploaded

    def _post_file(self, path: str | Path, purpose: str) -> UploadedFile:
        """送出檔案本身,不處理索引等待。"""
        p = Path(path)
        if not p.is_file():
            raise UploadFailed(f"找不到檔案: {p}")

        def _do() -> UploadedFile:
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            with p.open("rb") as fh:
                resp = self._session.post(
                    self._url("files"),
                    headers=self._headers(),
                    data={"purpose": purpose},
                    files={"file": (p.name, fh, mime)},
                    timeout=self.timeout,
                    verify=self.verify,
                )
            self._check_transport(resp)
            try:
                payload = resp.json()
            except ValueError as exc:
                raise UploadFailed(f"上傳回應不是 JSON: {self._body_text(resp)[:200]}") from exc
            file_id = payload.get("id")
            if not file_id:
                raise UploadFailed(f"上傳回應缺少 id: {payload}")
            return UploadedFile(
                file_id=str(file_id),
                filename=str(payload.get("filename") or p.name),
                bytes=int(payload.get("bytes") or p.stat().st_size),
            )

        uploaded, _ = self._retryable(_do, what=f"上傳 {p.name}")
        return uploaded

    def _wait_indexed(self, file_id: str) -> None:
        """用 GET /v1/files/{id} 確認檔案已可引用。查不到不視為致命。"""
        def _do() -> bool:
            resp = self._session.get(
                self._url(f"files/{file_id}"),
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify,
            )
            self._check_transport(resp)
            try:
                payload = resp.json()
            except ValueError:
                raise UploadFailed("檔案 metadata 回應不是 JSON")
            if not payload.get("id"):
                raise UploadFailed("檔案尚未完成索引")
            return True

        try:
            self._retryable(_do, what=f"確認檔案 {file_id} 索引")
        except AgentPlatformError as exc:
            # 索引查詢本身可能不穩;真正的失敗會在 chat 階段顯現。
            log.warning("檔案 %s 索引確認未通過(仍繼續): %s", file_id, exc)

    def delete_file(self, file_id: str) -> bool:
        try:
            resp = self._session.delete(
                self._url(f"files/{file_id}"),
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify,
            )
            self._check_transport(resp)
            return True
        except AgentPlatformError as exc:
            log.warning("刪除遠端檔案 %s 失敗: %s", file_id, exc)
            return False

    def list_files(self) -> list[dict[str, Any]]:
        resp = self._session.get(self._url("files"), headers=self._headers(),
                                 timeout=self.timeout, verify=self.verify)
        self._check_transport(resp)
        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        return data if isinstance(data, list) else []

    # --- 生成 -----------------------------------------------------------

    def chat(
        self,
        text: str,
        file_ids: list[str] | None = None,
        *,
        max_tokens: int = 2048,
    ) -> ChatResult:
        """單則 user 訊息 + 選用檔案引用。

        平台不吃 messages 歷史也沒有跨呼叫記憶,所以刻意不提供多輪介面:
        所有上下文都必須由呼叫端壓進 `text`。
        """
        if not self.model_id:
            raise ValueError("MODEL_ID 未設定")
        if not text or not text.strip():
            raise ValueError("text 不可為空")

        # 負值會讓平台回一個誤導性的 429,所以在送出前就擋掉。
        # 這是設定錯誤,靜默夾成 1 只會產出無用的 1-token 回應,寧可明確失敗。
        max_tokens = int(max_tokens)
        if max_tokens < MAX_TOKENS_FLOOR:
            raise ValueError(
                f"max_tokens 必須 >= {MAX_TOKENS_FLOOR},收到 {max_tokens}。"
                f"(平台會把非法值誤報為 429,故在此攔下)"
            )
        max_tokens = min(max_tokens, MAX_TOKENS_CEIL)

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": build_user_content(text, file_ids)}],
            "max_tokens": max_tokens,
        }
        # 結構性保證:不送任何會被靜默忽略的參數
        assert not (FORBIDDEN_PARAMS & payload.keys()), "request body 混入了無效參數"

        started = time.monotonic()

        def _do() -> ChatResult:
            resp = self._session.post(
                self._url("chat/completions"),
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
                verify=self.verify,
            )
            self._check_transport(resp)
            try:
                data = resp.json()
            except ValueError as exc:
                raise EmptyCompletion(
                    f"回應不是 JSON: {self._body_text(resp)[:200]}"
                ) from exc

            content, finish = _read_completion(data)
            # HTTP 200 不等於成功
            if not content.strip():
                raise EmptyCompletion("平台回 200 但內容為空")
            return ChatResult(
                content=content,
                usage=Usage.from_payload(data.get("usage")),
                finish_reason=finish,
            )

        result, attempts = self._retryable(_do, what="chat/completions")
        result.elapsed_seconds = round(time.monotonic() - started, 2)
        result.attempts = attempts
        result.file_ids = list(file_ids or [])
        return result

    # --- 健康檢查 -------------------------------------------------------

    def healthcheck(self) -> dict[str, Any]:
        """送一則最小訊息,驗證連線 / 認證 / 回應非空。

        不能只看 HTTP 狀態碼,所以這裡實際做一次生成。
        """
        started = time.monotonic()
        try:
            result = self.chat("請回覆「OK」兩個字。", max_tokens=16)
            return {
                "ok": True,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "reply": result.content[:200],
                "prompt_tokens": result.usage.prompt_tokens,
            }
        except AgentPlatformError as exc:
            return {
                "ok": False,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "error": str(exc),
                "error_type": type(exc).__name__,
            }


def _read_completion(data: Any) -> tuple[str, str]:
    """從回應取出文字。平台同時提供非標準的 choices[].text,兩者都接受。"""
    if not isinstance(data, dict):
        return "", ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    first = choices[0]
    if not isinstance(first, dict):
        return "", ""
    message = first.get("message")
    content = ""
    if isinstance(message, dict):
        content = message.get("content") or ""
    if not content:
        content = first.get("text") or ""
    return (content if isinstance(content, str) else ""), str(first.get("finish_reason") or "")
