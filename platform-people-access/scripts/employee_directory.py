"""公司員工資料表（例如 base.kh_ad_employees）的唯讀查詢：選人、核對工號、預填主管。

直接複製進專案使用（只依賴 SQLAlchemy 1.4／2.x）。整理自 GMS 監控平台 gms_app/domain/employees.py，
改成不綁 Flask：表名與欄位對應由呼叫端從設定傳入，不寫死欄位名稱。

    directory = EmployeeDirectory.from_settings(engine, os.environ.get("EMPLOYEE_TABLE"), settings.get("employees"))
    directory.search("王 一課")          # 工號／姓名／Email／部門／職稱，多個字詞須全部符合
    directory.find(["A1001", "b2001"])   # {工號(照傳入的寫法): Employee}，不分大小寫
    directory.supervisor_chain("A1001")  # 兩層主管預填
    directory.describe(["A1001", "X"])   # 給頁面標示「查無此工號」

規則（不要拿掉）：
- 只有 SELECT。這張表是全公司共用的，任何寫入都違反規範（部署助手 AUTH-10）。
- 表名、欄位名只接受識別字並由資料庫方言加引號；查詢值一律用參數，LIKE 的 % _ \\ 視為一般字元。
- 讀不到（沒授權、欄位對錯）時丟 EmployeeError，訊息說明要請 DBA 授權；呼叫端回 502／標示在頁面上，不要回 500。
- 用獨立的連線查詢：讀取失敗不會弄壞呼叫端正在進行的交易。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLUMNS = ("account", "name", "email", "department", "manager", "title")
REQUIRED = ("account", "name", "email")
SEARCHABLE = ("account", "name", "email", "department", "title")
SEARCH_LIMIT = 20
MAX_WORDS = 3


class EmployeeError(RuntimeError):
    """員工資料表有設定但讀不到（權限、欄位名稱錯誤），或設定本身不正確。"""


@dataclass
class Employee:
    account: str          # 工號
    name: str             # 姓名
    email: str = ""
    department: str = ""
    manager: str = ""     # 直屬主管工號
    title: str = ""       # 職稱

    def as_dict(self) -> dict:
        return asdict(self)


class EmployeeDirectory:
    def __init__(self, engine: Optional[Engine], table: str, columns: Mapping[str, Optional[str]],
                 active: Optional[Mapping] = None):
        self.engine = engine
        self.table = (table or "").strip()
        self.columns = {c: (columns or {}).get(c) or None for c in COLUMNS}
        self.active = active or None
        if self.configured:
            self._validate()

    @classmethod
    def from_settings(cls, engine: Optional[Engine], table: Optional[str], employees: Optional[Mapping]) -> "EmployeeDirectory":
        """employees = settings 的 {"columns": {...}, "active": {"column": ..., "values": [...]} 或 null}。"""
        employees = employees or {}
        return cls(engine, table or "", employees.get("columns") or {}, employees.get("active"))

    # ---- 設定 ----------------------------------------------------------------

    @property
    def configured(self) -> bool:
        """沒有設定表名時平台仍可運作（退回手動輸入並在頁面警告）。"""
        return bool(self.table)

    def _validate(self) -> None:
        parts = self.table.split(".")
        if len(parts) > 2 or not all(IDENTIFIER.match(p) for p in parts):
            raise EmployeeError(f"員工資料表名稱不正確：{self.table}（寫成 schema.table，例如 base.kh_ad_employees）")
        missing = [c for c in REQUIRED if not self.columns[c]]
        if missing:
            raise EmployeeError(f"缺少員工資料表欄位對應 employees.columns.{'、'.join(missing)}")
        for key, column in self.columns.items():
            if column and not IDENTIFIER.match(column):
                raise EmployeeError(f"employees.columns.{key} 不是合法的欄位名稱：{column}")
        if self.active:
            values = self.active.get("values") or []
            if not IDENTIFIER.match(self.active.get("column") or "") or not values:
                raise EmployeeError('employees.active 要寫成 {"column": 欄位, "values": [在職的值, ...]}')

    # ---- SQL -----------------------------------------------------------------

    def _quote(self, name: str) -> str:
        return self.engine.dialect.identifier_preparer.quote_identifier(name)

    def _select(self) -> tuple[str, dict]:
        table = ".".join(self._quote(p) for p in self.table.split("."))
        picked = ", ".join(f"{self._quote(self.columns[c])} AS {c}" if self.columns[c] else f"'' AS {c}" for c in COLUMNS)
        where, binds = "1 = 1", {}
        if self.active:   # 只列在職者，例如 {"column": "status", "values": ["在職"]}
            names = [f":active{i}" for i in range(len(self.active["values"]))]
            where = f"{self._quote(self.active['column'])} IN ({', '.join(names)})"
            binds = {f"active{i}": v for i, v in enumerate(self.active["values"])}
        return f"SELECT {picked} FROM {table} WHERE {where}", binds

    def _text_of(self, key: str) -> str:
        return f"LOWER(CAST({self._quote(self.columns[key])} AS VARCHAR(200)))"

    def _rows(self, sql: str, binds: dict) -> list[Employee]:
        if self.engine is None:
            raise EmployeeError("沒有資料庫連線")
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(text(sql), binds).mappings().all()
        except SQLAlchemyError as error:
            raise EmployeeError(f"員工資料表 {self.table} 無法讀取（{type(error).__name__}）；"
                                "請確認 DBA 已授權 SELECT，並用 check_employee_table.py 核對欄位對應") from error
        return [Employee(*(str(r[c] if r[c] is not None else "").strip() for c in COLUMNS)) for r in rows]

    # ---- 查詢 ----------------------------------------------------------------

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[Employee]:
        """工號、姓名、Email、部門、職稱部分比對、不分大小寫；每個字詞都要符合；依工號排序，最多 limit 筆。"""
        words = [w for w in re.split(r"\s+", (query or "").strip()) if w][:MAX_WORDS]
        if not words or not self.configured:
            return []
        sql, binds = self._select()
        fields = [self._text_of(c) for c in SEARCHABLE if self.columns[c]]
        for i, word in enumerate(words):
            escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").lower()
            binds[f"w{i}"] = f"%{escaped}%"
            sql += " AND (" + " OR ".join(f"{f} LIKE :w{i} ESCAPE '\\'" for f in fields) + ")"
        sql += f" ORDER BY {self._quote(self.columns['account'])}"
        return self._rows(sql, binds)[:limit]

    def find(self, accounts: Iterable[str]) -> dict[str, Employee]:
        """{照傳入寫法的工號: Employee}，只含表裡找得到的；工號比對不分大小寫。"""
        wanted = {a.strip().lower(): a for a in accounts if a and a.strip()}
        if not wanted or not self.configured:
            return {}
        sql, binds = self._select()
        names = [f":a{i}" for i in range(len(wanted))]
        binds.update({f"a{i}": key for i, key in enumerate(wanted)})
        sql += f" AND {self._text_of('account')} IN ({', '.join(names)})"
        return {wanted[e.account.lower()]: e for e in self._rows(sql, binds) if e.account.lower() in wanted}

    def supervisor_chain(self, account: str, levels: int = 2) -> dict:
        """新增人員時預填的主管：直屬主管、主管的主管。只是預填，管理員可以改；之後不跟著組織異動。

        主管不在表裡、或指回已出現過的人時停止，並在 note 說明。"""
        if not self.columns["manager"]:
            return {"supervisors": [], "note": "未設定 employees.columns.manager：主管請手動選取"}
        chain, note = [], ""
        current = self.find([account]).get(account)
        seen = {account.lower()}
        while current is not None and len(chain) < levels:
            manager = current.manager
            if not manager or manager.lower() in seen:
                break
            found = self.find([manager]).get(manager)
            if found is None:
                note = f"員工資料表查無主管工號 {manager}，請手動選取"
                break
            chain.append(found)
            seen.add(manager.lower())
            current = found
        if current is not None and not chain and not note:
            note = "員工資料表沒有此人的直屬主管，請手動選取"
        return {"supervisors": [{"account": e.account, "name": e.name, "found": True} for e in chain], "note": note}

    def describe(self, accounts: Iterable[str]) -> dict[str, dict]:
        """給頁面用：{工號: {"found": True, 姓名…} 或 {"found": False}}；沒設定表名時回空 dict。"""
        accounts = list(dict.fromkeys(a for a in accounts if a))
        if not self.configured:
            return {}
        found = self.find(accounts)
        return {a: ({"found": True, **found[a].as_dict()} if a in found else {"found": False}) for a in accounts}

    def table_columns(self) -> list[str]:
        """這張表實際的欄位（設定錯誤時列給使用者看）。"""
        from sqlalchemy import inspect

        schema, _, name = self.table.rpartition(".")
        return [c["name"] for c in inspect(self.engine).get_columns(name, schema=schema or None)]
