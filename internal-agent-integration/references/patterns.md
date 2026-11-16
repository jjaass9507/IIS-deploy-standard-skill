# 串接模式與程式碼骨架

以下程式碼假設已把 `scripts/agent_client.py`、`scripts/jsonx.py` 放進專案的 `core/`。

---

## §1 Prompt：單則、自足、錨點、契約

### 範本

```python
def build_prompt(*, role: str, task: str, context: dict, node_list: str = "") -> str:
    parts = [
        role,                                   # 可改段落：你是誰、著重什麼
        "【附件】",
        "1. `doc_text.md` —— 原始文件的完整文字，每一頁、每個表格都有固定錨點"
        "（[S03] 第 3 頁、[T03-1] 第 3 頁第 1 個表格）。",
        "2. 圖片若干張 —— 每張上方的黑色橫幅印著它的編號（IMG S03-1）。",
        "",
        "【背景】",
        f"文件：{context['name']}",
        f"資料日期：{context['date']}",
    ]
    if node_list:                               # 沒有資料就整段不出現
        parts += ["", "【節點清單】", node_list]
    parts += [
        "", "【任務】", task,
        "", "【硬性規則】",
        "1. 只根據附件回答。附件中查不到的填 null，或回答「附件中無此資料」——這樣回答完全沒有問題。",
        "2. 每一條結論都要有 `cite`，只能用附件裡真的存在的錨點。",
        "3. 數字必須與附件一字不差，不得四捨五入或換算單位。",
        "4. 不要把錨點代號寫進句子裡，來源只填在 `cite`。",
        "", "【輸出】只輸出下面格式的 JSON，不要前言或說明：",
        '{"items": [{"text": "完整的一句話", "cite": ["S03"]}], "unknown_fields": []}',
    ]
    return "\n".join(parts)
```

### 可改段落與契約段落分開

- **可改**：角色、著重點、用詞、某個工地的慣例——可以存在資料庫，讓使用者在後台依分類各自設定，沒設定的走公版。給一個長度上限（例如 4000 字），prompt 有成本。
- **契約**：JSON schema、附件清單、錨點格式、圖片標籤查核規則、資料清單段落——留在程式碼，後台唯讀顯示。改了它，解析結果就對不回程式的欄位。

### 代入使用者文字

```python
def fill(text: str, **values) -> str:
    # 不用 str.format：使用者寫的 JSON 範例或落單的大括號會讓 format 拋例外
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text
```

---

## §2 拿 JSON 的呼叫包裝

```python
from dataclasses import dataclass, field
from .agent_client import AgentClient, AgentPlatformError, RetryExhausted
from .jsonx import extract_json_object

def strict_json_retry_prompt(original: str) -> str:
    return (original + "\n\n【格式要求 —— 非常重要】"
            "\n這次請**只輸出 JSON**，不要任何前言、說明文字、標題或 Markdown 圍欄。"
            "\n你的回應必須以 { 開頭，以 } 結尾。")

@dataclass
class CallRecord:
    label: str
    file_ids: list = field(default_factory=list)
    prompt_chars: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_seconds: float = 0.0
    attempts: int = 1
    parse_status: str = "ok"        # ok | repaired | raw_only
    maybe_truncated: bool = False
    raw_response: str = ""
    error: str = ""
    retryable: bool = False

def call_and_parse(client: AgentClient, prompt: str, file_ids: list, label: str,
                   *, max_tokens: int = 2048):
    """回傳 (dict | None, CallRecord)。抽不出 JSON 不拋例外，讓工作降級完成。"""
    rec = CallRecord(label=label, file_ids=list(file_ids), prompt_chars=len(prompt))
    try:
        r = client.chat(prompt, file_ids, max_tokens=max_tokens)
    except AgentPlatformError as exc:
        rec.error, rec.parse_status = str(exc), "raw_only"
        rec.retryable = isinstance(exc, RetryExhausted)   # 工作層據此決定要不要整份重跑
        return None, rec

    rec.prompt_tokens, rec.completion_tokens = r.usage.prompt_tokens, r.usage.completion_tokens
    rec.elapsed_seconds, rec.attempts = r.elapsed_seconds, r.attempts
    rec.maybe_truncated, rec.raw_response = r.maybe_truncated, r.content

    data = extract_json_object(r.content)
    if data is not None:
        return data, rec
    try:                                                   # 只嚴格重試一次
        r2 = client.chat(strict_json_retry_prompt(prompt), file_ids, max_tokens=max_tokens)
        rec.attempts += r2.attempts
        rec.prompt_tokens += r2.usage.prompt_tokens
        rec.completion_tokens += r2.usage.completion_tokens
        data = extract_json_object(r2.content)
        if data is not None:
            rec.parse_status, rec.raw_response = "repaired", r2.content
            return data, rec
    except AgentPlatformError as exc:
        rec.error = str(exc)
        rec.retryable = isinstance(exc, RetryExhausted)
    rec.parse_status = "raw_only"
    return None, rec
```

拿到 dict 後，所有欄位都要正規化：`as_list(data.get("items"))`、`as_text(item.get("text"))`。模型可能給 `None`、單一物件、字串、或把字串包成 `{"text": ...}`。

---

## §3 分批與本地合併

```python
def chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]

def run_batched(client, pages, file_ids_for, *, per_call=25, max_tokens=2048):
    parts, records = [], []
    for i, group in enumerate(chunks(pages, per_call), 1):
        prompt = build_prompt(..., task=f"這是第 {i} 批，涵蓋 {group[0].label}–{group[-1].label}……")
        data, rec = call_and_parse(client, prompt, file_ids_for(group), f"part_{i}",
                                   max_tokens=max_tokens)
        records.append(rec)
        if data:
            parts.append(data)
    return merge_locally(parts), records

def merge_locally(parts: list[dict]) -> dict:
    """純資料串接在本地做：省一次 ~3,863 tokens，也不讓模型二次改寫引入幻覺。"""
    merged = {"items": [], "unknown_fields": []}
    seen = set()
    for p in parts:
        merged["items"].extend(as_list(p.get("items")))
        for u in as_list(p.get("unknown_fields")):
            t = as_text(u)
            if t and t not in seen:
                seen.add(t); merged["unknown_fields"].append(t)
    return merged
```

圖片的批次（每批約 6 張）同理；需要「綜合判斷」時才多一次彙整呼叫，而彙整吃的是**各批結構化結果整理成的 Markdown 附件**，不是重送原圖。

跨期比較也一樣：餵**已經解析好的各期結果摘要**，不要重送原文——重讀可能得到和使用者已看過的不一樣的說法。

---

## §4 來源比對（grounding）

```python
import re

NUMBER_RE = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?%?")
TRIVIAL = {str(i) for i in range(11)} | {"100"}

OK, VISUAL_ONLY, NO_CITE, BAD_CITE, UNVERIFIED = (
    "ok", "visual_only", "no_cite", "bad_cite", "unverified_number")
FAILED = {NO_CITE, BAD_CITE, UNVERIFIED}

class Grounder:
    def __init__(self, text_by_anchor: dict[str, str], image_labels: set[str]):
        self.text = text_by_anchor           # {"S03": "...", "T03-1": "..."}
        self.images = image_labels           # {"IMG S03-1", ...} —— 真的送出去的那些
        self.all_text = "\n".join(text_by_anchor.values())

    def exists(self, cite: str) -> bool:
        return cite in self.images if cite.startswith("IMG ") else cite in self.text

    def check(self, text: str, cites: list[str]) -> dict:
        cites = [c.strip().strip("[]") for c in cites if c and c.strip()]
        if not cites:
            return {"verdict": NO_CITE}
        unknown = [c for c in cites if not self.exists(c)]
        if unknown:
            return {"verdict": BAD_CITE, "unknown_cites": unknown}
        text_cites = [c for c in cites if not c.startswith("IMG ")]
        if not text_cites:
            return {"verdict": VISUAL_ONLY}  # 中性：不算通過也不算失敗
        source = "\n".join(self.text[c] for c in text_cites).replace(",", "")
        missing = [n for n in (t.replace(",", "") for t in NUMBER_RE.findall(text))
                   if n.rstrip("%") not in TRIVIAL and n.rstrip("%") not in source]
        if missing:
            elsewhere = [n for n in missing if n.rstrip("%") in self.all_text.replace(",", "")]
            return {"verdict": UNVERIFIED, "missing": missing,
                    "hint": "數字在別的位置找得到，可能標錯來源" if elsewhere else ""}
        return {"verdict": OK}
```

要點：

- 錨點清單用**程式真正送出的內容**建，不是模型說它看到的。
- 同時引用圖片與文字的結論，**仍然驗證文字部分**——交叉印證不是免驗金牌。
- 圖片的 OCR 文字（若有）與圖片所在頁的文字，可以算進該圖的佐證。
- 結果分三類呈現：文字可回溯（`ok`）、照片判讀（`visual_only`，請對照原圖）、需人工確認（`FAILED`）。

---

## §5 自我更正一輪，然後篩掉

```python
RECHECK_RULES = """【硬性規則】
1. 回去看附件，不要憑印象作答。
2. 引用只能用附件裡真的存在的錨點。
3. 數字必須與附件一字不差。
4. 不要為了讓結論成立而換一個看起來合理的來源。找不到就收回，收回不是失敗。

每一筆選一個 action：
* corrected —— 找得到正確的來源或數值，附上改好的 text 與 cite。
* withdrawn —— 附件裡根本沒有這件事。這個選項沒有任何問題。
* kept —— 你能明確指出原本為什麼是對的，在 reason 講清楚。講不出理由請改選 withdrawn。

只輸出 JSON：{"corrections": [{"id": "P1", "action": "...", "text": "...", "cite": [], "reason": "..."}]}"""

def recheck_once(client, problems: list[dict], file_ids: list[str]):
    if not problems:
        return [], None
    listing = "\n".join(
        f"【{p['id']}】{p['verdict']}\n  內容：{p['text']}\n  你標的來源：{p['cites'] or '（未標）'}"
        for p in problems)
    prompt = f"你上一輪的結論裡有 {len(problems)} 條經程式比對確定有問題：\n{listing}\n\n{RECHECK_RULES}"
    data, rec = call_and_parse(client, prompt, file_ids, "grounding_recheck")
    return as_list((data or {}).get("corrections")), rec
```

流程：比對 → 把 `FAILED` 的那幾條退回**一輪** → 套用 corrected / 移除 withdrawn → 再比對一次 → **篩選**：

- 不存在的錨點從結論中拿掉；
- 錨點全部不存在的結論整條排除，不進下游（報表、通知、下一期比對）；
- 同時有真假錨點的只拿掉假的；
- 被排除的內容與收回的原文保留在紀錄（例如 payload 的 `screened`、報告的「已排除」章節）——排除不是刪除。

不要一直重問：多輪會讓模型往「總得改點什麼」漂。

---

## §6 平台算得出來的事實，不問模型

日期推導的狀態（某節點依計畫今天該完成了沒）、兩期之間的差值、百分比比較——這些在本地算。模型負責「說法」：依據附件說實際進行到哪裡、理由、來源。兩者對不上時明確標示，不要挑一個留下。

---

## §7 工作層：背景執行、兩層重試、完成閘門

```python
def run_job(job, client):
    failures = []
    for stage in REQUIRED_STAGES:
        result = stage.run(client, job)
        if not result.ok:
            failures.append({"stage": stage.name, "error": result.error,
                             "retryable": any(r.retryable for r in result.calls)})
    if failures and all(f["retryable"] for f in failures) and job.auto_retries_left > 0:
        job.status = "retry_wait"           # JOB_RETRY_DELAY_SECONDS 後重排
        job.auto_retries_left -= 1
    elif failures:
        job.status = "failed"               # 由人確認原因後手動重跑
    else:
        job.status = "done"
        trigger_downstream(job)             # 只有全部成功才寄信、產報表
    cleanup_remote_files(client, job)       # 除非 KEEP_REMOTE_FILES
```

- 一次呼叫常要數十秒，放背景工作；網站只寫入佇列並回 202 + `status_url`，前端輪詢。
- 執行中定期寫心跳；服務重啟後，心跳過期的工作重新排隊，而不是丟「服務重新啟動」的失敗給使用者。

---

## §8 DemoClient

```python
class DemoClient:
    """介面與 AgentClient 相同；回傳擬真的固定結果，讓沒有憑證的人也能走完流程。"""
    def upload_file(self, path, purpose="assistants"):
        return UploadedFile(file_id=f"demo-{Path(path).name}", filename=Path(path).name)
    def upload_files(self, paths, purpose="assistants"):
        return [self.upload_file(p) for p in paths]
    def chat(self, text, file_ids=None, *, max_tokens=2048):
        return ChatResult(content=pick_canned_reply(text), usage=Usage(3863, 400, 4263))
    def delete_file(self, file_id): return True
    def healthcheck(self): return {"ok": True, "reply": "OK (demo)"}
```

依 prompt 裡的關鍵字（例如任務標題）挑對應的範例 JSON 回傳；範例最好也含一條捏造數字，讓 demo 畫面就能看到來源比對的效果。
