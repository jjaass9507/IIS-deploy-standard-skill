"""容錯 JSON 抽取。

平台的 response_format 完全無效(json_object / json_schema 都不遵守),
所以結構化輸出只能靠 prompt 約束 + 這裡的容錯抽取。
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.+?)\s*```", re.S)

# 回應被輸出上限截斷時的補救上限,避免 O(n^2) 掃描失控
_MAX_SCAN = 200_000


def _try_load(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _repair_truncated(text: str) -> Any | None:
    """回應被 max_tokens 砍斷時,補上缺少的括號再試一次。

    平台觀察到的輸出上限約 1825 tokens,長清單常在中途被切斷,
    這種情況下前面已完成的項目仍有價值,不該整包丟掉。
    """
    stack: list[str] = []
    in_str = False
    escape = False
    last_safe = -1  # 最後一個「結構上可安全截斷」的位置

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == "," and stack:
            last_safe = i

    if not stack:
        return None

    # 先試「原文 + 補齊括號」
    candidate = text + "".join(reversed(stack))
    parsed = _try_load(candidate)
    if parsed is not None:
        return parsed

    # 再試「砍到最後一個完整項目 + 補齊括號」
    if last_safe > 0:
        head = text[:last_safe]
        stack2: list[str] = []
        in_str = escape = False
        for ch in head:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                stack2.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack2:
                stack2.pop()
        return _try_load(head + "".join(reversed(stack2)))
    return None


def extract_json(text: str | None) -> Any | None:
    """從可能夾雜 Markdown 圍欄與說明文字的回應中抽出 JSON。

    依序嘗試:整段 -> 圍欄內容 -> 由長至短的子字串 -> 截斷修復。
    抽不出來回傳 None(呼叫端負責降級處理,絕不讓 job 崩潰)。
    """
    if not text or not text.strip():
        return None
    text = text[:_MAX_SCAN]

    parsed = _try_load(text.strip())
    if parsed is not None:
        return parsed

    candidates: list[str] = []
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1))
    candidates.append(text)

    for cand in candidates:
        parsed = _try_load(cand.strip())
        if parsed is not None:
            return parsed

        starts = [i for i in (cand.find("{"), cand.find("[")) if i >= 0]
        if not starts:
            continue
        start = min(starts)
        body = cand[start:]

        # 先找最外層的收尾括號,避免退化成 O(n^2) 全掃描
        closer = "}" if body[0] == "{" else "]"
        end = body.rfind(closer)
        while end > 0:
            parsed = _try_load(body[: end + 1])
            if parsed is not None:
                return parsed
            end = body.rfind(closer, 0, end)

        parsed = _repair_truncated(body)
        if parsed is not None:
            return parsed

    return None


def extract_json_object(text: str | None) -> dict[str, Any] | None:
    """只接受 dict 結果;拿到 list 時取第一個 dict 元素。"""
    parsed = extract_json(text)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                return item
    return None


def as_list(value: Any) -> list[Any]:
    """把模型可能給出的 None / 單一物件 / 字串,一律正規化成 list。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_text(value: Any) -> str:
    """把模型可能給出的 dict / list / 數字,壓成可顯示的字串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(as_text(v) for v in value if v is not None).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "description", "value", "item", "說明", "內容"):
            if key in value:
                return as_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)
