#!/usr/bin/env python
"""對真實的內部 Agent 平台做上線前檢查。

讀環境變數（或目前資料夾、APP_CONFIG_FILE 指向的 .env）中的
BASE_URL / API_KEY / MODEL_ID / CA_BUNDLE / VERIFY_SSL。

    python selftest.py [一張測試圖片.jpg]

需要 requests；給了圖片時還需要 Pillow（測視覺能力）。
結束碼 0 = 全部通過。
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_client import AgentClient, AgentPlatformError, RouteNotImplemented  # noqa: E402
from jsonx import extract_json_object                                         # noqa: E402

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    _results.append((ok, label))
    print(f"  {'OK ' if ok else 'NG '} {label}" + (f"  {detail}" if detail else ""))
    return ok


def load_env() -> None:
    """簡易 .env 讀取：不覆蓋已存在的環境變數。"""
    for candidate in (os.getenv("APP_CONFIG_FILE"), ".env"):
        if not candidate or not Path(candidate).is_file():
            continue
        for line in Path(candidate).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        print(f"設定檔：{candidate}")
        return


def main() -> int:
    load_env()
    base_url = (os.getenv("BASE_URL") or "").rstrip("/")
    api_key = os.getenv("API_KEY") or ""
    model_id = os.getenv("MODEL_ID") or ""
    missing = [k for k, v in (("BASE_URL", base_url), ("API_KEY", api_key),
                              ("MODEL_ID", model_id)) if not v]
    if missing:
        print(f"NG  尚未設定：{', '.join(missing)}")
        return 2
    if base_url.endswith("/v1"):
        print("NG  BASE_URL 不要包含 /v1，程式會自己組")
        return 2

    ca = (os.getenv("CA_BUNDLE") or "").strip()
    if ca and not Path(ca).is_file():
        print(f"NG  CA_BUNDLE 指到的檔案不存在：{ca}")
        return 2
    verify: bool | str = ca or (os.getenv("VERIFY_SSL", "true").lower() not in ("0", "false", "no", "off"))

    print(f"平台：{base_url}\n模型：{model_id}\nTLS 驗證：{verify}\n")
    client = AgentClient(base_url, api_key, model_id,
                         timeout=int(os.getenv("REQUEST_TIMEOUT") or 120),
                         max_retries=int(os.getenv("MAX_RETRIES") or 2),
                         upload_settle_seconds=float(os.getenv("UPLOAD_SETTLE_SECONDS") or 3.0),
                         verify=verify)

    print("1. 連線與認證")
    health = client.healthcheck()
    if not check(bool(health.get("ok")), "最小對話可取得非空回應",
                 f"{health.get('elapsed_seconds')}s"):
        print(f"     {health.get('error_type')}: {health.get('error')}")
        return 1
    overhead = int(health.get("prompt_tokens") or 0)
    check(overhead > 3000, "固定 prompt 開銷（約 3,863）", f"實測 {overhead}")

    print("\n2. 檔案路由")
    try:
        client.list_files()
        check(True, "GET /v1/files 可用")
    except RouteNotImplemented:
        check(False, "GET /v1/files 未實作")
    except AgentPlatformError as exc:
        check(False, "GET /v1/files 失敗", str(exc)[:80])

    tmp = Path(tempfile.mkdtemp(prefix="agent-selftest-"))
    uploaded: list[str] = []
    try:
        print("\n3. 上傳與引用")
        marker = f"SELFTEST-{int(time.time())}"
        probe = tmp / "probe.md"
        probe.write_text(f"# 自我測試\n\n驗證碼是 {marker}。\n\n進度數值：87.3%\n", encoding="utf-8")
        up = client.upload_file(probe)
        uploaded.append(up.file_id)
        check(True, "上傳成功", up.file_id)
        r = client.chat("請讀取附件，回答驗證碼是什麼。只回答驗證碼本身。", [up.file_id], max_tokens=64)
        check(marker in r.content, "附件內容可被讀取", r.content.strip()[:60])
        check(r.usage.prompt_tokens < overhead + 500, "檔案內容不計入 prompt_tokens",
              str(r.usage.prompt_tokens))

        print("\n4. JSON 輸出（response_format 無效，靠 prompt 約束）")
        r = client.chat('請讀取附件，只輸出 JSON：{"code": "驗證碼", "progress": 數值}。不要任何說明。',
                        [up.file_id], max_tokens=256)
        data = extract_json_object(r.content)
        check(data is not None, "回應可抽出 JSON", str(data)[:70] if data else r.content[:70])
        if data:
            check(str(data.get("code", "")).strip() == marker, "JSON 內容正確", str(data.get("code")))

        print("\n5. 幻覺行為")
        r = client.chat("請僅根據附件回答：設備 X-7749 的目前狀態與溫度是多少？"
                        "附件中查不到的，請明確回答「附件中無此資料」。", [up.file_id], max_tokens=256)
        refused = "無此資料" in r.content or "沒有" in r.content
        check(refused, "對不存在的資料會拒答", r.content.strip()[:70])
        if not refused:
            print("     ! 平台仍會捏造資料——來源比對層是必要的")

        print("\n6. 視覺能力")
        image = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        if not (image and image.is_file()):
            print("  --  未提供圖片，略過（用法：python selftest.py 測試圖片.jpg）")
        else:
            from label_banner import stage_image
            staged = stage_image(image, "IMG S01-1", tmp)
            up_img = client.upload_file(staged)
            uploaded.append(up_img.file_id)
            r = client.chat("附件是一張圖片。請先回答圖片上方黑色橫幅印的編號，"
                            "再描述畫面內容。看不到的不要編造。只輸出 JSON："
                            '{"visible_label": "...", "description": "..."}',
                            [up_img.file_id], max_tokens=400)
            data = extract_json_object(r.content) or {}
            blind = any(k in r.content for k in ("無法看到", "看不到圖片", "沒有視覺"))
            check(not blind, "模型看得到圖片", r.content.strip()[:70])
            check(str(data.get("visible_label", "")).replace(" ", "") == "IMGS01-1",
                  "讀得到像素上的標籤", str(data.get("visible_label")))
            if blind:
                print("     ! 改走 PDF 包裝：把圖逐張畫進 PDF、頁首印標籤，整份上傳")
    except AgentPlatformError as exc:
        check(False, "執行中斷", f"{type(exc).__name__}: {exc}"[:120])
    finally:
        print("\n7. 清理")
        for fid in uploaded:
            check(client.delete_file(fid), f"刪除遠端檔案 {fid}")
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(ok for ok, _ in _results)
    print(f"\n結果：{passed}/{len(_results)} 通過")
    for ok, label in _results:
        if not ok:
            print(f"  - {label}")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
