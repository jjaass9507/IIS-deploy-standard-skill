---
name: python-job-packaging
description: 「排程打包」：把 Python 批次程式（跑一次就結束、定時執行、常連 SQL Server／Oracle）用 Nuitka --mode=standalone 編譯成 exe、打包成含 SHA256 的離線 zip，在不裝 Python、不連外網的 Windows Server 上以 SYSTEM 帳號跑「工作排程器」的完整標準作法：<PREFIX>_ 環境變數 + .env（protect_env 鎖權限）、selfcheck／selfcheck --db／dryrun／run／--version、C:\ProgramData\<App>\logs 日誌與 0/1/2 結束碼、IgnoreNew 與執行上限、build_nuitka.ps1／preflight.ps1／register_task.ps1、交付文件與上線檢核表。只要使用者說「排程打包」，或要把 Python 程式／腳本做成 Windows 排程、Task Scheduler、編譯成 exe 給沒有 Python 的主機、用 Nuitka 打包、離線部署批次程式、處理 build_nuitka.ps1 或 register_task.ps1、Nuitka 編譯版 ModuleNotFoundError、工作排程 LastTaskResult 0x1／0x2／0x8007052E、.ps1 中文亂碼、requirements cp950 UnicodeDecodeError、Proxy 407 下 pip／Nuitka 下載失敗時，都要使用這個 skill——即使使用者沒有說出規範名稱。不適用：放在 IIS 上的網站與其常駐背景服務（WinSW），那些用 python-iis-deploy-standard。
---

# 排程打包：Python 批次程式 → Nuitka exe → Windows 工作排程

這個 skill 讓一支 Python 批次程式**照部門標準**上線到 Windows Server：

```
Nuitka 編譯成 exe（standalone 資料夾）→ 打包成離線 zip（含 SHA256）
→ 目標主機解壓、填 .env、protect_env 鎖權限 → preflight、dryrun → 以 SYSTEM 跑工作排程器
```

完整規範在 `references/standard.md`（文件編號 FAC-JOB-STD-001）。本檔是 Agent 的作業流程；細節、參數表與 FAQ 以規範為準。

## 先判斷：是不是這個 skill 的範圍

| 情況 | 用哪個 |
|---|---|
| 定時跑一次就結束的批次程式（擷取、同步、計算、報表），在 Windows Server 用工作排程器觸發 | **本 skill** |
| 目標主機沒有 Python、不能連外網，要把程式編成 exe 帶過去 | **本 skill** |
| 放在 IIS 上的網站（Flask／FastAPI／Django），或網站附帶的常駐背景服務 | `python-iis-deploy-standard`（WinSW，不用工作排程器） |
| 需要一直常駐、不能中斷的程式 | 不適合工作排程器；與使用者討論改成服務 |

## 不可違反的原則（規範 §1）

1. **目標主機不裝 Python**：Nuitka `--mode=standalone`，**不用 onefile**（排程頻繁啟動時每次解壓，慢且易被防毒攔截）。
2. **先唯讀、後寫入**：必備 `selfcheck`、`selfcheck --db`、`dryrun`（唯讀、輸出 CSV），上線前一定先跑。
3. **密碼不進版控、不進命令列、不進聊天**：只放 `.env`（`protect_env.ps1` 鎖權限），PowerShell 用 `Read-Host -AsSecureString`。使用者貼來的錯誤訊息若含密碼，提醒他遮掉並更換。
4. **設定與程式分離**：所有設定是 `<PREFIX>_` 環境變數；`.env` 只接受該前綴；**已設定的環境變數優先於 `.env`**。
5. **可回滾**：交付文件寫明回滾步驟（停用排程 + 切回舊做法），5 分鐘內完成。
6. **不寫死外部元件版本**：ODBC Driver、Python、C 編譯器都自動偵測。
7. **同一份資料只能有一個寫入者**：上線後開發主機不得再 `run`；舊程式以設定排除同一批資料。
8. **錯誤不能靜默**：每個失敗都要有 `ERROR` 行（含 traceback）並反映在結束碼 `0` 成功／`1` 部分失敗／`2` 整輪失敗。

## 工作流程

### 1. 收集專案資訊（能從程式碼看出來就不要問）

| 項目 | 例 | 用途 |
|---|---|---|
| `<app>` 套件名（小寫底線） | `meter_sync` | 套件、exe、安裝目錄 `D:\Jobs\<app>` |
| `<App>`（PascalCase） | `MeterSync` | `C:\ProgramData\<App>\logs`、預設排程名 |
| `<PREFIX>`（大寫） | `METER` | 環境變數 `METER_SQL_SERVER`… |
| 資料庫 | SQL Server／Oracle／兩者／無 | 決定範本內容與隱藏相依 |
| 排程頻率、下游何時讀取 | 每 5 分鐘；下游第 3 分讀 | `register_task.ps1` 預設值、執行上限、時間預算 |
| 舊做法與回滾方式 | 原本 C# 排程寫同一張表 | 交付文件 §10 回滾 |

### 2. 產生骨架

```bash
python <skill>/scripts/scaffold.py <專案資料夾> --app meter_sync --db sqlserver --description "電表資料同步"
```

- 選項：`--app-title`、`--prefix`、`--task-name`、`--company`（預設 ASE）、`--db sqlserver,oracle|oracle|none`。
- **既有專案**：加 `--into-existing`，只新增不存在的檔案、絕不覆寫；列出被略過的檔案後，逐一與 `assets/template/` 比對再合併。既有的業務程式搬進 `job.py` 的 `collect()`（唯讀）與 `write()`（寫入），不要整個重寫；動手前先跟使用者確認搬移方式。
- 產生的檔案、各自要改什麼，見規範 §4 表格。範本整理自實際上線的 pms_ingest（Kepware(Oracle) → PMS），已驗證過的寫法不要「簡化」掉，例如：`tcp:` 前綴與「埠號要用逗號」、ODBC Driver 依版本數字挑選、舊版驅動不送 `Encrypt`、密碼的 `}` 跳脫、oracledb 的隱藏相依清單、Proxy 一律用環境變數。

### 3. 完成 `TODO(專案)`

用搜尋 `TODO(專案)` 逐項處理，常見的有：

| 檔案 | 要做的事 |
|---|---|
| `<app>/job.py` | 實作 `collect()`（只讀）與 `_write_one()`／`write()`（參數化 SQL；表名欄位名只能來自白名單；單筆失敗記 ERROR 並計數，其餘繼續） |
| `<app>/config.py`、`.env.example` | 本程式的設定項目；`.env.example` 每一項都要有中文註解說明值從哪裡取得、不放真實密碼 |
| `<app>/selfcheck.py` | `REQUIRED_PACKAGES`、`REQUIRED_SQL_TABLES`／`REQUIRED_ORA_TABLES`、`_check_project()` |
| `deploy/build_nuitka.ps1` | 額外第三方套件加入 `$IncludePackages`／`$IncludeModules`／`$VerifyPackages` |
| `deploy/register_task.ps1` | `-IntervalMinutes` 預設值；執行上限必須小於間隔 |
| `tests/` | 為 `collect()`／`write()` 補單元測試：只用標準函式庫、以假物件模擬資料庫，不連線 |
| `sql/` | DDL、預建資料、授權範本，每句可獨立執行（DBeaver） |
| `deploy/README.md`、`deploy/DEV_TEST.md` | 依規範 §14 填入專案內容，**尤其回滾步驟的具體 SQL／設定** |

有診斷需求（「讀不到資料」）或補跑需求時，依規範 §6.3 建議加診斷命令與 `run --cycle <時間>`。

### 4. 自我檢查

```bash
python -m unittest discover -s tests -t .
python <skill>/scripts/check_project.py <專案資料夾>            # 開發中：TODO 只算警告
python <skill>/scripts/check_project.py <專案資料夾> --strict   # 交付前：不得留下 TODO(專案)
```

`check_project.py` 是靜態檢查（結構、BOM、ASCII、子命令、`.gitignore`、`.env.example` 無密碼、standalone、IgnoreNew、執行上限、SYSTEM、交付文件章節、參考實作名稱殘留）。它**不能取代**實際執行：`selfcheck --db`、`dryrun`、編譯版驗證都要在 Windows 上做。

### 5. 交給使用者執行（Agent 通常不在 Windows 上）

依規範 §7 給使用者對應階段的指令，並說明每一步的預期結果：

| 階段 | 在哪裡 | 指令 | 通過條件 |
|---|---|---|---|
| 0 開發主機測試 | 開發主機 | `python -m <app> selfcheck --db`、`dryrun` | 全 OK；dryrun 最小範圍 → 全部，各 2～3 輪 `errors=0` |
| 1 建置 | 建置機 | `.\deploy\build_nuitka.ps1 -Proxy ... -ProxyUser ... -TrustPyPI` | 得到 zip 與 `.sha256` |
| 2 驗證編譯版 | 建置機 | `build\run_<app>.dist\<app>.exe --version／selfcheck --db／dryrun` | 與階段 0 相同（換編譯器／Python／Nuitka 版本時不可省略） |
| 3 安裝 | 目標主機（管理員） | 核對 SHA256、`Expand-Archive`、`Unblock-File`、ODBC、`.env`、`protect_env.ps1 -RunAs "SYSTEM"` | — |
| 4 上線前驗證 | 目標主機 | `.\deploy\preflight.ps1`、`app\<app>.exe dryrun` | 全 `[ OK ]`；dryrun 連續 2～3 輪正常 |
| 5 上線 | 目標主機 | `.\deploy\register_task.ps1 -RunAs "SYSTEM"` | 同時切換舊做法、開發主機停止 `run` |
| 6 第一小時 | 目標主機 | `Get-ScheduledTaskInfo`、`Get-Content ...\logs\<app>.log -Tail 20 -Wait` | `LastTaskResult=0`、`errors=0`、資料連續 |

最後附上規範 §11 檢核表，請使用者逐項打勾；Agent 不可替使用者勾選或填寫無法確認的項目（防火牆、帳號權限、時間同步、回滾演練）。

### 6. 排查問題

使用者貼來錯誤訊息時，先查 `references/standard.md` §13 FAQ（D 開發主機、B 建置機、T 目標主機、R 上線後），用編號回覆原因與處理方式。排查順序：**日誌最後一行摘要與 ERROR 行 → `selfcheck --db` → 診斷命令**。

FAQ 沒有的新問題：解決後把「現象／原因／處理」補進 `references/standard.md` §13 對應表格，並提醒使用者同步到專案的規範文件（例如 ASEJOBS repo 的 `PYTHON_JOB_PACKAGING_STANDARD.md`）。

## 撰寫規定速查（規範 §5）

- `*.ps1`：**UTF-8 with BOM**、相容 Windows PowerShell 5.1：`python -c "..."` 內只用單引號；呼叫可能寫 stderr 的外部程式時暫時把 `$ErrorActionPreference` 改 `Continue`；格式化用 `Write-Host ("{0}" -f $x)`；密碼用 `Read-Host -AsSecureString`，要給子程序時用環境變數並在 `finally` 還原。
- `requirements*.txt`：**只用 ASCII**（註解寫英文）。`requirements-build.txt` 固定 `nuitka>=4.2,<5`。
- `*.py`、`*.md`、`*.sql`：UTF-8。
- Python 3.11～3.13 64 位元（3.12 優先）；單元測試只用標準函式庫。
- 新套件的隱藏相依：先編譯，用編譯版實際跑 `selfcheck --db` 與 dryrun，缺什麼補什麼；不要列入 `array`、`sys`、`time` 等內建模組。

## 檔案

```text
python-job-packaging/
├─ SKILL.md                    本檔
├─ references/standard.md      完整規範（§1～§14，含 FAQ 與檢核表）
├─ scripts/scaffold.py         由範本產生專案骨架
├─ scripts/check_project.py    靜態檢查
└─ assets/template/            專案範本（{{app}} 等佔位符與 {{#sqlserver}}／{{#oracle}} 條件區塊）
```
