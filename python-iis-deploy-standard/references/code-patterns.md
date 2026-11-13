# 程式碼寫法

目錄：
1. 設定與寫入路徑（所有框架）
2. 正式環境防呆（所有框架）
3. Flask：子路徑、/health、/version、Cookie
4. FastAPI：子路徑、/health、/version、Cookie
5. Django：設定對應
6. 登入端點與 CSRF
7. Windows SSO：解析權杖
8. AD 帳密（ldap3）
9. 背景服務（WinSW 管理的常駐程式）
10. Migration 指令

完整可執行的版本在 `assets/sample-app/`（Flask）。

## 1. 設定與寫入路徑

```python
# myapp/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# 正式環境由部署工具設定 APP_CONFIG_FILE（shared\config\.env）；開發機沒設定時才讀專案的 .env
load_dotenv(os.environ.get("APP_CONFIG_FILE") or ROOT / ".env", encoding="utf-8-sig")

# 開發機的預設寫入位置放在專案資料夾「外面」，這樣執行時不會弄髒程式目錄
_DEV_HOME = Path(os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp") / "myapp-dev"

def _dir(name: str, default: Path) -> Path:
    path = Path(os.environ.get(name) or default)
    path.mkdir(parents=True, exist_ok=True)
    return path

def log_dir() -> Path:    return _dir("APP_LOG_DIR", _DEV_HOME / "logs")
def data_dir() -> Path:   return _dir("APP_DATA_DIR", _DEV_HOME / "data")
def upload_dir() -> Path: return _dir("APP_UPLOAD_DIR", _DEV_HOME / "upload")
def temp_dir() -> Path:   return _dir("APP_TEMP_DIR", _DEV_HOME / "tmp")

APPLICATION = "myapp"                                   # 與 deployment.json 的 application 相同
APP_VERSION = os.environ.get("APP_VERSION", "dev")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
_prefix = os.environ.get("URL_PREFIX", "").strip("/")
URL_PREFIX = "/" + _prefix if _prefix else ""
```

開發用的 SQLite 也放在資料目錄，不要放在專案資料夾：

```python
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{data_dir() / 'dev.sqlite3'}"
```

log 寫檔：

```python
from logging.handlers import RotatingFileHandler
handler = RotatingFileHandler(log_dir() / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
```

平台自己的其他設定檔（設備清單、告警規則這類有結構的資料）：路徑做成 `.env` 的一個設定項目，名稱由平台自己決定，不要寫死。

```python
# .env.example 也要列出這一項，並說明要準備的檔案
# GMS_SETTINGS_FILE=D:\WebServices\gms-monitor-agent\shared\config\settings.json
SETTINGS_FILE = Path(os.environ.get("GMS_SETTINGS_FILE") or ROOT / "settings.json")

def load_settings() -> dict:
    if not SETTINGS_FILE.is_file():
        # 給部署的人看得懂的訊息，不要直接丟出 FileNotFoundError
        raise SystemExit(f"找不到設定檔 {SETTINGS_FILE}，請確認 .env 的 GMS_SETTINGS_FILE")
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
```

- 正式環境：檔案放在 `shared\config\`（部署腳本已開放網站讀取這個資料夾），由部署的人手動放入；程式會改寫的檔案放 `shared\data\`。
- 開發機：開發者自己的 `.env` 指向開發用的檔案；用部署助手檢查時勾選「用專案的 `.env` 啟動程式」，程式就讀得到。
- repo 裡提交一份範例（例如 `settings.example.json`），不含真實的帳號密碼。

為什麼用函式而不是模組層級的常數：測試會改環境變數，函式每次都讀最新的值；而且匯入模組時不會就建立資料夾。

## 2. 正式環境防呆

```python
def check_production() -> None:
    """APP_ENV=production 時，設定不安全就拒絕啟動。在 create_app 與背景服務的 main 開頭呼叫。"""
    if APP_ENV != "production":
        return
    problems = []
    if AUTH_MODE != "ad":
        problems.append(f"AUTH_MODE 必須是 ad（目前 {AUTH_MODE}）")
    if len(SECRET_KEY) < 32:
        problems.append("SECRET_KEY 至少 32 個字元")
    if problems:
        raise SystemExit("正式環境設定不正確：" + "；".join(problems))
```

檢查工具會用 `APP_ENV=production`＋`AUTH_MODE=mock` 啟動程式，預期它**不會**正常服務。

## 3. Flask

```python
class PrefixMiddleware:
    """掛在 IIS 子應用程式下：把 URL_PREFIX 交給 WSGI 的 SCRIPT_NAME，url_for 就會自動帶前綴。"""
    def __init__(self, app, prefix):
        self.app, self.prefix = app, prefix
    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            return self.app(environ, start_response)
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

def create_app():
    config.check_production()
    app = Flask(__name__)          # 不要用 instance_relative_config，也不要寫入 app.instance_path
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,   # 設定檔可開啟；正式 HTTPS 環境為 true
        SESSION_COOKIE_PATH=config.URL_PREFIX or "/",
    )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/version")
    def version():
        return jsonify(application=config.APPLICATION, version=config.APP_VERSION)

    if config.URL_PREFIX:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, config.URL_PREFIX)
    return app
```

`deployment.json`：`"web": {"framework": "wsgi", "entry": "app:create_app", "factory": true}`，根目錄的 `app.py` 寫 `from myapp import create_app`。

樣板中的連結一律 `{{ url_for('...') }}`；JavaScript 需要 API 根路徑時，由樣板輸出 `{{ request.script_root }}`。

## 4. FastAPI

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

config.check_production()
app = FastAPI(root_path=config.URL_PREFIX)     # root_path 讓產生的網址與文件頁帶前綴

app.add_middleware(
    SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax",
    https_only=config.SESSION_COOKIE_SECURE, path=config.URL_PREFIX or "/",
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"application": config.APPLICATION, "version": config.APP_VERSION}
```

IIS 轉給 Uvicorn 的請求路徑仍然帶著 `/<系統名稱>`，而 `root_path` 只影響「產生網址」，不會幫你剝掉前綴。所以要讓路由真的掛在前綴下，二擇一：

```python
# 作法 A：把整個應用程式掛在前綴下（建議）
inner = FastAPI()            # 路由都定義在 inner
app = FastAPI()
app.mount(config.URL_PREFIX or "/", inner)

# 作法 B：自己剝掉前綴的 ASGI middleware（與上面 Flask 的 PrefixMiddleware 同理，設定 scope["root_path"] 與 scope["path"]）
```

做完後一定要實際測：`URL_PREFIX=/myapp` 啟動，`/myapp/health` 要 200，`/health` 要 404。

`deployment.json`：`"web": {"framework": "asgi", "entry": "main:app", "factory": false}`。

## 5. Django

```python
# settings.py
FORCE_SCRIPT_NAME = config.URL_PREFIX or None
STATIC_URL = (config.URL_PREFIX or "") + "/static/"
SESSION_COOKIE_PATH = config.URL_PREFIX or "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = config.SESSION_COOKIE_SECURE
CSRF_COOKIE_SECURE = config.SESSION_COOKIE_SECURE
MEDIA_ROOT = config.upload_dir()
LOGGING = {...  "filename": str(config.log_dir() / "app.log") ...}
```

- WSGI：`"entry": "myproject.wsgi:application"`，`factory` 為 `false`；ASGI：`myproject.asgi:application`。
- Waitress 不會剝掉前綴，所以和 Flask 一樣需要一層 `PrefixMiddleware` 包住 `application`（寫在 `wsgi.py`）。
- 靜態檔由 WhiteNoise 提供（`STATIC_ROOT` 在程式目錄內，`collectstatic` 要在**打包前**執行並把結果列入 `include`；不要在伺服器啟動時才產生）。

## 6. 登入端點與 CSRF

```python
@bp.get("/api/auth/me")
def me():
    if "account" not in session:
        return jsonify(authenticated=False), 401          # 未登入不回任何個資
    return jsonify(authenticated=True, account=session["account"], role=session["role"], csrf_token=session["csrf"])

@bp.post("/api/auth/login")
def login():
    ...驗證帳密（mock 或 AD）...
    if not valid:
        return jsonify(error="帳號或密碼錯誤"), 401
    return _sign_in(account)

def _sign_in(account):
    role = platform_role(account)        # 平台自己的開通資料；AD 成功不等於開通
    if role is None:
        return jsonify(error="此帳號尚未開通平台權限"), 403
    session.clear()                      # 登入後換新的 Session
    session.update(account=account.lower(), role=role, csrf=secrets.token_urlsafe(32))
    return jsonify(authenticated=True, account=account.lower(), role=role, csrf_token=session["csrf"])

@bp.post("/api/auth/logout")            # 只接受 POST
def logout():
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not session.get("csrf") or not token or not secrets.compare_digest(token, session["csrf"]):
        abort(403)
    session.clear()
    session["sso_paused"] = True         # 登出後不要立刻又被自動登入
    return jsonify(authenticated=False)
```

所有會修改資料的 API 都用同樣的 CSRF 檢查；每個業務 API 在後端檢查角色，不要只靠前端隱藏按鈕。

## 7. Windows SSO：解析權杖

IIS 只對 `/auth/sso` 做 Windows 驗證，HttpPlatformHandler 把使用者的 Windows 權杖以 **Handle（十六進位數字）** 放在 `X-IIS-WindowsAuthToken` 標頭。它不是帳號；要用 Windows API 換成帳號，而且每次都要關閉 Handle，否則每次登入都洩漏一個。

```python
def windows_account(handle: int):
    """由權杖 Handle 取得帳號（只能在 Windows 上執行）。"""
    import ctypes
    from ctypes import wintypes
    advapi32, kernel32 = ctypes.windll.advapi32, ctypes.windll.kernel32
    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(wintypes.HANDLE(handle), 1, None, 0, ctypes.byref(size))   # 1 = TokenUser
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(wintypes.HANDLE(handle), 1, buffer, size, ctypes.byref(size)):
            return None
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents
        name, domain = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
        n, d, use = wintypes.DWORD(256), wintypes.DWORD(256), wintypes.DWORD(0)
        if not advapi32.LookupAccountSidW(None, sid, name, ctypes.byref(n), domain, ctypes.byref(d), ctypes.byref(use)):
            return None
        return name.value          # 需要區分網域時同時使用 domain.value
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))

@bp.get("/auth/sso")
def sso():
    if not config.AUTH_SSO_ENABLED or config.AUTH_MODE != "ad":
        return jsonify(authenticated=False, error="未啟用 Windows 登入"), 404     # 關閉時先擋，不要去解析標頭
    if session.get("sso_paused"):
        return jsonify(authenticated=False), 401
    try:
        handle = int(request.headers.get("X-IIS-WindowsAuthToken", ""), 16)
    except ValueError:
        return jsonify(authenticated=False, error="沒有收到 Windows 權杖"), 401
    account = windows_account(handle) if sys.platform == "win32" else None
    if not account:
        return jsonify(authenticated=False), 401
    return _sign_in(account)       # 與帳密登入走同一個函式
```

開發機（沒有 IIS）測不到真正的 SSO；用 `AUTH_MODE=mock` 測登入後的流程，SSO 要部署到測試 IIS 後另外驗收。

## 8. AD 帳密（ldap3）

部門預設不強制驗證 AD 伺服器的憑證，但把它做成設定，環境準備好時不用改程式就能開啟：

```python
def verify_ad(account: str, secret: str) -> bool:
    import ssl
    from ldap3 import Connection, Server, Tls
    use_ssl = config.AD_SERVER.lower().startswith("ldaps://")
    tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=config.AD_CA_FILE) if (use_ssl and config.AD_CA_FILE) else None
    server = Server(config.AD_SERVER, use_ssl=use_ssl, tls=tls, connect_timeout=8)
    with Connection(server, user=f"{config.AD_DOMAIN}\\{account}", password=secret) as conn:   # SIMPLE bind
        return bool(conn.bound)
```

- 空密碼要先擋掉（AD 對空密碼的 bind 可能視為匿名成功）。
- 用 SIMPLE bind，不要用 NTLM（新版 Python 沒有 MD4，會出現 `unsupported hash type MD4`）。
- 不要把 `secret` 寫進 log 或例外訊息。

## 9. 背景服務

```python
# myapp/worker.py —— python -m myapp.worker
import json, logging, signal, time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from . import config

INTERVAL_SECONDS = 60
_stop = False

def _on_signal(signum, frame):
    global _stop
    _stop = True

def run_once():
    ...實際的工作；設計成重複執行也不會出錯...
    status = {"scheduler": "running", "version": config.APP_VERSION,
              "last_success": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    target = config.data_dir() / "worker-status.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    temp.replace(target)                      # 先寫暫存檔再取代，讀的人不會讀到寫一半的內容

def main():
    config.check_production()
    logging.basicConfig(level=logging.INFO, handlers=[
        RotatingFileHandler(config.log_dir() / "worker.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"),
        logging.StreamHandler()])
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    next_run = 0.0
    while not _stop:                          # 常駐迴圈：不是跑一次就結束
        if time.monotonic() >= next_run:
            try:
                run_once()
            except Exception:
                logging.exception("run_once failed")     # 單次失敗不讓整個服務結束
            next_run = time.monotonic() + INTERVAL_SECONDS
        time.sleep(1)                         # 短睡眠，停止訊號來時能在一秒內結束

if __name__ == "__main__":
    main()
```

網站和背景服務之間用資料庫（或佇列）交接工作，不要共用記憶體或互相呼叫。使用 APScheduler 時，把 `BlockingScheduler` 放在這個服務模組裡，不要在 `create_app` 裡啟動 `BackgroundScheduler`。

## 10. Migration 指令

```python
# scripts/apply_migrations.py
url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"]   # 部署時由工具提供 migration 帳號
```

- 可重複執行（已套用的不重做），成功結束碼 0、失敗非 0。
- 支援 `--help`（argparse 預設就有），檢查工具會用它確認指令能啟動；否則在 `migrations.checkArgs` 指定。
- `MIGRATION_DATABASE_URL` 不寫進 `.env`。
