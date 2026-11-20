# {{app}} 開發主機測試

> 在開發主機以原始碼驗證，全部**唯讀**（除了第 6 節選用的實際寫入）。依《排程打包》規範 §7 階段 0 與 §14。
> 標示 **TODO(專案)** 的段落請依實際專案填寫，交付前不得留下。

## 1. 準備

- Python 3.11～3.13 64 位元（建議 3.12）
<!-- {{#sqlserver}} -->
- ODBC Driver 17 或 18 for SQL Server
<!-- {{/sqlserver}} -->
- 網路：開發主機可連 TODO(專案)：資料庫主機與連接埠
- 取得程式碼：`git clone ...`，`cd <專案>`

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. 單元測試

```powershell
python -m unittest discover -s tests -t .
```

測試會刻意模擬錯誤情境並印出錯誤訊息，屬正常；以最後的 `Ran N tests ... OK` 為準。

## 3. 設定連線

```powershell
copy .env.example .env
notepad .env
```

開發主機建議設 `{{PREFIX}}_LOG_DIR=logs`（日誌寫在專案內）。`.env` 已列入 `.gitignore`，不要提交。

TODO(專案)：說明每個值從哪裡取得。

| 設定 | 說明／取得方式 |
|---|---|
| `{{PREFIX}}_...` | |

## 4. 自我檢查

```powershell
python -m {{app}} selfcheck --db
```

預期全部 `[ OK ]`。失敗時依訊息處理：DNS 失敗 → 主機名稱；TCP 失敗 → 埠號或防火牆；登入失敗 → 帳密或權限（規範 FAQ D3～D10）。

## 5. dry-run（唯讀）

```powershell
python -m {{app}} dryrun
```

- 摘要行：`[dryrun] rows=... written=0 errors=0 elapsed=...s`
- CSV：`logs\dryrun\dryrun_<時間>.csv`

TODO(專案)：要看哪些欄位、預期結果、怎麼對照來源（附查詢 SQL）。先用最小範圍驗證，正常後再擴大；依排程間隔重跑 2～3 次，確認每輪都拿到新資料。

## 6. 實際寫入一輪（選用）

```powershell
python -m {{app}} run
```

TODO(專案)：可執行的時間窗、寫入目標、驗證 SQL。**正式上線後開發主機不得再執行 `run`**（同一份資料只能有一個寫入者）。

## 7. 測試編譯版

建置（見 `deploy/README.md` §2）後，用編譯版重複第 4、5 節，結果必須與原始碼版相同：

```powershell
.\build\run_{{app}}.dist\{{app}}.exe --version
.\build\run_{{app}}.dist\{{app}}.exe selfcheck --db
.\build\run_{{app}}.dist\{{app}}.exe dryrun
```

## 8. 回報問題時附上

- 完整指令與完整輸出（**先遮掉密碼**）
- 日誌相關段落（`logs\{{app}}.log`）
- `selfcheck --db` 的輸出
- dryrun CSV（如與資料有關）
