# 資料模型：員工資料表、平台名單、異動紀錄

## 1. 兩種資料，分清楚誰管什麼

| | 公司員工資料表 | 平台自己的名單 |
|---|---|---|
| 例子 | `base.kh_ad_employees` | `<schema>.<prefix>_person`、`_person_history` |
| 回答的問題 | 這個工號是誰：姓名、Email、部門、職稱、直屬主管 | 這個人在**本平台**能做什麼：角色、可檢視／可操作的範圍、主管、是否停用 |
| 誰維護 | 公司（人資／AD 同步），全公司共用 | 本平台的系統管理員，從管理頁設定 |
| 平台可以 | **只能 SELECT** | 讀寫（透過 `<prefix>_rw` 群組） |
| 部署規範 | `database.sharedReads`；寫入會被 `AUTH-10`、`DB-06` 擋下 | 本系統 Schema 內的表，由 Migration 建立 |

**不要**為了加欄位（例如「角色」）去改員工資料表、建 view 寫回去、或把整張表複製進平台定期同步。平台只存「工號 → 權限」，要顯示姓名時再查員工資料表（或用儲存時帶入的快照）。

## 2. 員工資料表的讀法

### 2.1 設定（不寫死欄位名稱）

表名放 `.env`，欄位對應放設定檔（非機密）：

```ini
# .env.example
# 公司員工資料表（唯讀，schema.table）。未設定時人員管理只能手動輸入，頁面會警告。
EMPLOYEE_TABLE=base.kh_ad_employees
```

```json
// settings.json（或 config 檔的同名區段）
"employees": {
  "columns": {
    "account": "empno",
    "name": "empname",
    "email": "email",
    "department": "department_name",
    "manager": "manager_empno",
    "title": "title"
  },
  "active": null
}
```

| 鍵 | 必填 | 說明 |
|---|---|---|
| `columns.account` | ✓ | 工號（主鍵用；比對不分大小寫） |
| `columns.name` | ✓ | 姓名 |
| `columns.email` | ✓ | Email（通知收件者） |
| `columns.department` | | 部門，選人時顯示、可搜尋 |
| `columns.manager` | | 直屬主管工號。有設定時新增人員會預填兩層主管 |
| `columns.title` | | 職稱，選人時顯示、可搜尋 |
| `active` | | 只列在職者：`{"column": "status", "values": ["在職"]}`；`null` 表示全部 |

現場 `base.kh_ad_employees` 的欄位是 `empno`、`empname`、`email`、`department_name`、`title`、`manager_empno`（取自 GMS 監控平台的部署紀錄）。**欄位仍以實際查到的為準**：部署後跑 `scripts/check_employee_table.py`，它會列出實際欄位並核對對應。

### 2.2 部署宣告與 DBA 授權

`deployment.json`：

```json
"auth": { "ad": true, "sso": true, "employeeLookup": true, "rbac": "平台表 <prefix>_person 記錄工號、角色與範圍，由系統管理員在「人員與權限」設定" },
"database": { "name": "CIM", "schema": "<schema>", "prefix": "<prefix>", "sharedReads": ["base.kh_ad_employees"] }
```

授權給**群組**，不要給個人或服務帳號本身（服務帳號只加入群組）：

```sql
-- 由 DBA 執行；程式與 Migration 都不寫 GRANT 到 base
GRANT USAGE  ON SCHEMA base               TO <prefix>_rw;
GRANT SELECT ON base.kh_ad_employees      TO <prefix>_rw;
-- 報表或唯讀帳號也要選人時再加：
GRANT SELECT ON base.kh_ad_employees      TO <prefix>_ro;
```

讀不到時 `check_employee_table.py` 會印出上面這兩行（`--rw-role` 帶入群組名稱）。

### 2.3 查詢寫法

直接用 `scripts/employee_directory.py`。如果專案不能用 SQLAlchemy，自己寫時要守住：

```sql
-- 搜尋：每個字詞一組 OR，字詞之間 AND；值全部用參數
SELECT "empno" AS account, "empname" AS name, "email" AS email,
       "department_name" AS department, "manager_empno" AS manager, "title" AS title
FROM "base"."kh_ad_employees"
WHERE 1 = 1
  AND (LOWER(CAST("empno" AS VARCHAR(200))) LIKE :w0 ESCAPE '\'
    OR LOWER(CAST("empname" AS VARCHAR(200))) LIKE :w0 ESCAPE '\'
    OR LOWER(CAST("email" AS VARCHAR(200))) LIKE :w0 ESCAPE '\'
    OR LOWER(CAST("department_name" AS VARCHAR(200))) LIKE :w0 ESCAPE '\'
    OR LOWER(CAST("title" AS VARCHAR(200))) LIKE :w0 ESCAPE '\')
ORDER BY "empno";
-- :w0 = '%' || 把 \ % _ 跳脫後轉小寫的字詞 || '%'；最多 3 個字詞；取前 20 筆
```

- 欄位名稱來自設定，只接受 `[A-Za-z_][A-Za-z0-9_]*`，再由資料庫方言加引號；**不可**把使用者輸入接進 SQL 字串。
- `%`、`_` 是一般字元（使用者查 `x_1` 不該變成萬用字元）。
- 一次查多個工號用 `IN (:a0, :a1, ...)`，不要逐筆查（名單頁一次要標示幾十個人）。
- 表很大時可請 DBA 在 `LOWER(empno)` 建索引；不要在平台端快取整張表。

## 3. 平台的名單表（Migration 建立）

以下是通用骨架：`<prefix>` 換成系統前綴，「範圍」換成你的業務單位（廠棟、部門、產線、專案…）。沒有範圍概念的平台就拿掉 `read_scopes`／`work_scopes`。依部署規範：流水號用 `GENERATED ALWAYS AS IDENTITY`，Migration 開頭先 `SET ROLE <owner>`。

```sql
-- 人員與權限：一個工號一列。姓名、Email 是儲存時從員工資料表帶入的快照（員工離職後頁面仍看得到是誰）。
CREATE TABLE <prefix>_person (
    account             VARCHAR(64)  PRIMARY KEY,            -- 工號，採用員工資料表的寫法
    display_name        VARCHAR(120) NOT NULL DEFAULT '',
    email               VARCHAR(200) NOT NULL DEFAULT '',
    active              BOOLEAN      NOT NULL DEFAULT TRUE,  -- 停用＝保留紀錄但不能登入使用
    roles               JSONB        NOT NULL DEFAULT '[]',  -- ["viewer","operator","admin"]
    read_scopes         JSONB        NOT NULL DEFAULT '[]',  -- 可檢視的範圍
    work_scopes         JSONB        NOT NULL DEFAULT '[]',  -- 可操作的範圍（必須包含在 read_scopes 內）
    supervisor_accounts JSONB        NOT NULL DEFAULT '[]',  -- 依序第一層、第二層主管工號（主管不必是平台使用者）
    version             INTEGER      NOT NULL DEFAULT 1,
    updated_by          VARCHAR(64)  NOT NULL DEFAULT '',
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 每次修改存一份完整快照＋理由；只新增不修改。
CREATE TABLE <prefix>_person_history (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account     VARCHAR(64)  NOT NULL,
    version     INTEGER      NOT NULL,
    snapshot    JSONB        NOT NULL,
    reason      TEXT         NOT NULL,
    changed_by  VARCHAR(64)  NOT NULL,
    view_as     VARCHAR(32)  NOT NULL DEFAULT '',  -- 管理員以「角色檢視模式」操作時記錄所檢視的角色
    changed_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (account, version)
);

-- 範圍負責人（需要「某範圍的負責人／通知對象」時才建）
CREATE TABLE <prefix>_scope_owner (
    scope            VARCHAR(40)  PRIMARY KEY,
    primary_account  VARCHAR(64)  NOT NULL,
    co_accounts      JSONB        NOT NULL DEFAULT '[]',
    version          INTEGER      NOT NULL DEFAULT 1,
    updated_by       VARCHAR(64)  NOT NULL DEFAULT '',
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE TABLE <prefix>_scope_owner_history (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope       VARCHAR(40)  NOT NULL,
    version     INTEGER      NOT NULL,
    snapshot    JSONB        NOT NULL,
    reason      TEXT         NOT NULL,
    changed_by  VARCHAR(64)  NOT NULL,
    view_as     VARCHAR(32)  NOT NULL DEFAULT '',
    changed_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 異動紀錄不可改、不可刪（資料庫層擋，不只靠程式）
CREATE FUNCTION <prefix>_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% 為不可變紀錄，不可修改或刪除', TG_TABLE_NAME;
END;
$$;
CREATE TRIGGER <prefix>_person_history_immutable BEFORE UPDATE OR DELETE ON <prefix>_person_history
    FOR EACH ROW EXECUTE FUNCTION <prefix>_reject_change();
CREATE TRIGGER <prefix>_scope_owner_history_immutable BEFORE UPDATE OR DELETE ON <prefix>_scope_owner_history
    FOR EACH ROW EXECUTE FUNCTION <prefix>_reject_change();
```

設計重點：

- **主鍵就是工號**。不另外發 user_id，也不用 AD 的 SID 或 GUID；登入（SSO 或帳密）解析出帳號後去掉網域（`DOMAIN\A1001` → `A1001`）直接查這張表。
- 角色用 JSON 陣列存在同一列即可（角色數量少、每次整列儲存、有版本號）。角色很多或需要「角色 × 範圍」各自不同時，改成 `<prefix>_role_assignment (account, role, scope)` 正規化表。
- 「多選清單」類設定（例如某功能的簽核人名單、通知名單）照同樣模式：一張表存工號陣列＋version，一張 history 表。
- SQLite 開發環境：JSONB 改 JSON（SQLAlchemy 的 `JSON` 型別兩邊都能用），觸發器改用 SQLite 語法或略過並在程式裡擋。

## 4. 稽核紀錄

權限相關的操作除了 history，也寫進平台的稽核表（例如 `<prefix>_audit_log`）：

| 動作 | 記錄 |
|---|---|
| 登入成功／失敗、登出 | 帳號、方式（SSO／帳密）、來源 IP |
| 被拒（403） | 帳號、路徑、需要的角色 |
| 新增／修改人員權限、範圍負責人 | 變更前後、理由、操作者、檢視角色 |
| 查詢員工資料表 | 一般不記（太多）；有個資疑慮時只記「誰、何時、查了幾次」，不記查詢字串 |

稽核表的讀寫群組只給 `INSERT`、`SELECT`；`UPDATE`／`DELETE`／`TRUNCATE` 由 DBA 撤銷。
