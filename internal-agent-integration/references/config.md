# 設定

## `.env.example` 片段（直接貼進專案）

```ini
# --- Demo 模式 -----------------------------------------------
# true = 用內建範例跑完整流程，不需要任何憑證
DEMO_MODE=false

# --- 內部 Agent 平台（DEMO_MODE=false 時必填）-----------------
# 不要自己加 /v1，程式會組
BASE_URL=http://your-agent-host:8080
API_KEY=
# UUID，只能從平台 UI 取得（/v1/models 未實作，無法列舉）
MODEL_ID=

# --- 呼叫行為 ------------------------------------------------
REQUEST_TIMEOUT=120
MAX_RETRIES=2
RETRY_BACKOFF=2.0
# 上傳後的索引延遲；太快引用會拿到空回應
UPLOAD_SETTLE_SECONDS=3.0
# 實際輸出上限約 1825 tokens；程式會夾在 1–4096
MAX_TOKENS=2048
# 除錯時保留上傳到平台的檔案
KEEP_REMOTE_FILES=false

# --- TLS（平台用 https 且為內部 CA / 自簽憑證時）------------
# 1）建議：指向內部 CA 憑證檔，驗證仍然生效
# CA_BUNDLE=D:\WebServices\<系統名稱>\shared\config\internal-ca.pem
# 2）關閉驗證：連線仍加密但不確認對方身分，只限受控內網
VERIFY_SSL=true

# --- 背景工作 ------------------------------------------------
# 平台的併發與租戶隔離未經驗證，預設一次一份
WORKER_CONCURRENCY=1
# 呼叫層重試用完後，整份工作再自動重跑幾次、間隔幾秒
JOB_AUTO_RETRIES=2
JOB_RETRY_DELAY_SECONDS=60
```

## 設定讀取

```python
import os
from dataclasses import dataclass, field
from pathlib import Path

def _bool(name, default):
    v = os.getenv(name)
    return default if v is None or v == "" else v.strip().lower() in ("1", "true", "yes", "on")

@dataclass
class AgentConfig:
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", False))
    base_url: str = field(default_factory=lambda: (os.getenv("BASE_URL") or "").rstrip("/"))
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY") or "")
    model_id: str = field(default_factory=lambda: os.getenv("MODEL_ID") or "")
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT") or 120))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES") or 2))
    retry_backoff: float = field(default_factory=lambda: float(os.getenv("RETRY_BACKOFF") or 2.0))
    upload_settle_seconds: float = field(
        default_factory=lambda: float(os.getenv("UPLOAD_SETTLE_SECONDS") or 3.0))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS") or 2048))
    keep_remote_files: bool = field(default_factory=lambda: _bool("KEEP_REMOTE_FILES", False))
    ca_bundle: str = field(default_factory=lambda: (os.getenv("CA_BUNDLE") or "").strip())
    verify_ssl: bool = field(default_factory=lambda: _bool("VERIFY_SSL", True))

    def missing(self) -> list[str]:
        if self.demo_mode:
            return []
        return [k for k, v in (("BASE_URL", self.base_url), ("API_KEY", self.api_key),
                               ("MODEL_ID", self.model_id)) if not v]

    @property
    def tls_verify(self) -> bool | str:
        """傳給 requests 的 verify：CA_BUNDLE 優先，否則 VERIFY_SSL。"""
        if self.ca_bundle:
            if not Path(self.ca_bundle).is_file():
                raise ValueError(f"CA_BUNDLE 指到的檔案不存在：{self.ca_bundle}")
            return self.ca_bundle
        return self.verify_ssl
```

`base_url` 若以 `/v1` 結尾，啟動時就提醒使用者拿掉（否則會變成 `/v1/v1/...`，平台回 500 `No static resource`）。

## 與部署規範（python-iis-deploy-standard）一起用

- `API_KEY` 只放在 `shared\config\.env`（`APP_CONFIG_FILE` 指向的檔案），不進版本包、不進 log。
- `CA_BUNDLE` 放在 `shared\config\`，換版本時不會不見。
- 暫存的抽取結果、轉檔、標籤圖寫到 `APP_DATA_DIR` 底下，不要寫進程式目錄。
- 解析工作是長時間任務，依規範拆成 WinSW 背景服務，網站只負責收件與查詢狀態。
- `/health` 不要每次都呼叫 Agent（固定燒 ~3,863 tokens）；需要檢查平台時另做一個管理者觸發的檢查，呼叫 `client.healthcheck()`。
