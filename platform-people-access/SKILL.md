---
name: platform-people-access
description: 內部平台的人員與權限管理標準作法：從公司員工資料表（base.kh_ad_employees，唯讀）查詢與選人、平台自己的名單表記錄工號的角色與可用範圍、後端逐請求檢查權限、管理頁的選人元件（員工選擇器）、主管兩層預填、異動理由與不可變版本紀錄、DBA 授權與欄位對應檢查。只要是在做或修改「權限控管」「角色權限」「RBAC」「人員與權限」「名單設定」「白名單」「簽核人／負責人／通知名單」「選人」「從員工表帶出姓名 Email 部門」「查人員清單」「主管是誰」「kh_ad_employees」「EMPLOYEE_TABLE」，或使用者問 AD 登入後如何決定誰能用什麼功能、員工資料表怎麼讀、為什麼讀員工表 permission denied 時，都要使用這個 skill——即使使用者沒有提到員工資料表的名稱。
---

# 平台人員與權限（員工資料表＋名單＋選人）

整理自 GMS 監控平台（`gms-monitor-agent`）實際上線的作法，選人元件與 power-bill-agent 同一規格。平台的登入（AD／SSO）與部署照 `python-iis-deploy-standard` skill；這份只管**登入之後「這個人是誰、能做什麼」**。

## 核心原則（不要違反）

1. **員工資料表只讀**。`base.kh_ad_employees` 是全公司共用的，平台只 SELECT；在 `deployment.json` 的 `database.sharedReads` 宣告、由 DBA 授權給本系統的 `<prefix>_rw` 群組。不改它、不複製它、不建 view 寫回去。
2. **權限存在平台自己的表**，以**工號**為主鍵（`<prefix>_person`）。角色不從 AD 群組來；AD 登入成功只代表「身分正確」，名單裡沒有的人一律 403「沒有本系統的使用權限」。
3. **身分以員工資料表為準**：選人一律從員工表搜尋（選人元件），不讓人打工號或姓名；儲存時伺服器重新查表帶入姓名與 Email，表單送來的不採用；員工表查無的工號不能新增。
4. **離職或調動不自動拔權限**：員工表查無已在名單的人時，權限保留、頁面標示「查無此工號」，由管理員處理。
5. **權限每個請求在後端重算**：Session 只存帳號；改權限立即生效；每支 API 自己檢查，前端停用按鈕只是體驗。拒絕一律回 **403**（401 會讓 IIS 跳出 Windows 帳密視窗）。
6. **每次異動要理由、留不可變版本**：history 表只新增，資料庫觸發器擋 UPDATE／DELETE，同時寫稽核。
7. **沒有員工表也要能運作**：未設定 `EMPLOYEE_TABLE` 時退回手動輸入並明確警告；員工表讀不到時名單頁照常開、搜尋回 502 說明原因，不回 500。

## 工作流程

### 新專案加入人員與權限

1. 決定角色清單、是否往下包含、有沒有「範圍」（廠棟／部門／產線），寫進專案決策紀錄。
2. 設定：`.env.example` 加 `EMPLOYEE_TABLE=base.kh_ad_employees`、`AUTH_ADMIN_ACCOUNTS=`；設定檔加 `employees.columns` 欄位對應 → `references/data-model.md` §2。
3. 宣告：`deployment.json` 設 `auth.employeeLookup: true`、`auth.rbac` 寫一兩句說明、`database.sharedReads: ["base.kh_ad_employees"]`。
4. Migration 建 `<prefix>_person`、`<prefix>_person_history`（需要時加範圍負責人表）與不可變觸發器 → `references/data-model.md` §3。
5. 複製 `scripts/employee_directory.py` 進專案，照 `references/backend.md` 接上：`Principal`／`current_user`、`require_role`、管理 API、`save_person` 規則、通知收件者。
6. 前端照 `references/person-picker.md` 用 `assets/frontend/` 的選人元件（React 或原生 JS），做「人員與權限」頁。
7. 測試：複製 `assets/tests/test_employee_directory.py`，再為 `save_person` 的每條規則與每支 API 的 403 寫測試。
8. 部署後在伺服器用服務帳號跑 `scripts/check_employee_table.py`；讀不到就把它印出的 GRANT 給 DBA。

### 只要「查人員清單」（例如下拉選負責人、顯示姓名）

不需要整套權限：步驟 2、3 的員工表部分＋`employee_directory.py`＋一支搜尋 API（`/api/admin/employees` 或業務自己的路徑，限需要的角色）＋選人元件即可。顯示姓名用 `directory.find([...])` 一次查多筆。

### 既有專案改用這套

先找出目前的做法：手打工號／姓名的欄位、寫死在設定裡的名單、用 AD 群組判斷角色、把員工表複製進平台的同步程式。逐項換成上面的作法前，先列出差距給使用者確認；既有名單用一次性腳本匯入 `<prefix>_person`（每筆寫 history，理由「初始匯入」），員工表查無的工號列出來給使用者處理，不要自動丟掉。

## 員工資料表速查

| 標準欄位 | `base.kh_ad_employees` 的欄位（現場） | 用途 |
|---|---|---|
| `account` | `empno` | 工號，比對不分大小寫 |
| `name` | `empname` | 姓名 |
| `email` | `email` | 通知收件者 |
| `department` | `department_name` | 選人時顯示、可搜尋 |
| `title` | `title` | 選人時顯示、可搜尋 |
| `manager` | `manager_empno` | 直屬主管工號，預填兩層主管 |

欄位名稱**不寫死在程式裡**，以設定對應；實際欄位以 `check_employee_table.py` 列出的為準。

```bash
python scripts/check_employee_table.py --settings settings.json --search 王
```

## 檔案

```text
platform-people-access/
├─ SKILL.md
├─ references/
│  ├─ data-model.md          員工表設定與授權、查詢 SQL、平台名單表 DDL、稽核
│  ├─ backend.md             角色、每請求權限計算、403 裝飾器、管理 API、save_person 規則、通知、FastAPI
│  └─ person-picker.md       選人元件規格、資料來源、頁面狀況處理、管理頁版面
├─ scripts/
│  ├─ employee_directory.py  員工表唯讀查詢（search／find／supervisor_chain／describe），直接複製進專案
│  └─ check_employee_table.py 部署後核對讀取權限與欄位對應，讀不到時印出給 DBA 的 GRANT
└─ assets/
   ├─ frontend/              PersonPicker.jsx、person-picker.js（原生）、person-picker.css
   └─ tests/                 test_employee_directory.py（SQLite，不需公司資料庫）
```

## 常見問題

| 現象 | 原因與處理 |
|---|---|
| 搜尋回 502「無法讀取」、`check_employee_table.py` 顯示 `permission denied` | DBA 尚未授權。把腳本印出的 `GRANT USAGE ON SCHEMA base`、`GRANT SELECT ON base.kh_ad_employees` 給 DBA，對象是 `<prefix>_rw` 群組 |
| 「欄位對應不在表裡」 | `employees.columns` 寫錯；照腳本列出的實際欄位修正 |
| AD 登入成功但每個畫面都 403「沒有本系統的使用權限」 | 名單沒有這個工號或已停用。新安裝時用 `AUTH_ADMIN_ACCOUNTS` 的帳號登入後在管理頁加人 |
| 登入帳號是 `DOMAIN\a1001`，名單是 `A1001` 對不上 | 登入時去掉網域；查名單與員工表時工號比對不分大小寫，新人員存員工表的寫法 |
| 改了權限沒生效 | 把角色存進 Session 了；改成每請求從名單表讀 |
| 被拒時瀏覽器跳出 Windows 帳密視窗 | 回了 401；改 403 |
| 名單上的人顯示「查無此工號」 | 員工表已查無（離職、調動或工號變更）。這是預期行為，由管理員確認後停用，不要寫程式自動刪 |
| 部署助手 `AUTH-10` 不通過 | 程式裡有 `INSERT/UPDATE/DELETE` 員工資料表；移除，平台的資料寫在自己的 Schema |
