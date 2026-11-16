"""測試用的假平台：替代 requests.Session，不用開 HTTP 伺服器。

重現內部 Agent 平台的已知行為：
  * 每次呼叫固定約 3863 prompt tokens，檔案內容不計入
  * 同時提供 choices[].message.content 與非標準的 choices[].text
  * 未實作路由回 500 + "No static resource"
  * content 用了 {"type":"file_id"} 會 504
  * max_tokens 非法時回 429（假限流）
  * 可設定前幾次回 200 空內容、或回 504 database_timeout

用法::

    session = FakePlatformSession(replies=['{"items": []}'])
    client = AgentClient("http://fake", "k", "m", session=session, sleep=lambda s: None)
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

FIXED_PROMPT_TOKENS = 3863


class _Resp:
    def __init__(self, status: int, body: Any, method: str = "POST", url: str = "") -> None:
        self.status_code = status
        self._body = body
        self.request = type("Req", (), {"method": method, "url": url})()

    @property
    def text(self) -> str:
        return self._body if isinstance(self._body, str) else json.dumps(self._body, ensure_ascii=False)

    def json(self) -> Any:
        if isinstance(self._body, str):
            return json.loads(self._body)
        return self._body


class FakePlatformSession:
    def __init__(self, *, replies: list[str] | None = None,
                 reply_fn: Callable[[str, list[str]], str] | None = None,
                 empty_first: int = 0, timeout_first: int = 0,
                 api_key: str | None = None) -> None:
        self.files: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []
        self.chat_calls: list[dict[str, Any]] = []
        self._replies = list(replies or [])
        self._reply_fn = reply_fn
        self._empty_left = empty_first
        self._timeout_left = timeout_first
        self._api_key = api_key

    # --- helpers ---
    def _auth_ok(self, kw) -> bool:
        if self._api_key is None:
            return True
        return kw.get("headers", {}).get("Authorization") == f"Bearer {self._api_key}"

    @staticmethod
    def _missing(method: str, url: str) -> _Resp:
        path = url.split("/v1", 1)[-1]
        return _Resp(500, {"errId": -1, "status": "EXCEPTION",
                           "message": f"No static resource {path.lstrip('/')}.",
                           "resultSet": []}, method, url)

    # --- HTTP verbs ---
    def post(self, url: str, **kw) -> _Resp:
        if not self._auth_ok(kw):
            return _Resp(401, {"error": {"code": "invalid_api_key"}}, "POST", url)
        path = url.split("/v1", 1)[-1]
        if path == "/files":
            fid = f"file-{len(self.files) + 1:04d}"
            name = kw.get("files", {}).get("file", ("unknown",))[0]
            self.files[fid] = {"id": fid, "filename": name, "bytes": 100, "purpose": "assistants"}
            return _Resp(200, self.files[fid], "POST", url)
        if path == "/chat/completions":
            return self._chat(url, kw["json"])
        return self._missing("POST", url)

    def get(self, url: str, **kw) -> _Resp:
        path = url.split("/v1", 1)[-1]
        if path == "/files":
            return _Resp(200, {"object": "list", "data": list(self.files.values())}, "GET", url)
        m = re.match(r"^/files/([^/]+)$", path)
        if m:
            f = self.files.get(m.group(1))
            return _Resp(200, f, "GET", url) if f else _Resp(404, {"error": "not found"}, "GET", url)
        return self._missing("GET", url)

    def delete(self, url: str, **kw) -> _Resp:
        m = re.match(r"^/files/([^/]+)$", url.split("/v1", 1)[-1])
        if m and m.group(1) in self.files:
            self.files.pop(m.group(1))
            self.deleted.append(m.group(1))
            return _Resp(200, {"id": m.group(1), "deleted": True}, "DELETE", url)
        return self._missing("DELETE", url)

    # --- chat ---
    def _chat(self, url: str, body: dict) -> _Resp:
        if int(body.get("max_tokens", 1)) < 1:
            return _Resp(429, {"error": {"code": "rate_limit_exceeded"}}, "POST", url)
        content = body["messages"][0]["content"]
        if isinstance(content, list) and any(p.get("type") == "file_id" for p in content):
            return _Resp(504, "gateway timeout", "POST", url)
        if self._timeout_left > 0:
            self._timeout_left -= 1
            return _Resp(504, {"error": {"code": "database_timeout",
                                         "message": "Database query timeout. Please retry later."}},
                         "POST", url)
        prompt = content[0]["text"] if isinstance(content, list) else str(content)
        file_ids = [p["file"]["file_id"] for p in content[1:]] if isinstance(content, list) else []
        self.chat_calls.append({"prompt": prompt, "file_ids": file_ids, "body": body})

        if self._empty_left > 0:
            self._empty_left -= 1
            text = ""
        elif self._reply_fn:
            text = self._reply_fn(prompt, file_ids)
        elif self._replies:
            text = self._replies.pop(0)
        else:
            text = "OK"
        prompt_tokens = FIXED_PROMPT_TOKENS + len(prompt) // 4
        completion = max(1, len(text) // 3)
        return _Resp(200, {
            "id": "chatcmpl-fake", "thread_id": f"thread-{len(self.chat_calls)}",
            "object": "chat.completion", "created": int(time.time()), "model": body.get("model"),
            "choices": [{"index": 0, "text": text,
                         "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion,
                      "total_tokens": prompt_tokens + completion},
        }, "POST", url)
