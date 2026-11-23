---
name: python-iis-deploy-standard
description: 讓 Python 網站或背景服務符合部門《Python 程式與平台部署標準 v1.2》與《PostgreSQL 資料庫權限與管理標準 v1.0》（Windows Server / IIS / HttpPlatformHandler / Waitress 或 Uvicorn / WinSW / AD 登入與 Windows SSO / 離線 Release 包），可通過「IIS 部署助手」的規範檢查並打包。只要是在建立新的公司內部 Python 系統（Flask、Django、FastAPI）、替既有專案補上部署所需的架構、新增 deployment.json / requirements.lock / /health / /version、處理 APP_CONFIG_FILE 或 shared 目錄的寫入路徑、AUTH_MODE / AD 帳密 / /auth/sso、把排程或 Worker 改成 WinSW 服務、設計 PostgreSQL 的 schema／角色／Migration 權限（owner、rw、ro、migrator、SET ROLE），或使用者提到「部署規範」「部署標準」「IIS 部署」「部署助手檢查沒過」「要能打包部署」時，都要使用這個 skill——即使使用者沒有明說規範的名稱。
---

# Python 部署標準 v1.2：讓專案具備必要架構

這個 skill 的目的：讓一個 Python 專案**從一開始就長成可以部署的樣子**。部門用「IIS 部署助手」檢查專案是否符合規範，符合才能打包部署；不符合會被擋下。照這裡做，專案就能通過檢查。

規範背後只有四個目標，遇到這裡沒寫到的情況時，用它們判斷：

- **可重建**：靠版本包與鎖定的套件清單就能在無外網的伺服器重建環境。
- **可追蹤**：看得出線上跑的是哪一版、從哪裡來。
- **可回滾**：程式切回舊版時，設定與資料不會跟著不見。
- **可驗收**：健康狀態、版本、登入、權限、排程都有明確的檢查方式。

## 正式環境長什麼樣子（先理解，再寫程式）

```text
D:\WebServices\<系統名稱>\
├─ releases\<版本>\app\   程式（每版一份，執行時視為唯讀）
│               \.venv\   該版的 Python 環境（在伺服器上現地建立）
├─ current\               目錄連結，指向目前上線的版本；IIS 與背景服務都從這裡執行
└─ shared\                換版本時不動：config\.env、logs\、data\、upload\、backup\
```

- 網站：`https://<主機>/<系統名稱>/` → IIS 子應用程式 → HttpPlatformHandler → `python -m waitress`（WSGI）或 `python -m uvicorn`（ASGI）。
- 背景工作：WinSW 包成 Windows 服務，獨立於網站程序。
- `web.config`、WinSW 設定、安裝／升級／回滾腳本都由部署助手產生，**專案不要自己寫**。

因為程式目錄每版都是新的、而且唯讀，所以「設定檔在哪、log 和資料寫去哪」都要由環境變數告訴程式——這是大多數既有專案不符合規範的主因。

## 工作流程

### 1. 先弄清楚這個專案是哪一種

用規範 §20 的幾個問題判斷（能從程式碼看出來就不要問使用者）：

| 問題 | 影響 |
|---|---|
| 網站／API，還是背景服務，或兩者都有？ | `type`：`web`、`services`、`web+services` |
| 框架是 WSGI（Flask、Django）還是 ASGI（FastAPI、Starlette）？ | Waitress 或 Uvicorn |
| 有沒有使用者登入？ | 有 → 必須同時提供 AD 帳密登入與 Windows SSO |
| 有沒有排程、長時間任務、或沒人使用也要跑的工作？ | 有 → 拆成 WinSW 背景服務，不放在網站程序 |
| 有沒有資料庫 Migration？ | 有 → 每一版要宣告與舊版是否相容 |
| 有沒有資料庫（含開發用的 SQLite）？ | 有 → 正式環境一律 PostgreSQL：宣告 `database`（資料庫、Schema、角色），照 §7 的角色模型寫 Migration |

### 2. 準備專案根目錄的檔案

| 檔案 | 重點 |
|---|---|
| `deployment.json` | 專案宣告。欄位與範例見 `references/deployment-json.md` |
| `CHANGELOG.md` | 每個版本一節；必須出現 `deployment.json` 的 `version` |
| `requirements.lock` | 所有套件（含間接相依）以 `==` 固定；只能有英文字元；不可有 `-e`、本機路徑、git 網址。建議附 `--hash` |
| `.env.example` | 列出所有設定 key（開發者自己的 `.env` 有的項目這裡都要有），不含真實密碼；要有 `AUTH_MODE`、`AUTH_SSO_ENABLED` |
| `.gitignore` | 排除 `.env`（開發者自己的設定，可能含開發用密碼）、`.venv`、`node_modules`、執行時產生的資料 |
| 進入點 | 例如 `app.py` 匯出 `create_app`；WSGI 專案的 lock 要有 `waitress`，ASGI 要有 `uvicorn` |
| `tests/` | pytest 可執行（建議） |
| 前端（有時） | `package.json` 寫 `"engines": {"node": ">=22"}`（工具依它檢查 Node.js 版本）、提交 `package-lock.json`；使用內部 npm 套件庫時在前端資料夾放 `.npmrc` 寫 `registry=…` |

`requirements.lock` 要在與部署機相同的 Python 版本、Windows 上產生（`pip-compile --generate-hashes -o requirements.lock requirements.txt`，或用部署助手的「產生 requirements.lock」）。在 Linux 或 macOS 上產生會漏掉 Windows 才需要的套件（例如 `colorama`），所以若你不在 Windows 上，請明確告訴使用者這個檔案需要在 Windows 重新產生，不要假裝它已經正確。

### 3. 讓程式遵守固定的環境變數

部署助手會在正式環境注入下列變數；程式讀它們，開發機沒設定時才用自己的預設值：

| 變數 | 正式環境的值 | 程式要做的事 |
|---|---|---|
| `APP_CONFIG_FILE` | `shared\config\.env` | 從這個路徑載入設定；未設定時才讀專案資料夾的 `.env` |
| `APP_LOG_DIR` | `shared\logs` | 檔案 log 寫這裡 |
| `APP_DATA_DIR` | `shared\data` | 資料檔、狀態檔、匯出、本機資料庫檔 |
| `APP_UPLOAD_DIR` | `shared\upload` | 使用者上傳的檔案 |
| `APP_TEMP_DIR` | `shared\data\tmp` | 暫存 |
| `APP_VERSION` | 這一版的版本號 | `/version` 回傳它 |
| `URL_PREFIX` | `/<系統名稱>` | 整個應用程式掛在這個子路徑下 |

開發者在開發機上照樣用專案資料夾的 `.env` 執行程式，不需要設定這些變數；它們只在正式環境與檢查工具中出現。

平台自己的其他設定檔（例如設備清單的 `settings.json`）怎麼設計由平台決定，規範不管，只要路徑不寫死：把路徑做成 `.env` 的一個設定項目，正式環境的檔案放在 `shared\config\`（程式會改寫的放 `shared\data\`）。寫法見 `references/code-patterns.md` 第 1 節。

執行期間**不可以**在程式目錄產生或修改任何檔案（包含開發用的 SQLite、快取、`instance/`）。檢查工具會實際啟動程式，比對啟動前後的程式目錄，有變動就不通過。

可直接照抄的程式碼在 `references/code-patterns.md`；完整可執行的範例在 `assets/sample-app/`（它通過了部署助手的全部檢查，新專案可以直接複製後改名）。

### 4. 網站必備的端點與行為

- `GET /health` → HTTP 200、`{"status": "ok"}`。只回基本狀態，不要放資料庫連線、主機、設定值。
- `GET /version` → `{"application": "<系統名稱>", "version": "<APP_VERSION>"}`。
- 掛在子路徑下：所有連結、靜態檔、轉址、Session Cookie 的 Path 都要帶 `URL_PREFIX`。用框架產生網址（`url_for`、`reverse`、`request.url_for`），不要寫死以 `/` 開頭的路徑。
- 正式環境不可使用 `--reload`。

### 5. 登入（有使用者登入的網站）

兩個入口、同一套 Session 與權限：

- **AD 帳密**：`POST /api/auth/login`。
- **Windows SSO**（必要）：`GET /auth/sso`，由 IIS 對這個路徑做 Windows 驗證，程式從 `X-IIS-WindowsAuthToken` 標頭拿到的是**權杖 Handle**，要用 Windows API 解析出帳號，並且每次都 `CloseHandle`。不可把標頭文字直接當帳號。
- `GET /api/auth/me`：未登入時回 401（或不含個資）。
- `POST /api/auth/logout`：只接受 POST，有 CSRF 防護，登出後暫停自動 SSO。
- 設定：`AUTH_MODE`（`off`／`mock`／`ad`）與 `AUTH_SSO_ENABLED`。`APP_ENV=production` 時，`AUTH_MODE` 不是 `ad` 就拒絕啟動。`AUTH_SSO_ENABLED=false` 時 `/auth/sso` 不可登入。
- **AD 登入成功不等於開通**：平台自己記錄哪些帳號已開通、是什麼角色，每個業務 API 在後端檢查。
- Session Cookie：`HttpOnly`、`SameSite`，`Secure` 可由設定開啟。
- 不要把密碼寫進 log。
- 員工資料表 `base.kh_ad_employees` 只讀不寫。要查人員清單、選人、做角色權限或名單設定時，照 `platform-people-access` skill（欄位對應、查詢寫法、名單表、選人元件、DBA 授權）。
- AD 連線：部門預設**不強制**驗證憑證（可用 `ldap://`）；環境允許時建議用 `ldaps://` 並驗證憑證。把 CA 檔路徑做成設定，之後要開啟才不用改程式。

### 6. 背景工作

排程、長時間任務、設備採集這類工作不放在網站程序裡，因為 IIS 回收 AppPool 時會被中斷。做成獨立的常駐程式（一個 `while` 迴圈，不是跑一次就結束），在 `deployment.json` 的 `services` 宣告，由 WinSW 管理。它要：

- 啟動的程式碼放在 `main()`，以 `if __name__ == "__main__": main()` 呼叫，載入模組時不做任何工作。
- 連不到資料庫、設備或外部系統時，記錄錯誤後稍等再重試，不要直接結束程式（直接結束會讓 WinSW 不斷重啟，也會讓檢查工具誤判）。服務一啟動就必須連正式設備、在開發機無法執行時，在服務宣告加 `"selfTest": "load"`。
- 收到停止訊號時在停止逾時內結束。
- 把「最後成功時間」與版本寫到 `APP_DATA_DIR` 的狀態檔（或提供查詢端點）。
- 排程類的工作要能防止重複執行，並在停機恢復後補跑或告警。

不要使用 NSSM、`startup.bat`、開機啟動捷徑，也不要用工作排程器啟動長駐程式。

### 7. 資料庫 Migration

升級時會**先更新資料庫、再切換程式版本**，所以更新完到切換完成之間，舊版程式還在新的資料庫結構上執行。因此：

- 優先設計成向後相容（新增欄位／資料表、不刪不改既有欄位）。
- 在 `deployment.json` 的 `migrations.compatibility` 宣告 `backward-compatible`、`restore-plan`（不相容，並在 `notes` 寫還原計畫）或 `none`。
- Migration 指令要能重複執行；連線帳號從設定的 `DATABASE_URL` 取得，若環境變數 `MIGRATION_DATABASE_URL` 存在就改用它（部署時由工具提供 migration 帳號）。

#### PostgreSQL 的角色與權限（《PostgreSQL 資料庫權限與管理標準 v1.0》）

每個系統有自己的 Schema 與五個角色，名稱由 `database.prefix` 推得（見 `references/deployment-json.md`）：

| 角色 | 可登入 | 用途 |
|---|---|---|
| `<prefix>_owner` | 否 | 擁有 Schema 與所有表 |
| `<prefix>_rw`／`<prefix>_ro` | 否 | 讀寫／唯讀群組；權限只授予群組 |
| `<prefix>_migrator` | 是 | 部署時跑 Migration：先 `SET ROLE <prefix>_owner` 再建表 |
| `<prefix>_svc` | 是 | 網站與背景服務；`.env` 的 `DATABASE_URL` 用它 |

寫程式時要做到：

- 網站與服務**不可**用 `postgres`、owner 或 migrator 連線。
- Migration 連線後、建表前，在**同一條連線**執行 `SET ROLE <owner>`（角色名稱從設定 `DATABASE_OWNER_ROLE` 讀）。沒有這一步，新表的 owner 會是 migrator、預設權限不會套用，上線後服務帳號會遇到 `permission denied`。部署助手在切換版本前會實際檢查，不符合就停止部署。
- 程式與 Migration 裡**不寫** `CREATE ROLE`、`ALTER ROLE`、密碼、`CREATE SCHEMA`、`... OWNER TO`、`REVOKE ... ON DATABASE`、`REASSIGN OWNED`、`DROP OWNED`——這些由 DBA 執行，部署助手會依宣告產生建置腳本給 DBA（`deploy-assistant db-scripts`）。
- 若要 `GRANT`，只授予本系統的 `_rw`／`_ro` 群組，不給 `ALL`、`TRUNCATE`、`CREATE`，不給登入帳號或 `PUBLIC`。通常不需要：DBA 設好預設權限後，owner 建立的新表會自動授權。
- 只建立或修改本系統 Schema 的物件。共用資料（例如 `base` Schema）只讀；要讀哪些表列在 `database.sharedReads`；確實要寫入時列在 `sharedWrites` 並由使用者填上 DBA 的核准紀錄（不要替使用者編造）。
- 新表的流水號用 `GENERATED ALWAYS AS IDENTITY`，不用 `SERIAL`。
- 程式碼一律寫完整名稱（`<schema>.<table>`）或依賴服務帳號的 `search_path`；不要改整個資料庫的 `search_path`。

### 8. 完成前自我檢查

執行 skill 附的檢查腳本，它涵蓋部署助手的大部分靜態規則：

```bash
python <skill 路徑>/scripts/self_check.py <專案資料夾>
```

把所有「必須修正」處理完。腳本沒有實際啟動程式，所以另外自己確認：以 `URL_PREFIX=/<系統名稱>` 啟動後，`/<系統名稱>/health` 與 `/<系統名稱>/version` 正常，且程式目錄沒有多出檔案。規則的完整清單與判定方式在 `references/rules.md`。

最後由使用者在 Windows 上用部署助手做完整檢查與打包——那一步會真的離線安裝套件並啟動程式，是最終依據。

## 修改既有專案時

- 先跑 `self_check.py` 取得差距清單，再逐項修，不要一次重寫。
- 保留開發機原本的行為：環境變數沒設定時維持原來的預設位置，開發者的習慣不受影響。
- 既有系統暫時做不到的項目，可以在 `deployment.json` 的 `exceptions` 登記（理由、風險、負責人、改善計畫、期限）。這是給使用者決定的事：列出你建議登記例外的項目和原因，由使用者確認，不要自行替他們填負責人或期限。
- 舊的部署腳本（NSSM、工作排程器、手寫的 `web.config`）不再需要；提醒使用者可以移除，但不要沒問就刪。

## 不要做的事

- 不要寫 `web.config`、安裝腳本或 WinSW 設定——由部署助手產生，專案自帶的會被忽略。
- 不要把 `.env`、`.venv`、資料庫檔、`logs`、`node_modules`、密鑰放進 `deployment.json` 的 `include` 範圍。
- 不要讓網站或服務用 owner／postgres 帳號連線資料庫，也不要在程式裡建立帳號或改授權來「自己修好」權限問題——權限不足時列出需要 DBA 執行的 SQL，交給使用者。
- 不要為了通過檢查而寫假的端點或假的宣告（例如宣告 Migration 相容但實際會刪欄位）。宣告是給部署的人判斷風險用的，寫錯會讓回滾出事。

## 參考檔案

- `references/deployment-json.md`：`deployment.json` 每個欄位與三種類型的完整範例。寫或改宣告檔時讀。
- `references/code-patterns.md`：Flask、FastAPI、Django 的設定載入、子路徑、`/health`、`/version`、登入、SSO 權杖、背景服務的程式碼。寫程式時讀對應的段落。
- `references/rules.md`：部署助手的全部規則、等級與判定方式。使用者貼上檢查結果（例如 `PATH-01`）要你修時讀。
- `assets/sample-app/`：通過全部檢查的最小範例（Flask 網站＋一個背景服務）。新專案的起點。
