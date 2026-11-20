# Python 排程程式打包與部署標準規範

| 項目 | 內容 |
|---|---|
| 文件編號 | FAC-JOB-STD-001 |
| 版本 | 1.1（2026-10-07） |
| 適用範圍 | 以 Python 撰寫、在 Windows Server 用「工作排程器」定時執行的批次程式（含連線 SQL Server／Oracle） |
| 參考實作 | 原始參考實作為 ASEJOBS repo 的 `python/`（pms_ingest）；本 skill 已整理成通用範本 `assets/template/`，以 `scripts/scaffold.py` 產生 |

> **簡稱**：本文件所述做法簡稱「**排程打包**」。凡新的 Python 排程程式要上線，一律依本規範：
> 用 Nuitka 編譯成 exe → 打包成離線 zip → 目標主機以 `.env` 設定、`SYSTEM` 帳號跑工作排程器。

---

## 目錄

1. [基本原則](#1-基本原則)
2. [名詞與佔位符](#2-名詞與佔位符)
3. [角色與機器](#3-角色與機器)
4. [新專案起手：從參考實作複製](#4-新專案起手從參考實作複製)
5. [專案結構規範](#5-專案結構規範)
6. [程式設計規範](#6-程式設計規範)
7. [標準作業流程](#7-標準作業流程)
8. [建置規範（Nuitka）](#8-建置規範nuitka)
9. [安全規範](#9-安全規範)
10. [排程規範](#10-排程規範)
11. [上線檢核表](#11-上線檢核表)
12. [維運：更新、回滾、移除](#12-維運更新回滾移除)
13. [常見問題排查（FAQ）](#13-常見問題排查faq)
14. [附錄：交付文件範本](#14-附錄交付文件範本)

---

## 1. 基本原則

| # | 原則 | 說明 |
|---|---|---|
| P1 | **目標主機不裝 Python** | 用 Nuitka 編譯成 exe（standalone 資料夾），目標主機只需 ODBC Driver 等系統元件 |
| P2 | **先唯讀、後寫入** | 每支程式必須提供 `selfcheck`（自我檢查）與 `dryrun`（唯讀試算），上線前一定先跑 |
| P3 | **密碼不進版控、不進命令列、不進聊天** | 密碼只放 `.env`（並鎖權限），需要輸入時以隱藏輸入詢問 |
| P4 | **設定與程式分離** | 同一個 exe，換 `.env` 即可在開發主機／目標主機執行 |
| P5 | **可回滾** | 上線前就寫好回滾步驟（停用排程 + 切回舊做法），並確認 5 分鐘內可完成 |
| P6 | **不寫死外部元件版本** | ODBC Driver、Python 版本、C 編譯器都要能自動偵測可用的版本 |
| P7 | **同一份資料只能有一個寫入者** | 新程式上線後，開發主機不得再正式寫入；舊程式必須以設定排除同一批資料 |
| P8 | **錯誤不能靜默** | 任何失敗都要在日誌留下 `ERROR` 行並反映在結束碼 |

## 2. 名詞與佔位符

本文件以下列佔位符表示各專案自己的名稱，使用時請替換：

| 佔位符 | 意義 | 範例 |
|---|---|---|
| `<app>` | Python 套件名稱（小寫、底線） | `pms_ingest` |
| `<App>` | 工作排程名稱、ProgramData 資料夾名稱 | `PmsIngest`、排程 `PMS_Ingest` |
| `<PREFIX>_` | 環境變數前綴（大寫） | `PMS_` |
| `<InstallDir>` | 目標主機安裝目錄 | `D:\Jobs\<app>` |
| `<proxy>` | 公司 Proxy `主機:埠` | 向網管確認 |

## 3. 角色與機器

| 機器 | 用途 | 網路 | 需要安裝 |
|---|---|---|---|
| **開發主機** | 寫程式、原始碼測試（selfcheck／dryrun） | 可連資料庫；外網經 Proxy | Python 3.11～3.13 64 位元、ODBC Driver 17/18 |
| **建置機** | 編譯 exe、打包 zip（可與開發主機同一台） | 經 Proxy 連外網（下載套件、編譯器） | 同上；C 編譯器可選（見 §8.3） |
| **目標主機** | 正式執行排程（Windows Server） | **不連外網**；只開必要的資料庫連接埠 | ODBC Driver for SQL Server 17 或 18（有用到時） |

| 角色 | 負責 |
|---|---|
| 開發者 | 程式、單元測試、開發主機測試、建置、提供部署包與交付文件 |
| 系統管理員 | 目標主機安裝、`.env` 設定、權限、排程建立 |
| 網路／資安 | 防火牆、Proxy、防毒排除 |
| DBA | 資料庫帳號與最小權限、資料表與預建資料 |

## 4. 新專案起手：用範本產生

1. 用 `scripts/scaffold.py` 產生骨架（範本整理自參考實作 pms_ingest，已去除業務邏輯）：

   ```bash
   python scripts/scaffold.py <專案資料夾> --app <app> --db sqlserver,oracle --description "<一句話說明>"
   ```

   | 產生的檔案 | 用途 | 需要修改（搜尋 `TODO(專案)`） |
   |---|---|---|
   | `<app>/envfile.py` | `.env` 載入 | 不用改 |
   | `<app>/odbc.py` | ODBC Driver 自動偵測（有 SQL Server 時） | 不用改 |
   | `<app>/config.py` | 設定讀取、連線字串 | 本程式自己的設定項目 |
   | `<app>/selfcheck.py` | 自我檢查 | 必要套件、必要資料表、專案特有檢查 |
   | `<app>/job.py` | 業務邏輯：`collect()` 唯讀、`write()` 寫入 | 實作兩者 |
   | `<app>/__main__.py` | CLI、日誌、結束碼 | 需要時加診斷命令、`run --cycle` |
   | `run_<app>.py` | Nuitka 入口 | 不用改 |
   | `deploy/build_nuitka.ps1` | 建置與打包 | 額外套件的 `$IncludePackages`／`$IncludeModules` |
   | `deploy/protect_env.ps1` | 鎖 `.env` 權限 | 不用改（預設路徑為腳本上一層） |
   | `deploy/preflight.ps1` | 上線前檢查 | 不用改（主機與埠從 `.env` 推得） |
   | `deploy/register_task.ps1` | 建立排程 | 預設頻率 |
   | `deploy/README.md`、`deploy/DEV_TEST.md` | 交付文件（§14） | 專案內容 |
   | `.env.example`、`.gitignore`、`requirements*.txt`、`sql/` | 設定範本與相依 | 內容 |

2. 既有專案改用本規範：加 `--into-existing`，只新增不存在的檔案；既有檔案逐一與範本比對後合併。
3. 產生的 `.ps1` 已是 **UTF-8 with BOM**、`requirements*.txt` 為純 ASCII；之後編輯請保持（§5）。
4. 完成後執行 `scripts/check_project.py <專案>`；交付前加 `--strict`（不得留下 `TODO(專案)`）。

## 5. 專案結構規範

```
<專案>/
├─ <app>/                    程式本體
│   ├─ __init__.py          __version__ = "x.y.z"（建置時讀取，寫入 exe 版本資訊與 zip 檔名）
│   ├─ __main__.py          CLI：run / dryrun / selfcheck / --version（必備）
│   ├─ config.py            從環境變數讀設定（含 .env 載入）
│   ├─ envfile.py           .env 解析（只接受 <PREFIX>_ 開頭）
│   ├─ odbc.py              ODBC Driver 自動偵測（有用 SQL Server 時）
│   └─ selfcheck.py         部署自我檢查
├─ run_<app>.py             Nuitka 建置入口（只 import 並呼叫 main）
├─ tests/                   單元測試（只用標準函式庫、不連資料庫）
├─ sql/                     DDL、預建資料、權限範本（每句可獨立執行）
├─ deploy/
│   ├─ build_nuitka.ps1     建置：測試 → 編譯 → 驗證 → 打包
│   ├─ protect_env.ps1      鎖 .env 權限
│   ├─ preflight.ps1        上線前檢查（網路、時間、設定、selfcheck --db）
│   ├─ register_task.ps1    建立工作排程
│   ├─ README.md            部署說明（§14）
│   └─ DEV_TEST.md          開發主機測試步驟（§14）
├─ requirements.txt         執行期套件（只放執行需要的）
├─ requirements-build.txt   建置期套件（nuitka>=4.2,<5、ordered-set）
├─ .env.example             設定範本（不含真實密碼，可進版控）
└─ .gitignore               至少：.env、.venv*/、build/、release/、logs/、build-freeze.txt
```

**檔案編碼規定**

| 檔案 | 編碼 | 原因 |
|---|---|---|
| `*.ps1` | **UTF-8 with BOM** | Windows PowerShell 5.1 沒有 BOM 時以 Big5 讀取，中文會亂碼甚至語法錯誤 |
| `requirements*.txt` | **純 ASCII**（註解用英文） | pip 以系統字碼頁（繁中 Windows 為 cp950）讀取，中文會 `UnicodeDecodeError` |
| `*.py`、`*.md`、`*.sql` | UTF-8 | — |

**PowerShell 撰寫規定**（相容 Windows PowerShell 5.1）
- `python -c "..."` 內只用單引號（5.1 傳參數會吃掉雙引號）。
- 呼叫外部程式探測（可能寫 stderr）時，暫時把 `$ErrorActionPreference` 改為 `Continue`，否則 5.1 會直接中止。
- 輸出格式化用 `Write-Host ("{0} ..." -f $x)`。
- 密碼一律 `Read-Host -AsSecureString`；要帶給子程序時用**環境變數**並在 `finally` 還原，不放命令列。

## 6. 程式設計規範

### 6.1 設定

1. 所有設定以**環境變數**讀取，變數一律加前綴 `<PREFIX>_`。
2. 支援 `.env`：找檔順序 `<PREFIX>_ENV_FILE` 指定路徑 → 目前目錄 → exe 所在目錄及上一層。
3. **已設定的環境變數優先於 `.env`**（臨時覆寫用）。
4. `.env` 只接受 `<PREFIX>_` 開頭的變數；格式錯誤要指出第幾行。
5. 值含空白或 `#` 用雙引號包住：`<PREFIX>_SQL_PASSWORD="ab #12"`。
6. `.env.example` 每一項都要有中文註解，說明值從哪裡取得。

### 6.2 資料庫連線

| 項目 | 規範 |
|---|---|
| SQL Server 驅動 | **自動偵測**：ODBC Driver N（取最新）→ SQL Server Native Client → 內建「SQL Server」；可用 `<PREFIX>_SQL_DRIVER` 指定 |
| 舊版驅動 | 內建「SQL Server」驅動不送 `Encrypt`／`TrustServerCertificate` |
| 伺服器位址 | 自動加 `tcp:` 前綴（避免退回 Named Pipes）；埠號用**逗號** `主機,1433`，寫成冒號要擋下並提示 |
| Oracle | `python-oracledb` thin 模式（不需 Oracle Client）；DSN `主機:1521/服務名稱` |
| 帳號 | SQL Server 用 SQL 驗證帳號；權限最小化；不使用 sa／DBA 帳號 |
| SQL | 全部參數化；欄位名、表名只能來自程式內白名單 |

### 6.3 必備子命令

| 子命令 | 行為 | 寫入 |
|---|---|---|
| `--version` | 印出版本 | 否 |
| `selfcheck` | 套件可載入、ODBC Driver | 否 |
| `selfcheck --db` | 再加：設定完整性、DNS／TCP 探測、資料庫實際連線、必要資料表存在、主機時間差 | 否 |
| `dryrun` | 完整計算一輪，結果輸出 CSV | **否** |
| `run` | 正式執行 | 是 |
| （建議）診斷命令 | 針對「讀不到資料」的唯讀診斷，並排列出各種比對條件的結果 | 否 |
| （建議）`run --cycle <時間>` | 指定時點補跑 | 是 |

### 6.4 日誌與結束碼

| 項目 | 規範 |
|---|---|
| 日誌位置 | 預設 `C:\ProgramData\<App>\logs\`，可用 `<PREFIX>_LOG_DIR` 覆寫；dryrun CSV 放 `logs\dryrun\` |
| 輪替 | 每日輪替，保留 90 天 |
| 每輪摘要 | 固定格式一行，例：`[run] T0=... rows=... missing=... errors=0 elapsed=1.2s` |
| 錯誤 | 每個失敗都有 `ERROR` 行並附 traceback；不允許靜默略過 |
| 結束碼 | `0` 成功、`1` 部分失敗（其餘已完成）、`2` 整輪失敗 |
| 時效 | 有截止時間的程式（須在下游讀取前寫完），超時要記警告 |

### 6.5 測試

- 單元測試只用標準函式庫，以假的資料存取物件模擬資料庫，**不需連線**即可在建置機執行。
- 建置腳本先跑單元測試，失敗即中止。
- 測試中模擬錯誤情境會印出錯誤訊息，屬正常；以最後的 `Ran N tests ... OK` 為準。

## 7. 標準作業流程

```
 階段 0  開發主機測試（原始碼、唯讀）   → selfcheck --db 全 OK、dryrun errors=0
 階段 1  建置（建置機）                 → release\<app>_<版本>_<日期時間>.zip
 階段 2  驗證編譯版（建置機、唯讀）     → exe 的 selfcheck --db、dryrun 與原始碼版相同
 階段 3  安裝與設定（目標主機）         → 解壓、相依元件、.env、protect_env
 階段 4  上線前驗證（目標主機、唯讀）   → preflight 全 OK、dryrun 連續 2～3 輪正常
 階段 5  上線                           → register_task；切換舊做法；開發主機停止 run
 階段 6  上線後第一小時檢查             → 排程結果 0、日誌 errors=0、資料連續無缺口
```

### 階段 0：開發主機測試（唯讀）

```powershell
cd <專案>
py -3.12 -m venv .venv            # 3.11～3.13 皆可
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -t .

copy .env.example .env            # 填入連線資訊；開發主機的日誌可設 <PREFIX>_LOG_DIR=logs
python -m <app> selfcheck --db
python -m <app> dryrun ...
```

- 先用**最小範圍**（一筆設定、一個廠區）驗證，正常後再擴大範圍重跑。
- dryrun 依排程頻率間隔重跑 2～3 次，確認每輪都拿到新資料。
- （選用）在正確時間窗手動 `run` 一輪，核對寫入結果。

### 階段 1：建置

```powershell
cd <專案>
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\deploy\build_nuitka.ps1 -Proxy "<proxy>" -ProxyUser "<帳號>" -TrustPyPI
```

| 參數 | 用途 |
|---|---|
| `-Proxy` / `-ProxyUser` | 經公司 Proxy 下載（密碼以隱藏輸入詢問） |
| `-TrustPyPI` | Proxy 攔截 HTTPS 時使用（等同 pip `--trusted-host`） |
| `-Python <路徑>` | 指定 python.exe（預設依序找 3.12 → 3.13 → 3.11 → PATH） |
| `-Compiler auto\|msvc\|mingw64\|zig` | C 編譯器（預設 auto，見 §8.3） |
| `-OdbcMsi <路徑>` | 把 ODBC 安裝檔一起打包 |
| `-SkipTests` | 重跑時略過已通過的單元測試 |

產出 `release\<app>_<版本>_<日期時間>.zip`，內含：`app\`（exe 與 DLL）、`deploy\`、`sql\`、`.env.example`、`README_DEPLOY.md`、`VERSION.txt`、`SHA256SUMS.txt`、`build-freeze.txt`、（選用）`prereq\`。

### 階段 2：驗證編譯版（唯讀）

```powershell
.\build\run_<app>.dist\<app>.exe --version
.\build\run_<app>.dist\<app>.exe selfcheck --db
.\build\run_<app>.dist\<app>.exe dryrun ...
```

結果必須與階段 0 相同。**換了編譯器、Python 或 Nuitka 版本時，這一步不可省略。**

### 階段 3：目標主機安裝與設定（系統管理員身分）

```powershell
# 1. 核對、解壓、解除封鎖
Get-FileHash .\<zip> -Algorithm SHA256                  # 與建置機的值比對
Expand-Archive .\<zip> -DestinationPath <InstallDir>
Get-ChildItem -Recurse <InstallDir> | Unblock-File

# 2. 相依元件（例：ODBC，已有 17 或 18 可略過）
Get-OdbcDriver -Name "ODBC Driver*SQL Server*" -Platform 64-bit
msiexec /i <InstallDir>\prereq\msodbcsql.msi /quiet IACCEPTMSODBCSQLLICENSETERMS=YES

# 3. 設定檔與權限
cd <InstallDir>
copy .env.example .env
notepad .env                                             # 正式值；不設 <PREFIX>_LOG_DIR（用預設 ProgramData）
.\deploy\protect_env.ps1 -RunAs "SYSTEM"
```

### 階段 4：上線前驗證（唯讀）

```powershell
.\deploy\preflight.ps1 -SqlHost "<SQL主機>" -OraHost "<Oracle主機>" ...
.\app\<app>.exe dryrun ...
```

preflight 全部 `[ OK ]`；dryrun 連續 2～3 輪 `errors=0`，結果與來源一致。

### 階段 5：上線

```powershell
.\deploy\register_task.ps1 -RunAs "SYSTEM"
```

同時完成：
1. 舊程式（若有）以設定排除同一批資料，避免兩邊寫入。
2. **開發主機停止執行 `run`**。
3. 回滾步驟告知值班人員。

### 階段 6：上線後第一小時檢查

| # | 檢查 | 方法 | 預期 |
|---|---|---|---|
| 1 | 排程結果 | `Get-ScheduledTask -TaskName <排程名> \| Get-ScheduledTaskInfo` | `LastTaskResult = 0`，`NextRunTime` 正確 |
| 2 | 程式日誌 | `Get-Content C:\ProgramData\<App>\logs\<app>.log -Tail 20 -Wait` | 每輪摘要 `errors=0`，無逾時警告 |
| 3 | 目的資料 | 查寫入的資料表 | 依排程頻率更新 |
| 4 | 下游 | 查下游系統 | 連續、無缺口 |

## 8. 建置規範（Nuitka）

### 8.1 版本

| 項目 | 規範 |
|---|---|
| Python | 3.12 64 位元優先；3.11、3.13 可用（3.14 未驗證，腳本會擋下） |
| Nuitka | `nuitka>=4.2,<5`（固定大版本） |
| 版本紀錄 | 每次建置輸出 `build-freeze.txt`，隨 zip 保存 |

### 8.2 編譯參數

| 參數 | 理由 |
|---|---|
| `--mode=standalone` | 輸出資料夾；**不用 onefile**（排程頻繁啟動，onefile 每次解壓，慢且易被防毒攔截） |
| `--include-package=<app>` 與主要相依套件 | 確保完整帶入 |
| `--include-module=<隱藏相依>` | C／Cython 擴充在執行期才 import 的模組，Nuitka 看不到；漏掉會在目標主機執行時才 `ModuleNotFoundError` |
| `--windows-console-mode=force` | 保留主控台輸出 |
| `--file-version`、`--product-version` | 由 `__version__` 帶入 |
| `--report=build\nuitka-report.xml` | 排查漏帶模組用 |

**已知的隱藏相依**（使用該套件時必須列入）：

| 套件 | `--include-module` | `--include-package` |
|---|---|---|
| `oracledb` | asyncio、base64、collections、copy、datetime、decimal、functools、getpass、hashlib、inspect、json、locale、os、random、re、secrets、select、socket、ssl、string、subprocess、threading、uuid、warnings | cryptography.hazmat.primitives、cryptography.x509 |
| `pyodbc` | — （`--include-module=pyodbc`） | — |

新套件的隱藏相依：先編譯，用編譯版實際跑 `selfcheck --db` 與 dryrun，缺什麼補什麼。不要列入 `array`、`sys`、`time` 等內建模組。

### 8.3 C 編譯器（`-Compiler auto`）

| 順序 | 條件 | 使用 |
|---|---|---|
| 1 | 偵測到 Visual Studio Build Tools（含 C++） | MSVC |
| 2 | 否則，Python ≤ 3.12 | MinGW64（Nuitka 自動下載，約 100～400 MB，經 Proxy，之後快取） |
| 3 | 否則 | Zig（Nuitka 自動下載） |

MinGW64 不需管理員權限。若公司不允許下載編譯器，請 IT 安裝 Visual Studio 2022 Build Tools（勾選「使用 C++ 的桌面開發」）。

### 8.4 Proxy

- pip 的 `--proxy`／`--trusted-host` **不會**傳給「安裝建置相依」的子程序（原始碼套件如 nuitka 安裝時會另開子程序下載 setuptools），所以**一律以環境變數**帶入：`HTTP_PROXY`、`HTTPS_PROXY`、`PIP_PROXY`、`PIP_TRUSTED_HOST`。
- `PIP_PROXY` 會蓋過 `pip.ini` 裡沒有帳密的 proxy 設定。
- 建置腳本只在下載期間設定這些環境變數，結束即還原；密碼不寫檔、不出現在命令列。
- 手動設定時，帳號／密碼特殊字元要 URL 編碼：`\`→`%5C`、`@`→`%40`、`#`→`%23`、`:`→`%3A`、`%`→`%25`。

## 9. 安全規範

| # | 規範 |
|---|---|
| S1 | `.env` 列入 `.gitignore`，**絕不提交**；版控只放 `.env.example` |
| S2 | 目標主機的 `.env` 必須執行 `protect_env.ps1`：移除繼承權限，只留執行帳號（讀）、Administrators、SYSTEM |
| S3 | 修改 `.env` 一律以「系統管理員身分」開記事本；權限被改掉就重跑 `protect_env.ps1` |
| S4 | 密碼不得放在命令列參數（會留在 PowerShell 歷史與程序清單） |
| S5 | 不小心把密碼打在命令列：`Clear-History; Remove-Item (Get-PSReadLineOption).HistorySavePath` |
| S6 | **貼錯誤訊息給他人（含 AI 助理、Teams、Email）前先遮掉密碼**；已外洩者立即更改密碼 |
| S7 | 資料庫帳號只給必要權限（讀來源、寫目的表） |
| S8 | 限制可登入目標主機的人員 |

## 10. 排程規範

| 項目 | 規範 | 理由 |
|---|---|---|
| 執行帳號 | **`SYSTEM`**（預設） | 不需密碼、不會過期；資料庫以 `.env` 的資料庫帳號連線，不受影響 |
| 例外：需要存取網路共用資料夾或用 Windows 整合驗證連資料庫 | 改用網域服務帳號（需「以批次工作登入」權限） | SYSTEM 對外以電腦帳號身分存取 |
| 個人或 Administrator 帳號 | 不建議；若使用，**改密碼後必須重跑 `register_task.ps1`** | 否則登入失敗（`0x8007052E`），資料默默停止更新 |
| 執行時間點 | 依業務；若下游會讀取結果，排在下游起跑**之前**並留緩衝 | 晚於下游讀取的資料可能永久缺漏 |
| 重疊 | `MultipleInstances IgnoreNew` | 上一輪未結束不啟動新的 |
| 執行上限 | `ExecutionTimeLimit` 小於排程間隔 | 卡住的程序不拖到下一輪 |
| 錯過 | 不自動補跑 | 以 `run --cycle` 手動補跑 |
| 起始目錄 | `<InstallDir>` | exe 依此找到 `.env` |
| 名稱 | 與程式對應（例：`<App>` 或 `XXX_Ingest`） | 方便辨識 |

## 11. 上線檢核表

**開發／建置**
- [ ] 單元測試全過
- [ ] 開發主機 `selfcheck --db` 全 OK
- [ ] 開發主機 dryrun：最小範圍 → 全部，各 2～3 輪，`errors=0`
- [ ] （選用）開發主機實際 `run` 一輪並核對
- [ ] `build_nuitka.ps1` 成功，取得 zip 與 SHA256
- [ ] 編譯版 `--version`、`selfcheck --db`、dryrun 與原始碼版一致

**申請與準備**
- [ ] 防火牆：目標主機 → 各資料庫
- [ ] 資料庫帳號與最小權限
- [ ] 目標主機時間同步（與相關主機差距 < 5 秒）
- [ ] 防毒排除 `<InstallDir>\app\`（若有誤判）

**目標主機**
- [ ] SHA256 核對、解壓、`Unblock-File`
- [ ] 相依元件（ODBC 等）已安裝
- [ ] `.env` 填寫完成（正式值、無開發用設定）
- [ ] `protect_env.ps1 -RunAs "SYSTEM"` 完成
- [ ] `preflight.ps1` 全 OK
- [ ] dryrun 連續 2～3 輪正常
- [ ] `register_task.ps1 -RunAs "SYSTEM"` 完成

**切換與上線後**
- [ ] 舊做法已排除同一批資料
- [ ] 開發主機停止 `run`
- [ ] 回滾步驟已告知值班人員
- [ ] 第一小時：`LastTaskResult=0`、日誌 `errors=0`、資料連續
- [ ] 第一天結束：缺值／錯誤紀錄無異常累積

## 12. 維運：更新、回滾、移除

| 作業 | 步驟 |
|---|---|
| 版本更新 | 改 `__version__` → 建置 → 目標主機 `Disable-ScheduledTask` → 備份並替換 `app\` → `app\<app>.exe selfcheck --db` → `Enable-ScheduledTask`（路徑不變不用重建排程） |
| 只改部署腳本 | 複製新的 `deploy\*.ps1` 覆蓋，`Unblock-File`；不用重建 exe |
| 換資料庫密碼 | 系統管理員身分編輯 `.env`，下一輪生效 |
| 暫停／恢復 | `Disable-ScheduledTask -TaskName <排程名>`／`Enable-ScheduledTask -TaskName <排程名>` |
| 緊急回滾 | ① 停用排程 ② 把資料切回舊做法（各專案於交付文件寫明 SQL／設定） ③ 確認舊做法下一輪已接手 |
| 補跑 | `app\<app>.exe run --cycle "<時間>"`；下游已讀取過的時點需另行處理 |
| 移除 | `Unregister-ScheduledTask -TaskName <排程名> -Confirm:$false`，再刪除 `<InstallDir>` |

## 13. 常見問題排查（FAQ）

> 排查順序：**日誌最後一行摘要與 ERROR 行** → `selfcheck --db` → 診斷命令。
> 回報問題附上：完整指令、完整輸出（**遮掉密碼**）、日誌相關段落。

### 13.1 開發主機／資料庫腳本

| # | 現象 | 原因 | 處理 |
|---|---|---|---|
| D1 | DBeaver：`必須宣告資料表變數 "@x"` | DBeaver 以分號拆句，變數宣告與使用被拆到不同批次 | SQL 腳本寫成「每句可獨立執行」；必須整份執行的用 `Ctrl+A` 後 `Ctrl+Enter`（或 `Alt+X`） |
| D2 | Oracle：`ORA-06550` / `PLS-00103 ... end-of-file` | DBeaver 吃掉 PL/SQL 區塊 `END;` 的分號 | 改用純 SQL（例：`INSERT ... SELECT ... WHERE NOT EXISTS`） |
| D3 | `IM002 找不到資料來源名稱且未指定預設驅動程式` | 指定的 ODBC Driver 未安裝 | 拿掉 `<PREFIX>_SQL_DRIVER` 讓程式自動挑選；`selfcheck` 會列出本機已安裝的驅動 |
| D4 | SQL Server `Named Pipes Provider ... (53)` | 主機名稱錯誤或連不到 | 看 `selfcheck --db` 的 DNS／TCP：DNS 失敗 → 主機名稱打錯，或改用 IP／FQDN；TCP 失敗 → 埠號或防火牆 |
| D5 | `埠號要用逗號` | 寫成 `主機:1433` | SQL Server 是 `主機,1433`（Oracle 才用冒號） |
| D6 | `Login failed for user` | 帳密錯誤或無權限 | 確認帳密；請 DBA 確認權限 |
| D7 | Oracle `ORA-01017` | 帳密錯誤 | 確認帳密 |
| D8 | Oracle `DPY-6005` | 主機、埠、service_name 或防火牆 | 對照既有系統的連線設定 |
| D9 | Oracle `DPY-3015` | 帳號使用舊版密碼驗證，thin 模式不支援 | 請 DBA 確認密碼版本（需 11G 以上） |
| D10 | `certificate chain ... not trusted` | 伺服器自簽憑證 | `<PREFIX>_SQL_TRUST_CERT=yes` |
| D11 | dryrun 一直讀不到值 | 名稱、來源表、時間條件不符，或**來源本身停止更新** | 執行診斷命令；來源最新一筆停在過去 → 來源中斷，不是程式問題 |
| D12 | dryrun 正常，但資料庫沒寫入 | **dryrun 不寫資料庫** | 寫入需 `run`（注意時間窗） |
| D13 | 手動 `run` 寫到錯的時點 | 不在時間窗，或時點對齊參數不對 | 依專案說明的時間窗執行，並以環境變數臨時覆寫對齊參數 |
| D14 | 某筆第一次沒寫入、重跑正常 | 偶發（鎖、逾時等） | 看該輪 `ERROR` 行；反覆發生要回報 |

### 13.2 建置機

| # | 現象 | 原因 | 處理 |
|---|---|---|---|
| B1 | `執行指令碼已停用` / `running scripts is disabled` | PowerShell 執行原則 | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| B2 | 腳本中文亂碼、莫名語法錯誤 | `.ps1` 不是 UTF-8 with BOM | VS Code 另存為「UTF-8 with BOM」 |
| B3 | `py.exe : No suitable Python runtime found` | 沒有指定版本 | 腳本會自動找 3.13／3.11／PATH；或 `-Python "<python.exe>"`；`py -0p` 列出已安裝版本 |
| B4 | `需要 Python 3.11～3.13 64 位元` | 版本不符或 32 位元 | 安裝 3.12 64 位元，以 `-Python` 指定 |
| B5 | `407 Proxy authentication required` | Proxy 需帳密 | `-Proxy "<proxy>" -ProxyUser "<帳號>"` |
| B6 | `Installing build dependencies ... error`，子程序 407、`No matching distribution found for setuptools` | pip `--proxy` 不會傳給建置子程序 | 改用環境變數（腳本已內建）；手動時設 `HTTPS_PROXY`、`PIP_PROXY` |
| B7 | `UnicodeDecodeError: 'cp950' codec can't decode` | `requirements*.txt` 含中文 | requirements 只用 ASCII |
| B8 | `SSL: CERTIFICATE_VERIFY_FAILED` | Proxy 攔截 HTTPS | 加 `-TrustPyPI`；Nuitka 下載也失敗時，向 IT 取得根憑證或改裝 VS Build Tools |
| B9 | `Cannot connect to proxy`／逾時 | Proxy 主機或埠錯 | `netsh winhttp show proxy` 或瀏覽器設定；PAC 自動設定請問網管 |
| B10 | `cannot locate suitable C compiler` | 沒有 VS Build Tools | `-Compiler auto` 會自動改用 MinGW64／Zig；或請 IT 安裝 VS 2022 Build Tools（C++） |
| B11 | `module 'array' ... is built-in` 警告 | 內建模組不需列入 | 從 `$HiddenModules` 移除 |
| B12 | 單元測試輸出大量錯誤訊息 | 測試刻意模擬錯誤 | 以 `Ran N tests ... OK` 為準 |
| B13 | 編譯版 `No module named 'xxx'` | 漏帶隱藏相依 | 加入 `$HiddenModules` 重建；查 `build\nuitka-report.xml` |
| B14 | 建置時 `selfcheck` 的 ODBC 項 FAIL | 建置機沒裝 ODBC | 可忽略；其餘套件必須 OK |

### 13.3 目標主機部署

| # | 現象 | 原因 | 處理 |
|---|---|---|---|
| T1 | exe 或腳本被擋 | 複製來的檔案被標記封鎖 | `Get-ChildItem -Recurse <InstallDir> \| Unblock-File` |
| T2 | 防毒刪除或隔離 exe | Nuitka 編譯檔誤判 | 請資安把 `app\` 加入排除 |
| T3 | 缺少 `VCRUNTIME140.dll` | 缺 VC++ 執行階段 | 安裝 Visual C++ 2015-2022 Redistributable (x64) |
| T4 | `protect_env.ps1` 的 `icacls 失敗` | 帳號名稱錯或非管理員身分 | 系統管理員開 PowerShell；`-RunAs` 填 `SYSTEM` 或 `whoami` 顯示的 `網域\帳號` |
| T5 | 鎖權限後打不開 `.env` | 權限只剩執行帳號與管理員 | 以系統管理員身分開記事本 |
| T6 | preflight：`.env 權限過寬` | 沒執行或被改回 | 重跑 `protect_env.ps1` |
| T7 | `register_task.ps1 -RunAs "SYSTEM"` 仍詢問密碼 | 舊版腳本 | 換新版（`Select-String deploy\register_task.ps1 -Pattern "NT AUTHORITY"` 有結果即新版）；密碼視窗按取消不會建立任何東西 |
| T8 | 設定值警告（例：時點對齊參數） | `.env` 沿用開發主機的值 | 改成正式值 |
| T9 | 時間差警告 | 主機時間未同步 | `w32tm /resync`；請管理者確認網域時間同步 |

### 13.4 上線後執行

| # | 現象 | 原因 | 處理 |
|---|---|---|---|
| R1 | 在哪裡看排程 | — | `taskschd.msc` → 工作排程器程式庫 → 排程名；或 `Get-ScheduledTask -TaskName <排程名> \| Get-ScheduledTaskInfo` |
| R2 | 「歷程記錄」顯示已停用 | 預設關閉 | 右側「啟用所有工作歷程記錄」 |
| R3 | `LastTaskResult = 0x1` | 部分失敗 | 看日誌 `ERROR` 行 |
| R4 | `LastTaskResult = 0x2` | 整輪失敗（設定、連線、讀不到 `.env`） | 看日誌；`selfcheck --db`；確認執行帳號能讀 `.env` |
| R5 | `LastTaskResult = 0x8007052E` | 排程帳號登入失敗（改過密碼） | 改用 `SYSTEM`，或重跑 `register_task.ps1` |
| R6 | `LastTaskResult = 0x41301` | 執行中 | 長時間如此表示卡住，看日誌 `elapsed` |
| R7 | `LastTaskResult = 0x41306` | 工作被終止（手動結束，或超過執行上限） | 看日誌 `elapsed` 與資料庫回應時間 |
| R8 | 逾時警告（晚於下游讀取） | 執行太慢或排程時間不對 | 確認排程時間與對齊參數；檢查 `elapsed` 與資料庫效能 |
| R9 | 資料忽新忽舊、重複寫入 | 兩處同時寫入 | 停止開發主機 `run`；確認舊做法已排除 |
| R10 | 寫入 0 列 | 目的表沒有預建資料或鍵值打錯 | 依專案 `sql/` 腳本預建 |
| R11 | 日誌找不到 | 不在預設位置 | 預設 `C:\ProgramData\<App>\logs\`；或看 `.env` 的 `<PREFIX>_LOG_DIR` |

## 14. 附錄：交付文件範本

每個專案的 `deploy/` 至少要有兩份文件，章節如下：

**`deploy/DEV_TEST.md`（開發主機測試）**
1. 準備（Python、ODBC、網路、取得程式碼）
2. 單元測試
3. 設定連線（`.env`，說明每個值從哪裡取得）
4. 自我檢查（`selfcheck --db`）
5. dry-run（看哪些欄位、預期結果、怎麼對照來源）
6. 實際寫入一輪（選用；時間窗、驗證 SQL）
7. 測試編譯版
8. 回報要附哪些資訊

**`deploy/README.md`（部署說明，打包時成為 `README_DEPLOY.md`）**
0. 總覽（機器、排程時序、流程）
1. 建置機準備
2. 建置
3. 申請與準備（防火牆、帳號、時間同步、資料庫權限）
4. 目標主機安裝
5. 設定（`.env` + `protect_env`）
6. 驗證（preflight、dryrun）
7. 上線與第一小時檢查
8. 日常維運
9. 疑難排解（專案特有的問題；通用問題引用本規範 §13）
10. **回滾步驟**（具體 SQL／設定）

**範本**：`assets/template/deploy/README.md`、`assets/template/deploy/DEV_TEST.md`（scaffold 產生時已替換名稱，章節已依本節排好）。
