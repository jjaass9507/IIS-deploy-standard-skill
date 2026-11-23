"""核對平台帳號能不能讀員工資料表、欄位對應對不對。部署後在伺服器上用平台的服務帳號執行。

    python check_employee_table.py --settings settings.json
    python check_employee_table.py --table base.kh_ad_employees --columns '{"account":"empno","name":"empname","email":"email"}'

連線字串讀 --database-url 或環境變數 DATABASE_URL；表名讀 --table 或 EMPLOYEE_TABLE。
--settings 指向含 "employees": {"columns": {...}, "active": ...} 的 JSON。
--search 可順便試查一次（例如 --search 王）。結束碼：0 正常、1 有問題、2 參數錯誤。
只做 SELECT，不會寫入任何資料。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from employee_directory import REQUIRED, EmployeeDirectory, EmployeeError  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="核對員工資料表的讀取權限與欄位對應")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--table", default=os.environ.get("EMPLOYEE_TABLE", ""))
    parser.add_argument("--settings", help="含 employees 區段的 JSON 設定檔")
    parser.add_argument("--columns", help='欄位對應 JSON，例如 {"account":"empno","name":"empname","email":"email"}')
    parser.add_argument("--rw-role", default=os.environ.get("DATABASE_RW_ROLE", "<prefix>_rw"),
                        help="要授權的群組（印在授權 SQL 裡），預設讀 DATABASE_RW_ROLE")
    parser.add_argument("--search", help="試查一次")
    args = parser.parse_args(argv)

    employees = {}
    if args.settings:
        with open(args.settings, encoding="utf-8") as f:
            employees = json.load(f).get("employees") or {}
    if args.columns:
        employees = {**employees, "columns": json.loads(args.columns)}
    if not args.database_url or not args.table:
        print("需要 --database-url（或 DATABASE_URL）與 --table（或 EMPLOYEE_TABLE）")
        return 2

    from sqlalchemy import create_engine, func, select, table as sa_table
    from sqlalchemy.engine import make_url

    engine = create_engine(args.database_url)
    user = make_url(args.database_url).username or "<平台帳號>"
    schema, _, name = args.table.rpartition(".")
    try:
        directory = EmployeeDirectory.from_settings(engine, args.table, {**employees, "columns": employees.get("columns") or {"account": "x", "name": "x", "email": "x"}})
    except EmployeeError as error:
        print(f"[錯誤] {error}")
        return 1
    try:
        with engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(sa_table(name, schema=schema or None))).scalar()
        actual = directory.table_columns()
    except Exception as error:  # noqa: BLE001 - 任何錯誤都要轉成給 DBA 的說明
        print(f"[錯誤] 員工資料表 {args.table} 無法讀取（{type(error).__name__}，連線帳號 {user}）")
        print("請 DBA 對平台的讀寫群組授權（不是對個人帳號）：")
        print(f"  GRANT USAGE ON SCHEMA {schema or 'public'} TO {args.rw_role};")
        print(f"  GRANT SELECT ON {args.table} TO {args.rw_role};")
        return 1
    listed = "、".join(actual) or "（查不到欄位清單）"
    print(f"[正常] {args.table} 可讀取，共 {count} 筆；欄位：{listed}")

    columns = employees.get("columns") or {}
    if not all(columns.get(c) for c in REQUIRED):
        print(f"[錯誤] 尚未設定欄位對應 employees.columns（必填 {'、'.join(REQUIRED)}）；請從上面的欄位挑選")
        return 1
    wrong = [f"{k}={v}" for k, v in columns.items() if v and actual and v not in actual]
    if wrong:
        print(f"[錯誤] 欄位對應不在表裡：{'、'.join(wrong)}")
        return 1
    print("[正常] 欄位對應：" + "、".join(f"{k}→{v}" for k, v in columns.items() if v))
    if not columns.get("manager"):
        print("[提示] 沒有 manager 欄位：新增人員時不會預填主管")

    if args.search:
        try:
            found = EmployeeDirectory.from_settings(engine, args.table, employees).search(args.search)
        except EmployeeError as error:
            print(f"[錯誤] {error}")
            return 1
        print(f"[試查] 「{args.search}」找到 {len(found)} 筆")
        for e in found[:5]:
            print(f"  {e.account}  {e.name}  {e.department}  {e.email or '無 Email'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
