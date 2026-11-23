"""employee_directory.py 的範例測試（SQLite，不需要公司資料庫）。複製進專案時一起帶走。

    python -m pytest -q assets/tests
"""
import os
import sys

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from check_employee_table import main as check_main  # noqa: E402
from employee_directory import EmployeeDirectory, EmployeeError  # noqa: E402

# 實際的表用自己的欄位名稱；設定裡的對應說明哪個是哪個。
COLUMNS = {"account": "emp_no", "name": "emp_name", "email": "mail", "department": "dept", "manager": "boss", "title": "job"}
STAFF = [("A1001", "王小明", "a1001@x", "廠務一課", "工程師", "在職", "B2001"),
         ("A1002", "李大華", "a1002@x", "廠務一課", "工程師", "在職", "Z0000"),
         ("B2001", "陳主任", "b2001@x", "廠務部", "主任", "在職", "D4001"),
         ("C3001", "林離職", "c3001@x", "廠務一課", "工程師", "離職", "B2001"),
         ("A1003", "張無信", None, "廠務二課", "技術員", "在職", "A1003"),
         ("D4001", "黃經理", "d4001@x", "廠務處", "經理", "在職", "E5001"),
         ("E5001", "周協理", "e5001@x", "製造中心", "協理", "在職", None),
         ("X_100", "底線測試", "x@x", "測試課", "", "在職", None)]


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'hr.db'}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE kh_ad_employees (emp_no TEXT, emp_name TEXT, mail TEXT, dept TEXT, job TEXT, status TEXT, boss TEXT)"))
        c.execute(text("INSERT INTO kh_ad_employees VALUES (:a, :n, :m, :d, :j, :s, :b)"),
                  [dict(zip("anmdjsb", row)) for row in STAFF])
    yield engine
    engine.dispose()


def directory(engine, **kw):
    return EmployeeDirectory(engine, "kh_ad_employees", kw.pop("columns", COLUMNS), **kw)


def names(d, q):
    return [e.name for e in d.search(q)]


def test_search_matches_every_word_case_insensitive(engine):
    d = directory(engine)
    assert names(d, "a100") == ["王小明", "李大華", "張無信"]
    assert names(d, "一課 李") == ["李大華"]          # 多個字詞要全部符合
    assert names(d, "陳") == ["陳主任"]               # 一個字就能查（中文姓氏）
    assert names(d, "d4001@") == ["黃經理"]           # Email
    assert names(d, "協理") == ["周協理"]             # 職稱
    assert names(d, "") == [] and names(d, "   ") == []


def test_like_wildcards_are_literal(engine):
    d = directory(engine)
    assert names(d, "%") == []
    assert names(d, "x_1") == ["底線測試"]
    assert names(d, "a_00") == []


def test_limit(engine):
    assert len(directory(engine).search("@", limit=2)) == 2


def test_find_ignores_case_and_keeps_callers_spelling(engine):
    found = directory(engine).find(["a1001", "B2001", "NOBODY", ""])
    assert set(found) == {"a1001", "B2001"}
    assert found["a1001"].account == "A1001" and found["a1001"].email == "a1001@x"
    assert directory(engine).find(["A1003"])["A1003"].email == ""   # NULL 變空字串


def test_active_filter_hides_people_who_left(engine):
    d = directory(engine, active={"column": "status", "values": ["在職"]})
    assert [e.account for e in d.search("一課")] == ["A1001", "A1002"]
    assert d.find(["C3001"]) == {}


def test_supervisor_chain(engine):
    d = directory(engine)
    first = d.supervisor_chain("A1001")
    assert [(s["account"], s["name"]) for s in first["supervisors"]] == [("B2001", "陳主任"), ("D4001", "黃經理")]
    assert first["note"] == ""
    assert [s["account"] for s in d.supervisor_chain("D4001")["supervisors"]] == ["E5001"]   # 最上層只有一層
    missing = d.supervisor_chain("A1002")
    assert missing["supervisors"] == [] and "Z0000" in missing["note"]
    assert d.supervisor_chain("A1003")["supervisors"] == []                                    # 指回自己
    no_column = directory(engine, columns={k: v for k, v in COLUMNS.items() if k != "manager"})
    assert "manager" in no_column.supervisor_chain("A1001")["note"]


def test_describe_flags_unknown_accounts(engine):
    out = directory(engine).describe(["A1001", "GONE"])
    assert out["A1001"]["found"] and out["A1001"]["department"] == "廠務一課"
    assert out["GONE"] == {"found": False}
    assert EmployeeDirectory(engine, "", {}).describe(["A1001"]) == {}    # 沒設定表名：平台照常運作


def test_bad_settings_are_refused_before_any_sql(engine):
    with pytest.raises(EmployeeError, match="email"):
        EmployeeDirectory(engine, "kh_ad_employees", {"account": "emp_no", "name": "emp_name"})
    with pytest.raises(EmployeeError, match="欄位名稱"):
        EmployeeDirectory(engine, "kh_ad_employees", {**COLUMNS, "name": "emp_name; DROP TABLE x"})
    with pytest.raises(EmployeeError, match="schema.table"):
        EmployeeDirectory(engine, "base.kh;drop", COLUMNS)
    with pytest.raises(EmployeeError, match="employees.active"):
        EmployeeDirectory(engine, "kh_ad_employees", COLUMNS, active={"column": "status", "values": []})


def test_unreadable_table_raises_employee_error(engine):
    d = EmployeeDirectory(engine, "no_such_table", COLUMNS)
    with pytest.raises(EmployeeError, match="無法讀取"):
        d.search("A1001")


def test_check_script_reports_missing_mapping(engine, tmp_path, capsys):
    url = str(engine.url)
    assert check_main(["--database-url", url, "--table", "kh_ad_employees"]) == 1
    assert "emp_no" in capsys.readouterr().out                       # 列出實際欄位讓人挑
    import json
    assert check_main(["--database-url", url, "--table", "kh_ad_employees", "--columns", json.dumps(COLUMNS), "--search", "王"]) == 0
    assert "王小明" in capsys.readouterr().out
    assert check_main(["--database-url", url, "--table", "nope", "--columns", json.dumps(COLUMNS)]) == 1
    assert "GRANT SELECT ON nope" in capsys.readouterr().out
