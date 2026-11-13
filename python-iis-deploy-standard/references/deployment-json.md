# deployment.json

放在專案根目錄。部署助手靠它決定哪些規則適用、要打包哪些檔案、怎麼啟動程式。

## 欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `standard` | ✓ | 固定 `"1.2"` |
| `application` | ✓ | 系統名稱：小寫英數加連字號（`power-bill-agent`）。會成為網址路徑 `/<application>` 與伺服器上的目錄名稱 |
| `displayName` | | 顯示用的中文名稱 |
| `version` | ✓ | `主.次.修`（`1.4.0`）。`CHANGELOG.md` 必須有這個版本 |
| `python` | ✓ | 與部署機相同的 Python 版本，`"3.12"` |
| `type` | ✓ | `"web"`、`"services"` 或 `"web+services"` |
| `web.framework` | 網站 | `"wsgi"`（Waitress）或 `"asgi"`（Uvicorn） |
| `web.entry` | 網站 | `模組:物件`，例如 `"app:create_app"`、`"main:app"` |
| `web.factory` | | `entry` 是工廠函式（呼叫後才得到應用程式）時為 `true` |
| `web.health`、`web.version` | | 預設 `"/health"`、`"/version"` |
| `web.probePage` | | 檢查子路徑連結用的頁面，預設 `"/"` |
| `web.frontend` | | 有前端時：`{"dir": "frontend", "build": "npm run build", "output": "frontend/dist"}`，打包時會建置，只帶 `output` |
| `web.scheduling` | | 網站含排程時的架構。省略或 `"split"`＝拆成背景服務（首選）。其他值需登記例外 `DECL-05` |
| `auth.ad` | | 有使用者登入時 `true` |
| `auth.sso` | | 有使用者登入的網站必須 `true` |
| `auth.employeeLookup` | | 有從 `base.kh_ad_employees` 選人的功能時 `true` |
| `auth.meEndpoint`、`loginEndpoint`、`logoutEndpoint`、`ssoEndpoint` | | 預設 `/api/auth/me`、`/api/auth/login`、`/api/auth/logout`、`/auth/sso`；既有系統路徑不同時在這裡指定 |
| `auth.rbac` | 有登入 | 一兩句話說明平台如何記錄「已開通的帳號與角色」 |
| `services[]` | 背景服務 | 見下 |
| `include` | ✓ | 要打包的檔案與資料夾（相對於專案根目錄）。沒列的不會打包 |
| `configTemplate` | | 設定範本，預設 `".env.example"` |
| `selfTest.env` | ✓ | 檢查工具啟動程式時用的設定：要讓程式在**沒有正式資料庫、沒有 AD** 的情況下也能啟動（例如 SQLite＋`AUTH_MODE=mock`）。不會被打包 |
| `migrations.args` | | Migration 指令（接在 venv 的 python 後面），例如 `["scripts/apply_migrations.py"]`；沒有資料庫時 `[]` |
| `migrations.compatibility` | 有 Migration | `"backward-compatible"`、`"restore-plan"` 或 `"none"` |
| `migrations.notes` | 有 Migration | 這一版改了什麼、為何舊版仍可運作；`restore-plan` 時寫還原計畫 |
| `migrations.checkArgs` | | 指令不支援 `--help` 時，指定一組只檢查不修改的參數 |
| `reviewed[]` | | 檢查工具「靠掃描推測」的項目誤判時的人工確認：`{"rule", "file", "note", "by"}` |
| `exceptions[]` | | 暫時做不到的項目：`{"rule", "reason", "risk", "owner", "plan", "until": "yyyy-MM-dd"}`，六項都要填，過期失效 |

### services[]

| 欄位 | 說明 |
|---|---|
| `id` | 服務名稱，小寫英數加連字號，建議 `<application>-worker` |
| `kind` | `"venv"`（預設）或 `"pyinstaller"`（需另給 `spec`） |
| `args` | 接在 venv 的 python 後面的參數，例如 `["-m", "myapp.worker"]` |
| `scheduled` | 會依排程執行工作時 `true` |
| `restart` | 失敗時如何重啟，例如 `"on-failure"` |
| `stopTimeoutSeconds` | 收到停止訊號後多久內要結束 |
| `lastSuccess` | 如何得知最後成功時間，例如 `"file:${APP_DATA_DIR}/worker-status.json"` |
| `dedup` | （排程）如何防止同一個任務被重複執行 |
| `catchUp` | （排程）停機後如何補跑或告警 |
| `selfTest` | 檢查工具怎麼試這個服務：`"start"`（預設）在暫存資料夾啟動、觀察 15 秒後停止；`"load"` 只確認程式與套件載入得了，用於一啟動就需要正式資料庫或設備的服務 |

## 範例一：只有網站（Flask，有登入）

```json
{
  "standard": "1.2",
  "application": "asset-portal",
  "displayName": "資產查詢平台",
  "version": "1.0.0",
  "python": "3.12",
  "type": "web",
  "web": { "framework": "wsgi", "entry": "app:create_app", "factory": true },
  "auth": { "ad": true, "sso": true, "employeeLookup": false,
            "rbac": "platform_users 資料表的 is_active 與 role；未開通者登入後回 403" },
  "include": ["app.py", "asset_portal", "migrations", "scripts"],
  "selfTest": { "env": { "APP_ENV": "development", "AUTH_MODE": "mock", "DATABASE_URL": "" } },
  "migrations": { "args": ["scripts/apply_migrations.py"], "compatibility": "backward-compatible",
                  "notes": "新增 assets.location 欄位（可為空），舊版程式不讀取此欄位" }
}
```

## 範例二：網站＋背景服務（FastAPI）

```json
{
  "standard": "1.2",
  "application": "gms-monitor-agent",
  "version": "2.3.1",
  "python": "3.12",
  "type": "web+services",
  "web": { "framework": "asgi", "entry": "main:app", "factory": false,
           "frontend": { "dir": "frontend", "build": "npm run build", "output": "frontend/dist" } },
  "auth": { "ad": true, "sso": true, "rbac": "role_assignment 資料表；無角色者只能看首頁" },
  "services": [
    { "id": "gms-monitor-agent-collector", "kind": "venv", "args": ["-m", "gms.collector"], "scheduled": true,
      "restart": "on-failure", "stopTimeoutSeconds": 30,
      "lastSuccess": "file:${APP_DATA_DIR}/collector-status.json",
      "dedup": "每筆採集以（設備、時間）為唯一鍵寫入，重複執行不會產生重複資料",
      "catchUp": "啟動時從狀態檔的最後成功時間補抓到現在" }
  ],
  "include": ["main.py", "gms", "migrations"],
  "selfTest": { "env": { "APP_ENV": "development", "AUTH_MODE": "mock" } },
  "migrations": { "args": ["-m", "alembic", "upgrade", "head"], "checkArgs": ["-m", "alembic", "--help"],
                  "compatibility": "none", "notes": "本版沒有資料庫變更" }
}
```

## 範例三：只有背景服務（沒有網站、沒有登入）

```json
{
  "standard": "1.2",
  "application": "opc-collector",
  "version": "1.2.0",
  "python": "3.12",
  "type": "services",
  "services": [
    { "id": "opc-collector", "kind": "venv", "args": ["-m", "opc_collector"], "scheduled": false,
      "restart": "on-failure", "stopTimeoutSeconds": 20,
      "lastSuccess": "file:${APP_DATA_DIR}/status.json" }
  ],
  "include": ["opc_collector"],
  "selfTest": { "env": { "APP_ENV": "development", "OPC_ENDPOINT": "mock" } }
}
```

## 常見錯誤

- `include` 列了 `tests`、`.env`、`frontend`（整個前端原始碼）→ 只列執行需要的程式；前端用 `web.frontend`。
- `selfTest.env` 連正式資料庫 → 檢查工具會在同仁的電腦上啟動程式，請用本機可用的設定。
- `version` 改了但 `CHANGELOG.md` 沒寫 → 兩邊要一起更新。
- 把 `exceptions` 當成略過檢查的方法 → 例外會出現在每一份檢查報告與 Release 包裡，並且有期限。
