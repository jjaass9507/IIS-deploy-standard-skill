# 後端：權限判斷、管理 API、儲存規則

程式以 Flask＋Flask-SQLAlchemy 示範（整理自 GMS 監控平台 `gms_app/auth/*`、`gms_app/api/admin.py`、`gms_app/domain/people.py`）。FastAPI 寫法見最後一節。`<prefix>` 是系統前綴，「範圍（scope）」換成你的業務單位。

## 1. 角色

```python
# myapp/auth/roles.py
VIEWER, OPERATOR, ADMIN = "viewer", "operator", "admin"
ALL_ROLES = (VIEWER, OPERATOR, ADMIN)
ROLE_LABELS = {VIEWER: "檢視者", OPERATOR: "操作人員", ADMIN: "系統管理員"}
VIEWABLE_ROLES = (VIEWER, OPERATOR)   # 管理員可以「以某角色檢視」的角色
```

角色**要不要往下包含**（管理員 ⊃ 操作 ⊃ 檢視）是專案決定，寫進專案的決策紀錄。GMS 的決定是「不包含，只有系統管理員擁有全部」——例如專家不自動有工程師的操作權。不論哪種，都在 `has_role` 一個地方實作，不要散在各 API 裡。

## 2. 每個請求重新算權限

Session 只存「誰登入、怎麼登入」，**不存角色**。角色與範圍每個請求從 `<prefix>_person` 讀，管理員改了權限下一個請求就生效，不必重新登入。

```python
# myapp/auth/core.py
from dataclasses import dataclass, field
from flask import current_app, g, has_request_context, session

from myapp.auth.roles import ADMIN, ALL_ROLES, OPERATOR, ROLE_LABELS, VIEWABLE_ROLES
from myapp.extensions import db
from myapp.models import Person

SESSION_USER, SESSION_VIEW_AS = "user", "view_as"


@dataclass
class Principal:
    account: str
    display_name: str
    email: str
    auth_type: str                 # "sso" / "password" / "mock"
    roles: frozenset
    read_scopes: frozenset
    work_scopes: frozenset
    real_roles: frozenset          # 檢視模式下仍知道本人真正的角色
    view_as: dict | None = None
    all_scopes: tuple = field(default_factory=tuple)

    @property
    def is_admin(self): return ADMIN in self.roles
    def has_role(self, role): return self.is_admin or role in self.roles
    def can_read(self, scope): return self.is_admin or scope in self.read_scopes
    def can_work(self, scope): return self.is_admin or (OPERATOR in self.roles and scope in self.work_scopes)

    def public(self) -> dict:      # /api/auth/me 回傳這個，前端據以停用按鈕（後端仍要擋）
        roles = sorted(self.roles, key=ALL_ROLES.index)
        return {"account": self.account, "display_name": self.display_name, "email": self.email,
                "auth_type": self.auth_type, "roles": roles, "role_labels": [ROLE_LABELS[r] for r in roles],
                "read_scopes": [s for s in self.all_scopes if self.can_read(s)],
                "work_scopes": [s for s in self.all_scopes if self.can_work(s)],
                "is_admin": self.is_admin, "can_view_as": ADMIN in self.real_roles, "view_as": self.view_as}


def _bootstrap_admin(account: str) -> bool:
    """.env 的 AUTH_ADMIN_ACCOUNTS：新安裝時第一個管理員、名單表讀不到時的緊急入口。"""
    return account.lower() in {a.strip().lower() for a in current_app.config.get("AUTH_ADMIN_ACCOUNTS") or ()}


def build_principal(account, display_name, email, auth_type, view_as) -> "Principal":
    everything = tuple(current_app.config["ALL_SCOPES"])
    person = db.session.get(Person, account)
    roles, read, work = set(), set(), set()
    if person and person.active:
        roles = {r for r in person.roles if r in ALL_ROLES}
        read = set(person.read_scopes or [])
        work = set(person.work_scopes or []) & read
        display_name, email = person.display_name or display_name, person.email or email
    if _bootstrap_admin(account):
        roles.add(ADMIN)
    if ADMIN in roles:
        read = work = set(everything)
    real = frozenset(roles)
    if view_as and ADMIN in real and view_as.get("role") in VIEWABLE_ROLES:   # 角色檢視模式
        scope = set(view_as.get("scopes") or everything) & set(everything)
        roles, read = {view_as["role"]}, scope
        work = scope if view_as["role"] == OPERATOR else set()
    else:
        view_as = None
    return Principal(account, display_name, email, auth_type, frozenset(roles), frozenset(read),
                     frozenset(work), real, view_as, everything)


def current_user():
    if not has_request_context():
        return None
    if "user" not in g:
        stored = session.get(SESSION_USER)
        g.user = build_principal(stored["account"], stored.get("display_name", ""), stored.get("email", ""),
                                 stored.get("auth_type", ""), session.get(SESSION_VIEW_AS)) if stored else None
    return g.user


def actor() -> tuple[str, str]:
    """(操作者工號, 檢視角色)：寫業務紀錄與稽核時用。檢視模式下仍記本人。"""
    user = current_user()
    return (user.account, user.view_as["role"] if user and user.view_as else "") if user else ("system", "")
```

登入時（SSO 或帳密，見 `python-iis-deploy-standard`）只做：

```python
session.clear(); session.permanent = True
session[SESSION_USER] = {"account": plain_account, "display_name": name, "email": email, "auth_type": "sso"}
```

`plain_account` 是去掉網域的工號（`DOMAIN\A1001`、`a1001@corp` → `A1001`）。姓名、Email 優先用 `<prefix>_person` 的快照，沒有才用員工資料表／AD 查到的。

**AD 登入成功 ≠ 有權限**：名單裡沒有（或已停用）的人，`roles` 是空的，所有業務 API 回 403「您的帳號沒有本系統的使用權限，請聯絡系統管理員」。角色**不從 AD 群組**來。

## 3. API 一律在後端擋

```python
# myapp/auth/permissions.py
from functools import wraps
from flask import jsonify
from myapp.auth.core import current_user
from myapp.auth.roles import ROLE_LABELS


def deny(error, message, **extra):
    # 一律 403，不用 401：IIS 開了 Windows 驗證時，401 會讓瀏覽器跳出帳密視窗。
    return jsonify({"error": error, "message": message, **extra}), 403


def _signed_in():
    user = current_user()
    if not user:
        return None, deny("login_required", "請先登入。")
    if not user.roles:
        return None, deny("no_access", "您的帳號沒有本系統的使用權限，請聯絡系統管理員。")
    return user, None


def require_login(view):
    @wraps(view)
    def wrapper(*a, **kw):
        _, refused = _signed_in()
        return refused or view(*a, **kw)
    return wrapper


def require_role(*roles):
    def decorate(view):
        @wraps(view)
        def wrapper(*a, **kw):
            user, refused = _signed_in()
            if refused:
                return refused
            if not any(user.has_role(r) for r in roles):
                return deny("forbidden", f"需要「{'或'.join(ROLE_LABELS[r] for r in roles)}」權限才能執行此操作。",
                            required_role=list(roles))
            return view(*a, **kw)
        return wrapper
    return decorate


def check_work(scope):
    """範圍檢查要在 API 裡、拿到資料的範圍之後做（裝飾器不知道這筆資料屬於哪個範圍）。"""
    if not current_user().can_work(scope):
        return deny("forbidden_scope", f"您沒有 {scope} 的操作權限。")
    return None
```

- 新 API 預設要掛 `require_login`；只有 `/health`、`/version`、`/auth/*` 例外。
- 清單 API 依 `user.read_scopes` 過濾，不是回全部再讓前端藏。
- 前端用 `/api/auth/me` 的結果停用按鈕並寫出「需要 X 權限」，但那只是體驗；真正的檢查在這裡。

## 4. 員工資料表接進 app

```python
# myapp/employees.py
import os
from flask import current_app
from employee_directory import EmployeeDirectory, EmployeeError  # scripts/employee_directory.py 複製進專案

def directory() -> EmployeeDirectory:
    if "employee_directory" not in current_app.extensions:
        current_app.extensions["employee_directory"] = EmployeeDirectory.from_settings(
            db.engine, current_app.config.get("EMPLOYEE_TABLE"), current_app.config.get("EMPLOYEES") or {})
    return current_app.extensions["employee_directory"]
```

設定錯誤（欄位對應缺、表名不合法）時 `from_settings` 就會丟 `EmployeeError`；在 app 啟動時呼叫一次並寫進 log，或在 `/health` 的細項標示，不要讓整個網站起不來（平台沒有員工表仍應可用）。

## 5. 管理 API

| 方法與路徑 | 角色 | 用途 |
|---|---|---|
| `GET /api/admin/employees?q=` | 系統管理員 | 選人元件的搜尋；回 `{results:[{account,name,email,department,title,manager,is_person}], limited}` |
| `GET /api/admin/employees/<account>/supervisors` | 系統管理員 | 新增人員時預填兩層主管 `{supervisors:[{account,name,found}], note}` |
| `GET /api/admin/people` | 系統管理員 | 名單；每人附 `directory`（員工表現況：`{found:false}` 表示查無此工號）；頁面層級附 `employee_table:{configured, problem}` |
| `PUT /api/admin/people/<account>` | 系統管理員 | 新增或修改；body 含 `roles`、`read_scopes`、`work_scopes`、`supervisor_accounts`、`active`、`reason` |
| `GET /api/admin/people/<account>/history` | 系統管理員 | 版本紀錄（快照、理由、誰、何時） |
| `GET /api/<業務>/candidates` | 依業務 | 「必須是平台使用者」的欄位（例如指派處理人）的候選：從 `<prefix>_person` 篩，回傳格式與員工搜尋相同，前端用同一個元件 |

**搜尋員工只開放給需要設定人員的角色**（通常只有系統管理員）。員工資料表是全公司通訊錄，不要讓檢視者拿來查人。若一般使用者也要選人（例如申請單選簽核主管），另開一支只回 `account,name,department` 的 API，並在稽核記錄使用次數。

```python
@api_bp.get("/admin/employees")
@require_role(ADMIN)
def search_employees():
    d = directory()
    if not d.configured:
        return jsonify({"error": "not_configured", "message": "未設定 EMPLOYEE_TABLE：無法查詢員工資料表"}), 409
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": [], "message": "請輸入工號、姓名或部門"})
    try:
        found = d.search(query)
    except EmployeeError as error:
        return jsonify({"error": "employee_table", "message": str(error)}), 502   # 不要 500
    existing = {p.account.lower() for p in Person.query.filter(Person.account.in_([e.account for e in found]))} if found else set()
    return jsonify({"results": [{**e.as_dict(), "is_person": e.account.lower() in existing} for e in found],
                    "limited": len(found) >= SEARCH_LIMIT})


@api_bp.get("/admin/people")
@require_role(ADMIN)
def list_people():
    people = Person.query.order_by(Person.account).all()
    wanted = [p.account for p in people] + [s for p in people for s in p.supervisor_accounts or []]
    try:
        info, problem = directory().describe(wanted), ""          # 一次查完，不要逐人查
    except EmployeeError as error:
        info, problem = {}, str(error)                            # 員工表壞了名單頁仍要能開
    rows = []
    for p in people:
        row = person_dict(p)
        row["directory"] = info.get(p.account)                    # None＝沒設定員工表；{"found": False}＝查無此工號
        row["supervisors"] = [{"account": s, "name": (info.get(s) or {}).get("name", ""), "found": (info.get(s) or {}).get("found")}
                              for s in p.supervisor_accounts or []]
        rows.append(row)
    return jsonify({"people": rows, "scopes": list(current_user().all_scopes),
                    "employee_table": {"configured": directory().configured, "problem": problem}})
```

## 6. 儲存人員的規則（`save_person`）

全部在後端驗證，違反時回 422＋中文訊息、整筆 rollback：

1. 必須填**修改理由**。
2. 角色只能是 `ALL_ROLES` 裡的值；範圍只能是設定裡有的範圍；`work_scopes ⊆ read_scopes`。
3. **身分以員工資料表為準**（有設定員工表時）：
   - 新工號不在員工表 → 拒絕「員工資料表查無工號 X，請從員工清單選取」。
   - 姓名、Email **由伺服器重新查表帶入**，表單送來的 `display_name`、`email` 一律不採用。
   - 新人員的工號採用員工表的大小寫寫法。
   - 主管工號也要在員工表裡；主管不能是本人；最多兩層。
4. 已在名單、但員工表已查無的人（離職、調動）：**權限保留**、姓名與 Email 維持上次快照，頁面標示「查無此工號」，由管理員決定是否停用。**不要**自動停用或刪除。
5. 自我保護：不能停用自己、不能移除自己的系統管理員；停用或降級最後一位啟用中的系統管理員時拒絕（有 `AUTH_ADMIN_ACCOUNTS` 時可放行）。
6. 業務關聯：仍是某範圍主要負責人的人不能停用（先換負責人）。
7. 寫入：`SELECT ... FOR UPDATE` 鎖該列 → 更新 → `version + 1`、`updated_by`、`updated_at` → 新增一筆 history（完整快照＋理由＋操作者＋檢視角色）→ 寫稽核。
8. 沒設定員工表時才接受表單的姓名與 Email，頁面明確警告「未設定 EMPLOYEE_TABLE，無法核對是誰」。

範圍負責人（`save_owner`）：負責人必須是**啟用中的平台人員**、有 Email、且對該範圍有檢視權限；同樣要理由、版本與 history。

## 7. 通知收件者

```python
def recipients(accounts: list[str]) -> list[dict]:
    """平台人員用名單裡的快照（停用的人不寄）；不是平台人員的（例如只收升級通知的主管）查員工資料表。"""
    accounts = list(dict.fromkeys(a for a in accounts if a))
    persons = {a: db.session.get(Person, a) for a in accounts}
    try:
        others = directory().find([a for a, p in persons.items() if p is None])
    except EmployeeError:
        others = {}   # 員工表讀不到時其他人照寄，不要整批失敗
    rows = []
    for a in accounts:
        p, e = persons[a], others.get(a)
        if p is not None:
            rows.append({"account": a, "name": p.display_name, "email": p.email if p.active else ""})
        else:
            rows.append({"account": a, "name": e.name if e else "", "email": e.email if e else ""})
    return rows
```

## 8. FastAPI 寫法

把裝飾器換成 dependency，其餘相同：

```python
from fastapi import Depends, HTTPException, Request

def principal(request: Request) -> Principal:
    stored = request.session.get("user")
    if not stored:
        raise HTTPException(403, {"error": "login_required", "message": "請先登入。"})
    user = build_principal(**stored, view_as=request.session.get("view_as"))
    if not user.roles:
        raise HTTPException(403, {"error": "no_access", "message": "您的帳號沒有本系統的使用權限，請聯絡系統管理員。"})
    return user

def require_role(*roles):
    def check(user: Principal = Depends(principal)) -> Principal:
        if not any(user.has_role(r) for r in roles):
            raise HTTPException(403, {"error": "forbidden", "required_role": list(roles)})
        return user
    return check

@router.get("/api/admin/employees")
def search_employees(q: str = "", user: Principal = Depends(require_role(ADMIN))): ...
```

`EmployeeDirectory` 本身是同步的；在 async 路由裡用 `run_in_threadpool` 呼叫，或直接把路由寫成 `def`。
