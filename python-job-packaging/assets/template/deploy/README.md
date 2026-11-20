# {{app}} 部署說明

> {{description}}
>
> 本文件依《Python 排程程式打包與部署標準規範》（排程打包）§14 撰寫；通用問題見規範 §13 FAQ。
> 打包時本檔會成為部署包內的 `README_DEPLOY.md`。
> 標示 **TODO(專案)** 的段落請依實際專案填寫，交付前不得留下。

| 項目 | 內容 |
|---|---|
| 套件／exe | `{{app}}` ／ `app\{{app}}.exe` |
| 工作排程名稱 | `{{TaskName}}` |
| 環境變數前綴 | `{{PREFIX}}_` |
| 安裝目錄 | `D:\Jobs\{{app}}`（下文以 `<InstallDir>` 表示） |
| 日誌 | `C:\ProgramData\{{App}}\logs\{{app}}.log`（每日輪替，保留 90 天）；dryrun CSV 在 `logs\dryrun\` |
| 結束碼 | `0` 成功、`1` 部分失敗、`2` 整輪失敗 |

## 0. 總覽

TODO(專案)：寫明資料從哪裡讀、寫到哪裡、下游是誰、何時讀取。

| 機器 | 用途 |
|---|---|
| 開發主機 | 原始碼測試（selfcheck／dryrun），見 `deploy/DEV_TEST.md` |
| 建置機 | 編譯 exe、打包 zip（經 Proxy 連外網） |
| 目標主機 | 正式執行排程（不連外網） |

排程時序：TODO(專案)（例：每 5 分鐘，第 0 分起跑；下游於第 3 分讀取，本程式須在 2 分鐘內完成）。

```
開發主機測試 → 建置 → 驗證編譯版 → 目標主機安裝 → preflight + dryrun → register_task → 第一小時檢查
```

## 1. 建置機準備

- Windows x64，可經 Proxy 連外網
- Python 3.12 64 位元（3.11、3.13 亦可）
- C 編譯器可選：有 Visual Studio 2022 Build Tools（C++）用 MSVC；沒有時 Nuitka 自動下載 MinGW64／Zig

## 2. 建置

```powershell
cd <專案>
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\deploy\build_nuitka.ps1 -Proxy "<proxy>" -ProxyUser "<帳號>" -TrustPyPI
```

產出 `release\{{app}}_<版本>_<日期時間>.zip` 與 `.zip.sha256`。建置後先用編譯版驗證（結果必須與原始碼版相同）：

```powershell
.\build\run_{{app}}.dist\{{app}}.exe --version
.\build\run_{{app}}.dist\{{app}}.exe selfcheck --db
.\build\run_{{app}}.dist\{{app}}.exe dryrun
```

## 3. 申請與準備

| 項目 | 內容 | 負責 |
|---|---|---|
| 防火牆 | 目標主機 → TODO(專案)：資料庫主機與連接埠 | 網路／資安 |
| 資料庫帳號 | TODO(專案)：帳號與最小權限（讀哪些表、寫哪些表） | DBA |
| 資料表／預建資料 | 依 `sql\` 腳本建立 | DBA |
| 時間同步 | 目標主機與相關主機差距 < 5 秒 | 系統管理員 |
| 防毒排除 | `<InstallDir>\app\`（若有誤判） | 資安 |

## 4. 目標主機安裝（系統管理員身分）

```powershell
Get-FileHash .\{{app}}_<版本>_<日期時間>.zip -Algorithm SHA256     # 與 .zip.sha256 比對
Expand-Archive .\{{app}}_<版本>_<日期時間>.zip -DestinationPath D:\Jobs\{{app}}
Get-ChildItem -Recurse D:\Jobs\{{app}} | Unblock-File
```

<!-- {{#sqlserver}} -->
相依元件（ODBC Driver for SQL Server，已有 17 或 18 可略過；建置時加 `-OdbcMsi` 才會有 `prereq\`）：

```powershell
Get-OdbcDriver -Name "ODBC Driver*SQL Server*" -Platform 64-bit
msiexec /i D:\Jobs\{{app}}\prereq\msodbcsql.msi /quiet IACCEPTMSODBCSQLLICENSETERMS=YES
```

<!-- {{/sqlserver}} -->
TODO(專案)：有其他相依元件（例：VC++ 執行階段）時補上；沒有就刪除這一行。

## 5. 設定（`.env` + `protect_env`）

```powershell
cd D:\Jobs\{{app}}
copy .env.example .env
notepad .env                                  # 填正式值；不要設 {{PREFIX}}_LOG_DIR（用預設 ProgramData）
.\deploy\protect_env.ps1 -RunAs "SYSTEM"
```

TODO(專案)：列出每個設定的正式值來源（不寫密碼）。

| 設定 | 正式值 | 來源 |
|---|---|---|
| `{{PREFIX}}_...` | | |

之後修改 `.env` 一律以「系統管理員身分」開記事本；權限被改掉就重跑 `protect_env.ps1`。

## 6. 驗證（唯讀）

```powershell
.\deploy\preflight.ps1
.\app\{{app}}.exe dryrun
```

- preflight 全部 `[ OK ]`
- dryrun 依排程間隔連續 2～3 輪 `errors=0`，CSV 內容與來源一致

TODO(專案)：寫明 dryrun CSV 要看哪些欄位、怎麼對照來源。

## 7. 上線與第一小時檢查

```powershell
.\deploy\register_task.ps1 -RunAs "SYSTEM"      # 預設頻率見腳本；可加 -IntervalMinutes / -At
```

同時完成：舊做法（若有）排除同一批資料；開發主機停止執行 `run`；回滾步驟（§10）告知值班人員。

| # | 檢查 | 方法 | 預期 |
|---|---|---|---|
| 1 | 排程結果 | `Get-ScheduledTask -TaskName {{TaskName}} \| Get-ScheduledTaskInfo` | `LastTaskResult = 0`，`NextRunTime` 正確 |
| 2 | 程式日誌 | `Get-Content C:\ProgramData\{{App}}\logs\{{app}}.log -Tail 20 -Wait` | 每輪摘要 `errors=0`，無超過預算警告 |
| 3 | 目的資料 | TODO(專案)：查詢 SQL | 依排程頻率更新 |
| 4 | 下游 | TODO(專案) | 連續、無缺口 |

## 8. 日常維運

| 作業 | 步驟 |
|---|---|
| 版本更新 | 改 `__version__` → 建置 → `Disable-ScheduledTask -TaskName {{TaskName}}` → 備份並替換 `app\` → `app\{{app}}.exe selfcheck --db` → `Enable-ScheduledTask -TaskName {{TaskName}}` |
| 只改部署腳本 | 複製新的 `deploy\*.ps1` 覆蓋，`Unblock-File`；不用重建 exe |
| 換資料庫密碼 | 系統管理員身分編輯 `.env`，下一輪生效 |
| 暫停／恢復 | `Disable-ScheduledTask -TaskName {{TaskName}}`／`Enable-ScheduledTask -TaskName {{TaskName}}` |
| 移除 | `Unregister-ScheduledTask -TaskName {{TaskName}} -Confirm:$false`，再刪除 `D:\Jobs\{{app}}` |

## 9. 疑難排解

排查順序：**日誌最後一行摘要與 ERROR 行** → `selfcheck --db` → 診斷命令。
通用問題（ODBC、Proxy、編譯器、權限、排程結果碼）見規範 §13 FAQ。回報問題前先遮掉密碼。

TODO(專案)：本程式特有的問題。

| 現象 | 原因 | 處理 |
|---|---|---|
| | | |

## 10. 回滾步驟

目標：5 分鐘內完成。

1. 停用排程：`Disable-ScheduledTask -TaskName {{TaskName}}`
2. 把資料切回舊做法：TODO(專案)：具體 SQL／設定
3. 確認舊做法下一輪已接手：TODO(專案)：確認方式
