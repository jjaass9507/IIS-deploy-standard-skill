# python-iis-deploy-standard（部署規範 skill）

給 AI Agent 用的 skill：讓 Python 專案從一開始就符合部門《Python 程式與平台部署標準 v1.2》，可以通過 [IIS 部署助手](https://github.com/jjaass9507/IIS-deploy-assistant) 的規範檢查並打包部署。

開新專案，或請 Agent 修改既有專案時提供給它，Agent 會照規範建立必要的架構：

- 專案宣告檔 `deployment.json`、`CHANGELOG.md`、`requirements.lock`、`.env.example`、`.gitignore`
- 設定檔與寫入路徑改由固定的環境變數提供（`APP_CONFIG_FILE`、`APP_LOG_DIR`、`APP_DATA_DIR`…），程式目錄維持唯讀
- `/health`、`/version`，以及掛在 IIS 子路徑（`/<系統名稱>`）下的網址處理
- AD 帳密登入與 Windows SSO（`/auth/sso`、權杖解析、`CloseHandle`）、Session 與 CSRF
- 背景工作改成由 WinSW 管理的常駐服務
- 資料庫 Migration 的相容性宣告

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
- skill 已反映部門的決定：有使用者登入的網站一律要有 Windows SSO；AD 連線的憑證驗證為建議、不強制；升級時先更新資料庫再切換版本；固定的環境變數名稱。這些與規範 v1.2 原文不完全相同，規範原文待部門更新。

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

## 更新

規範或部署助手的規則改變時，同步更新這裡與 [IIS-deploy-assistant](https://github.com/jjaass9507/IIS-deploy-assistant) 裡的同一份 skill（`skills/python-iis-deploy-standard`）。推送到 `main` 後會自動：

1. 用 `self_check.py` 檢查範例專案，並執行範例專案的測試。
2. 確認 `SKILL.md` 的格式。
3. 打包並發佈新的 Release。
