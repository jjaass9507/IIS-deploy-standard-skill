# python-iis-deploy-standard（部署規範 skill）

給 AI Agent 用的 skill：讓 Python 專案從一開始就符合部門《Python 程式與平台部署標準 v1.2》與《PostgreSQL 資料庫權限與管理標準 v1.0》，可以通過 [IIS 部署助手](https://github.com/jjaass9507/IIS-deploy-assistant) 的規範檢查並打包部署。

開新專案，或請 Agent 修改既有專案時提供給它，Agent 會照規範建立必要的架構：

- 專案宣告檔 `deployment.json`、`CHANGELOG.md`、`requirements.lock`、`.env.example`、`.gitignore`
- 設定檔與寫入路徑改由固定的環境變數提供（`APP_CONFIG_FILE`、`APP_LOG_DIR`、`APP_DATA_DIR`…），程式目錄維持唯讀
- `/health`、`/version`，以及掛在 IIS 子路徑（`/<系統名稱>`）下的網址處理
- AD 帳密登入與 Windows SSO（`/auth/sso`、權杖解析、`CloseHandle`）、Session 與 CSRF
- 背景工作改成由 WinSW 管理的常駐服務
- 資料庫 Migration 的相容性宣告
- PostgreSQL 的 `database` 宣告（資料庫、Schema、owner／rw／ro／migrator／服務帳號）；Migration 先 `SET ROLE` 成 owner、程式不建立帳號或改授權（開發時用 SQLite 也要宣告，正式環境一律 PostgreSQL）
- 每張資料表與每個欄位都要有中文註解（Migration 裡的 `COMMENT ON`，規則 `DB-08`）

完成後 Agent 會用附的檢查腳本自我檢查，再請你在 Windows 上用 IIS 部署助手做最終檢查。

---

## 內容

```text
python-iis-deploy-standard/
├─ SKILL.md                      主要說明（Agent 先讀這份）
├─ references/
│  ├─ code-patterns.md           Flask、FastAPI、Django 可以照抄的程式碼
│  ├─ deployment-json.md         deployment.json 每個欄位與三種範例
│  └─ rules.md                   IIS 部署助手的全部檢查規則（貼檢查結果給 Agent 時它會查這份）
├─ scripts/
│  └─ self_check.py              自我檢查腳本（只用 Python 標準函式庫）
└─ assets/
   └─ sample-app/                通過全部檢查的範例專案（Flask 網站＋一個背景服務）
```

---

## 安裝

到 [Releases](https://github.com/jjaass9507/IIS-deploy-standard-skill/releases) 下載最新的 `python-iis-deploy-standard.skill`（內容就是 zip，也提供同樣內容的 `.zip`）。或直接 `git clone` 這個 repo，使用 `python-iis-deploy-standard` 資料夾。

### Claude Code

二擇一：

- **只給某個專案用（建議）**：把 `python-iis-deploy-standard` 資料夾放到該專案的 `.claude/skills/` 底下並提交，之後所有在這個專案工作的人與 Agent 都會用到。

  ```text
  <你的專案>/.claude/skills/python-iis-deploy-standard/SKILL.md
  ```

- **自己所有專案都用**：放到使用者資料夾。

  ```text
  Windows：%USERPROFILE%\.claude\skills\python-iis-deploy-standard\SKILL.md
  macOS／Linux：~/.claude/skills/python-iis-deploy-standard/SKILL.md
  ```

放好後重新開啟 Claude Code。提到部署規範、IIS 部署、`deployment.json`、部署助手檢查沒過等內容時，Agent 會自動使用這個 skill；也可以直接說「依部署規範 skill 處理」。

### claude.ai

在設定的 Skills（技能）頁面上傳下載的 `.skill` 或 `.zip` 檔。組織帳號若沒有上傳選項，請組織管理員代為加入。

### 其他 AI 工具

沒有 skill 機制的工具（例如只讀 `AGENTS.md`、`.github/copilot-instructions.md` 的工具），把整個 `python-iis-deploy-standard` 資料夾放進專案，並在該工具的指示檔中寫：

```text
處理部署、IIS、deployment.json 相關工作前，先閱讀 python-iis-deploy-standard/SKILL.md 並照做。
```

---

## 使用方式

### 開新專案

> 用 Flask 做一個設備保養登記系統，系統名稱 equipment-maintenance，要有 AD 登入，每天早上 8 點寄到期提醒信。請依部署規範 skill 建好架構。

Agent 會從 `assets/sample-app` 的寫法開始，建立宣告檔、設定載入、`/health`、`/version`、登入與 SSO，並把每天寄信做成背景服務。

### 讓既有專案符合規範

> 這個專案要用 IIS 部署助手部署，請依部署規範 skill 檢查並修改。先跑 self_check 列出差距，修改前先跟我確認。

Agent 會先執行自我檢查取得差距清單，再逐項修改，保留開發機原本的使用方式。暫時做不到的項目，它會列出建議登記為例外的理由，由你決定。

### 修正部署助手檢查出的問題

在部署助手的結果畫面按「複製報告」，貼給 Agent：

> 部署助手檢查結果如下，請依部署規範 skill 修正：
> （貼上報告）

Agent 會用規則編號（例如 `PATH-01`、`SSO-02`）在 `references/rules.md` 找原因與改法。

### 只執行自我檢查

不透過 Agent 也可以直接執行（需要 Python 3.8 以上）：

```bash
python python-iis-deploy-standard/scripts/self_check.py <專案資料夾>
```

它檢查部署助手的大部分靜態規則，不會啟動程式。結束碼 0 表示沒有必須處理的項目。

---

## 注意

- **自我檢查不能取代部署助手**：它不會實際安裝套件、啟動網站、送出請求。最終以 IIS 部署助手在 Windows 上的完整檢查為準。
- **`requirements.lock` 要在 Windows、與部署機相同的 Python 版本上產生**。在 Linux 或 macOS 產生的版本會漏掉 Windows 才需要的套件；Agent 不在 Windows 上時會提醒你重新產生。
- **例外與人工確認由人決定**：skill 要求 Agent 不可以替你填寫負責人、期限或確認人。
- skill 已反映部門的決定：有使用者登入的網站一律要有 Windows SSO；AD 連線的憑證驗證為建議、不強制；升級時先更新資料庫再切換版本；固定的環境變數名稱。資料表與欄位要有中文註解（`DB-08`，目前為警告）。這些與規範 v1.2、PostgreSQL 標準 v1.0 原文不完全相同，規範原文待部門更新。

---

# internal-agent-integration（內部 Agent 串接 skill）

這個 repo 另外附一個獨立的 skill：**串接公司內部 Agent 平台的完整作法**，整理自「工程進度簡報 AI 解析平台」實際上線的程式。

內部 Agent 平台長得像 OpenAI API（`/v1/chat/completions`、`/v1/files`），但行為不相容：`temperature`、`response_format`、`tools` 靜默忽略，沒有對話記憶，HTTP 200 可能是空回應、429 可能是參數錯、500 可能只是路由不存在，附件只認一種寫法，輸出上限約 1,825 tokens，而且會自信地捏造。這個 skill 讓 Agent 在新專案裡照已驗證的方式串接，不必再踩一次這些坑：

- 防禦式 client（`scripts/agent_client.py`，只依賴 `requests`）：上傳與索引等待、唯一有效的附件形狀、把不可信的狀態碼翻成明確例外、可重試／不可重試分開、TLS（內部 CA）
- 結構化輸出：prompt 約束＋容錯 JSON 抽取（`scripts/jsonx.py`）＋一次嚴格重試＋降級
- 單則自足 prompt、錨點引用、分批與本地合併
- 圖片判讀：正規化、標籤畫進像素並查核（`scripts/label_banner.py`）
- 來源比對（grounding）、自我更正一輪、篩掉來源不存在的結論
- 呼叫層／工作層兩層重試、呼叫紀錄、DEMO 模式
- 測試用假平台（`assets/tests/`）與上線前 `scripts/selftest.py`

```text
internal-agent-integration/
├─ SKILL.md                      主要說明（Agent 先讀這份）
├─ references/
│  ├─ platform-quirks.md         每個平台怪異行為的現象、判斷與處理
│  ├─ patterns.md                prompt、JSON 呼叫包裝、分批、來源比對、自我更正、工作層的程式碼骨架
│  └─ config.md                  .env.example 片段、設定讀取、與部署規範一起用時的注意事項
├─ scripts/
│  ├─ agent_client.py            防禦式 client（直接複製進專案）
│  ├─ jsonx.py                   容錯 JSON 抽取
│  ├─ label_banner.py            圖片正規化與標籤橫幅（Pillow）
│  └─ selftest.py                對真實平台的上線前檢查
└─ assets/tests/
   ├─ fake_platform.py           重現平台行為的假 Session
   └─ test_agent_client.py       範例測試（不需要 API key）
```

安裝方式與上面相同：下載 Release 裡的 `internal-agent-integration.skill`（或 `.zip`），或把 `internal-agent-integration` 資料夾放到 `.claude/skills/`。兩個 skill 可以一起用——串接 Agent 的系統要部署到 IIS 時，設定與寫入路徑照部署規範 skill，Agent 呼叫照這一份。

使用範例：

> 這個 Flask 專案要串接內部 Agent，把上傳的 Excel 摘要成 JSON。請依 internal-agent-integration skill 實作。

> Agent 呼叫一直回 200 但內容是空的／回 429／回 500 No static resource，請依 internal-agent-integration skill 檢查。

部署到新環境後，先在伺服器上跑：

```bash
python internal-agent-integration/scripts/selftest.py 測試圖片.jpg
```

---

# python-job-packaging（排程打包 skill）

這個 repo 另外附一個獨立的 skill：**把 Python 批次程式打包成 Windows 排程上線的標準作法**（簡稱「排程打包」，規範文件 FAC-JOB-STD-001），整理自實際上線的 pms_ingest（Kepware(Oracle) → PMS）。

和部署規範 skill 的分界：

| 程式型態 | 用哪個 skill |
|---|---|
| 放在 IIS 上的網站，以及網站附帶的常駐背景服務（WinSW） | python-iis-deploy-standard |
| 定時跑一次就結束的批次程式，目標主機不裝 Python，用工作排程器觸發 | **python-job-packaging** |

做法重點：

- Nuitka `--mode=standalone` 編譯成 exe，`deploy/build_nuitka.ps1` 打包成含 SHA256 的離線 zip（Proxy、C 編譯器自動選擇、oracledb／pyodbc 隱藏相依都已處理）
- 設定用 `<PREFIX>_` 環境變數 + `.env`（環境變數優先），`protect_env.ps1` 鎖權限
- 程式必備 `selfcheck`／`selfcheck --db`／`dryrun`／`run`／`--version`；日誌在 `C:\ProgramData\<App>\logs\`，結束碼 0/1/2
- 工作排程器以 `SYSTEM` 執行（`register_task.ps1 -RunAs "SYSTEM"`），`IgnoreNew`、執行上限小於間隔
- 交付 `deploy/README.md`（含回滾步驟）與 `deploy/DEV_TEST.md`，依上線檢核表確認

```text
python-job-packaging/
├─ SKILL.md                      主要說明（Agent 先讀這份）
├─ references/
│  └─ standard.md                完整規範（原則、結構、流程、建置、安全、排程、檢核表、FAQ、交付文件範本）
├─ scripts/
│  ├─ scaffold.py                由範本產生新專案骨架（只用標準函式庫）
│  └─ check_project.py           靜態檢查專案是否符合規範（只用標準函式庫）
└─ assets/template/              專案範本：程式、單元測試、部署腳本、交付文件
```

安裝方式與上面相同：下載 Release 裡的 `python-job-packaging.skill`（或 `.zip`），或把 `python-job-packaging` 資料夾放到 `.claude/skills/`。

使用範例：

> 排程打包：寫一支每 15 分鐘把 Oracle 的電表讀值同步到 SQL Server 的程式，套件名稱 meter_sync。

> 這支 Python 腳本要排程打包上線到沒有 Python 的 Windows Server，先檢查差距，修改前先跟我確認。

> 編譯版在目標主機跑 selfcheck 出現 No module named 'xxx'，請依排程打包 skill 處理。

不透過 Agent 也可以直接使用（需要 Python 3.8 以上）：

```bash
python python-job-packaging/scripts/scaffold.py ./meter_sync --app meter_sync --db sqlserver,oracle --description "電表資料同步"
python python-job-packaging/scripts/check_project.py ./meter_sync            # 交付前加 --strict
```

產生的專案搜尋 `TODO(專案)` 逐項完成即可。`check_project.py` 只做靜態檢查；`selfcheck --db`、dryrun、編譯版驗證仍要在 Windows 上執行。

---

# platform-people-access（人員與權限 skill）

這個 repo 另外附一個獨立的 skill：**內部平台的人員與權限管理標準作法**，整理自 GMS 監控平台（gms-monitor-agent）實際上線的程式，選人元件與 power-bill-agent 同一規格。平台的登入與部署照部署規範 skill；這份管的是**登入之後「這個人是誰、能做什麼」**：

- 公司員工資料表 `base.kh_ad_employees` **只讀**：`sharedReads` 宣告、DBA 授權給 `<prefix>_rw` 群組、欄位名稱以設定對應（不寫死）
- 平台自己的名單表 `<prefix>_person`（工號 → 角色、可檢視／可操作範圍、主管），每次異動要理由並留不可變版本
- 權限每個請求在後端重算，拒絕一律 403；角色不從 AD 群組來
- 選人一律用員工選擇器（搜尋工號／姓名／部門，不讓人手打），儲存時姓名與 Email 以員工資料表為準；離職者不自動拔權限，只標示「查無此工號」
- 依直屬主管欄位預填兩層主管

```text
platform-people-access/
├─ SKILL.md                      主要說明（Agent 先讀這份）
├─ references/
│  ├─ data-model.md              員工表設定與授權、查詢 SQL、平台名單表 DDL、稽核
│  ├─ backend.md                 每請求權限計算、403 裝飾器、管理 API、儲存規則、通知收件者、FastAPI 寫法
│  └─ person-picker.md           選人元件規格與管理頁版面
├─ scripts/
│  ├─ employee_directory.py      員工表唯讀查詢（直接複製進專案，只依賴 SQLAlchemy）
│  └─ check_employee_table.py    部署後核對讀取權限與欄位對應，讀不到時印出給 DBA 的 GRANT
└─ assets/
   ├─ frontend/                  PersonPicker.jsx（React）、person-picker.js（原生 JS）、person-picker.css
   └─ tests/                     test_employee_directory.py（SQLite，不需公司資料庫）
```

安裝方式與上面相同：下載 Release 裡的 `platform-people-access.skill`（或 `.zip`），或把 `platform-people-access` 資料夾放到 `.claude/skills/`。

使用範例：

> 這個平台要加「人員與權限」頁：角色分檢視者、操作人員、系統管理員，依廠區限制可操作範圍，人員從員工資料表選。請依 platform-people-access skill 實作。

> 簽核設定要能指定簽核人名單，請照人員權限 skill 用選人元件從 kh_ad_employees 選人。

部署後在伺服器上用平台的服務帳號核對員工表：

```bash
python platform-people-access/scripts/check_employee_table.py --settings settings.json --search 王
```

---

## 更新

規範或部署助手的規則改變時，同步更新這裡與 [IIS-deploy-assistant](https://github.com/jjaass9507/IIS-deploy-assistant) 裡的同一份 skill（`skills/python-iis-deploy-standard`）。推送到 `main` 後會自動：

1. 用 `self_check.py` 檢查範例專案，並執行範例專案的測試；用排程打包範本產生各種資料庫組合的專案，跑單元測試與 `check_project.py`。
2. 確認 `SKILL.md` 的格式。
3. 打包並發佈新的 Release。
