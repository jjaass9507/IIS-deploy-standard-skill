"""AgentClient 與 jsonx 的範例測試：不需要 API key，不打真平台。

把 scripts/agent_client.py、scripts/jsonx.py 複製進專案後，
把這份與 fake_platform.py 放進專案的 tests/，並改成專案的 import 路徑。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts"))   # skill 內直接執行時使用

from agent_client import (  # noqa: E402
    FORBIDDEN_PARAMS, AgentClient, AuthError, RetryExhausted, RouteNotImplemented,
    build_user_content,
)
from fake_platform import FakePlatformSession  # noqa: E402
from jsonx import as_list, as_text, extract_json_object  # noqa: E402


def make(session: FakePlatformSession, **kw) -> AgentClient:
    return AgentClient("http://fake:8080", "key", "model-uuid", session=session,
                       sleep=lambda s: None, **kw)


def test_only_valid_file_shape():
    content = build_user_content("hi", ["file-1", "", "file-2"])
    assert content[0] == {"type": "text", "text": "hi"}
    assert content[1:] == [{"type": "file", "file": {"file_id": "file-1"}},
                           {"type": "file", "file": {"file_id": "file-2"}}]
    assert all(p["type"] != "file_id" for p in content)


def test_chat_sends_no_ignored_params_and_reads_content():
    s = FakePlatformSession(replies=["你好"])
    r = make(s).chat("說你好")
    assert r.content == "你好"
    assert not (FORBIDDEN_PARAMS & s.chat_calls[0]["body"].keys())
    assert r.usage.prompt_tokens >= 3863


def test_empty_200_is_retried():
    s = FakePlatformSession(replies=["OK"], empty_first=1)
    r = make(s, max_retries=2).chat("ping")
    assert r.content == "OK" and r.attempts == 2


def test_transient_5xx_is_retried_then_exhausted():
    s = FakePlatformSession(replies=["OK"], timeout_first=5)
    with pytest.raises(RetryExhausted):
        make(s, max_retries=1).chat("ping")


def test_route_missing_is_not_retried():
    s = FakePlatformSession()
    c = make(s)
    with pytest.raises(RouteNotImplemented):
        c._check_transport(s.get("http://fake:8080/v1/models"))


def test_bad_key_is_auth_error():
    s = FakePlatformSession(api_key="right")
    with pytest.raises(AuthError):
        make(s).chat("ping")


def test_non_positive_max_tokens_blocked_before_sending():
    s = FakePlatformSession()
    with pytest.raises(ValueError):
        make(s).chat("ping", max_tokens=0)
    assert s.chat_calls == []


def test_upload_reference_and_delete(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# x", encoding="utf-8")
    s = FakePlatformSession(replies=["ok"])
    c = make(s)
    up = c.upload_files([f])[0]
    c.chat("讀附件", [up.file_id])
    assert s.chat_calls[0]["file_ids"] == [up.file_id]
    assert c.delete_file(up.file_id) and s.deleted == [up.file_id]


@pytest.mark.parametrize("raw", [
    '{"a": 1}',
    '以下是結果：\n```json\n{"a": 1}\n```\n希望有幫助',
    '說明文字 {"a": 1} 結尾',
])
def test_extract_json_variants(raw):
    assert extract_json_object(raw) == {"a": 1}


def test_extract_json_repairs_truncation():
    data = extract_json_object('{"items": [{"t": "一"}, {"t": "二"}, {"t": "三')
    assert data is not None and data["items"][:2] == [{"t": "一"}, {"t": "二"}]


def test_normalisers():
    assert as_list(None) == [] and as_list({"x": 1}) == [{"x": 1}]
    assert as_text({"text": " 內容 "}) == "內容" and as_text(3) == "3"
