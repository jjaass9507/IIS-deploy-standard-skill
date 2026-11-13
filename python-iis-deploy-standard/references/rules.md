# 部署助手的檢查規則

使用者貼上檢查結果時，用規則編號在這裡找原因與修法。「等級」決定不符合時的結果：**必過**＝擋下打包；**警告**＝可打包但會列在報告；**宣告**＝要在 `deployment.json` 寫明，沒寫會擋下。標「可例外」的可以登記 `exceptions`。

## 宣告與架構

| 規則 | 要求 | 等級 |
|---|---|---|
| DECL-01 | 根目錄有格式正確的 `deployment.json`，`standard` 為 `"1.2"` | 必過 |
| DECL-02 | `application` 為小寫英數加連字號 | 必過 |
| DECL-03 | `version` 為 `主.次.修`，且 `CHANGELOG.md` 有此版本 | 必過 |
| DECL-04 | `type`、`web.framework`、`web.entry`、`services[].kind` 合法；`include` 的項目都存在 | 必過 |
| DECL-05 | `web.scheduling` 不是 `split` 時需登記例外 | 必過・可例外 |
| DECL-06 | `python` 為 `3.x` | 必過 |
| ARCH-01 | WSGI 的 lock 有 `waitress`；ASGI 有 `uvicorn` | 必過 |
| ARCH-02 | 進入點能在「只裝了 lock 套件」的環境中載入 | 必過 |
| ARCH-03 | 打包範圍內沒有 `--reload`、`reload=True` | 必過 |
| ARCH-04 | 沒有 NSSM、`schtasks`、`Register-ScheduledTask`、`startup.bat`（打包範圍內＝必過；範圍外的舊腳本＝警告） | 必過・可例外 |
| ARCH-05 | 網站程式裡沒有 APScheduler、`threading.Timer`、`threading.Thread(` 之類的背景工作（服務的啟動模組除外） | 警告（推測） |
| ARCH-06 | PyInstaller 服務有 `.spec` | 必過 |

## 套件與打包內容

| 規則 | 要求 | 等級 |
|---|---|---|
| PKG-01 | 有 `requirements.lock`，每個套件都是 `名稱==版本` | 必過 |
| PKG-02 | 每個套件附 `--hash` | 警告 |
| PKG-03 | lock 只有英文字元；沒有 `-e`、`file:`、`git+`、本機路徑 | 必過 |
| PKG-04 | 所有套件都下載得到 `win_amd64`＋指定 Python 版本的 wheel（不能有只提供原始碼的套件） | 必過 |
| PKG-05 | 只用下載好的 wheel 就能離線安裝（lock 沒有漏列間接相依） | 必過 |
| PKG-06 | `include` 範圍內沒有 `.venv`、`.env`、`*.sqlite3`、`*.db`、`*.log`、`logs/`、`node_modules/`、`.git/` | 必過 |
| PKG-07 | 沒有私鑰（必過）、沒有看起來像真實密碼的連線字串（警告）；`.env.example` 機密項目的值不可與 `.env` 相同（必過） | 必過／警告 |
| PKG-08 | 專案內不要有 `web.config` | 警告 |
| PKG-09 | 有 `.env.example` | 必過 |
| PKG-10 | 有前端時 `npm ci`＋建置成功，並產生新的 `index.html` | 必過 |
| PKG-11 | 開發機 `.env` 的每個設定項目，`.env.example` 都有列出 | 警告 |
| PKG-12 | `.gitignore` 排除 `.env` | 警告 |

## 路徑

| 規則 | 要求 | 等級 |
|---|---|---|
| PATH-01 | 程式碼有讀取 `APP_CONFIG_FILE` | 必過・可例外 |
| PATH-02 | 程式會寫檔時，有讀取 `APP_LOG_DIR`／`APP_DATA_DIR`／`APP_UPLOAD_DIR`／`APP_TEMP_DIR` 至少一個 | 必過・可例外 |
| PATH-03 | 實際啟動並操作後，程式目錄沒有新增或被修改的檔案 | 必過 |

PATH-03 最常見的原因：開發用的 SQLite 預設放在專案資料夾、Flask 的 `instance/`、相對路徑的 `logs/`。把這些預設位置改成讀 `APP_DATA_DIR`／`APP_LOG_DIR`。

## 健康檢查、版本、子路徑

| 規則 | 要求 | 等級 |
|---|---|---|
| HLTH-01 | `<前綴>/health` 回 200 與 `{"status":"ok"}`；健康檢查在別的路徑時，`/health` 也要存在 | 必過 |
| HLTH-02 | `<前綴>/version` 的 `application`、`version` 等於 `deployment.json` | 必過 |
| HLTH-03 | `/health` 的欄位名稱不含 database、host、schema、url、env、prefix、user、mode 等 | 警告（推測） |
| HLTH-04 | 每個背景服務有 `lastSuccess` | 宣告 |
| URL-01 | 設定 `URL_PREFIX=/<application>` 後，程式在該前綴下回應；頁面連結與轉址都帶前綴 | 必過 |
| URL-02 | Session Cookie 的 Path 以前綴開頭 | 警告 |

## 登入

| 規則 | 要求 | 等級 |
|---|---|---|
| AUTH-01 | `.env.example` 有 `AUTH_MODE` 與 `AUTH_SSO_ENABLED` | 必過 |
| AUTH-02 | `APP_ENV=production`＋`AUTH_MODE=mock` 時程式不會正常服務 | 必過 |
| AUTH-03 | 建議 `AD_SERVER` 用 `ldaps://`、ldap3 設定 `Tls(validate=ssl.CERT_REQUIRED)`（部門預設不強制） | 警告 |
| AUTH-04 | log 呼叫中沒有 password 變數 | 警告（推測） |
| AUTH-05 | 使用統一路徑 `/api/auth/me`、`/api/auth/login`、`/api/auth/logout`、`/auth/sso` | 警告 |
| AUTH-06 | 未登入呼叫 me 端點不回傳使用者資料；端點必須存在 | 必過 |
| AUTH-07 | 登出只接受 POST；沒有 CSRF Token 的 POST 被拒 | 必過／警告 |
| AUTH-08 | Cookie 有 `HttpOnly`、`SameSite`；程式有可開啟 `Secure` 的設定 | 必過 |
| AUTH-09 | `auth.rbac` 有說明 | 宣告 |
| AUTH-10 | 不寫入 `base.kh_ad_employees` | 必過 |
| SSO-00 | 有登入的網站 `auth.sso` 為 `true` | 必過・可例外 |
| SSO-01 | 有 `/auth/sso`；讀 `X-IIS-WindowsAuthToken` 後用 `GetTokenInformation`／`LookupAccountSid`（或 pywin32）解析 | 必過／警告 |
| SSO-02 | 有呼叫 `CloseHandle` | 必過 |
| SSO-03 | `AUTH_SSO_ENABLED=false` 時，即使帶了權杖標頭，`/auth/sso` 也不會登入、不會回 500 | 必過／警告 |

## 背景服務、Migration、測試

| 規則 | 要求 | 等級 |
|---|---|---|
| SVC-01 | 每個服務有 `id`、`args`、`restart`、`stopTimeoutSeconds` | 必過 |
| SVC-02 | 工具在暫存資料夾試啟動服務、觀察 15 秒後停止：結束碼 0（批次）或載入錯誤＝必過；其他錯誤（檢查環境缺資料庫、設備）＝警告。`"selfTest": "load"` 時只檢查載入 | 必過／警告・可例外 |
| SVC-03 | 排程服務有 `dedup`、`catchUp` | 宣告 |
| MIG-01 | 專案有 migrations 時，`migrations.compatibility` 與 `notes` 已填 | 宣告 |
| MIG-02 | Migration 指令加 `--help`（或 `checkArgs`）可以執行 | 警告 |
| TEST-01 | 有 `tests/` 且 pytest 全部通過 | 警告 |

## 誤判時

靠掃描程式碼推測的規則（上表標「推測」，以及 PATH-01、PATH-02、PKG-07、SSO-01、SSO-02、AUTH-10）可能誤判。確認程式沒有問題後，在 `deployment.json` 加：

```json
"reviewed": [ { "rule": "ARCH-05", "file": "myapp/report.py", "note": "執行緒只用來平行查詢，請求結束前就會 join", "by": "K12345" } ]
```

`note` 與 `by` 要由負責的人填；不要替使用者編造確認人。
