"""部署自我檢查（不寫入任何資料）。

目標主機沒有 Python（Nuitka 打包）時，由 exe 自己確認：
  - selfcheck：必要套件是否可載入（打包是否完整）、ODBC Driver
  - selfcheck --db：再加設定是否齊全、DNS／TCP 探測、資料庫實際連線、必要資料表存在、與資料庫主機的時間差

輸出只到畫面，不寫日誌、不顯示密碼。結束碼：0 全部通過、1 有項目失敗。

TODO(專案)：
  - REQUIRED_PACKAGES 加入本程式用到的第三方套件（編譯版漏帶時在這裡就會 FAIL）
  - REQUIRED_SQL_TABLES／REQUIRED_ORA_TABLES 填入本程式要讀寫的資料表
  - 需要檢查預建資料、設定值合理性時，寫在 _check_project()
"""

from __future__ import annotations

#{{#sqlserver}}
import os
#{{/sqlserver}}
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import __version__

MAX_CLOCK_SKEW_SEC = 5

# (顯示名稱, import 名稱, 取版本的屬性)
REQUIRED_PACKAGES: list[tuple[str, str, str]] = [
#{{#oracle}}
    ("oracledb", "oracledb", "__version__"),
    ("cryptography（oracledb thin 模式需要）", "cryptography", "__version__"),
#{{/oracle}}
#{{#sqlserver}}
    ("pyodbc", "pyodbc", "version"),
#{{/sqlserver}}
]
#{{#sqlserver}}
REQUIRED_SQL_TABLES: list[str] = []   # 例："dbo.MyTarget"（以 {{PREFIX}}_SQL_DATABASE 為資料庫）
#{{/sqlserver}}
#{{#oracle}}
REQUIRED_ORA_TABLES: list[str] = []   # 例："SCHEMA.MY_SOURCE"
#{{/oracle}}


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def ok(self, msg: str) -> None:
        print(f"[ OK ] {msg}")

    def fail(self, msg: str) -> None:
        self.failed += 1
        print(f"[FAIL] {msg}")

    def warn(self, msg: str) -> None:
        print(f"[WARN] {msg}")

    def step(self, name: str, fn: Callable[[], str]) -> None:
        try:
            self.ok(f"{name}：{fn()}")
        except Exception as exc:  # 檢查用途，任何錯誤都只回報
            self.fail(f"{name}：{type(exc).__name__}: {exc}")


def _skew(report: Report, name: str, server_now: datetime) -> None:
    diff = (server_now - datetime.now()).total_seconds()
    msg = f"{name} 與本機時間差 {diff:+.1f} 秒"
    if abs(diff) > MAX_CLOCK_SKEW_SEC:
        report.warn(msg + f"（超過 {MAX_CLOCK_SKEW_SEC} 秒，請確認時間同步）")
    else:
        report.ok(msg)


def run(check_db: bool, env_path: Optional[Path] = None) -> int:
    report = Report()
    compiled = "__compiled__" in globals()
    print(f"{{app}} {__version__}  Python {sys.version.split()[0]}  "
          f"{'Nuitka 編譯版' if compiled else '原始碼執行'}")
    print(f"設定來源：{env_path if env_path else '環境變數（未找到 .env）'}")

    print("\n== 套件 ==")
    for label, module, attr in REQUIRED_PACKAGES:
        report.step(label, lambda m=module, a=attr: str(getattr(__import__(m), a, "已載入")))
    if not REQUIRED_PACKAGES:
        report.ok("沒有第三方套件")
#{{#sqlserver}}

    def odbc_driver() -> str:
        import pyodbc

        from .odbc import detect

        installed = [d for d in pyodbc.drivers() if "SQL Server" in d]
        driver = detect(os.environ.get("{{PREFIX}}_SQL_DRIVER"))
        if driver.kind in ("snac", "legacy"):
            report.warn(f"使用 {driver.name}{driver.note}")
        return f"使用「{driver.name}」（本機 SQL Server 驅動：{installed}）"

    report.step("ODBC Driver", odbc_driver)
#{{/sqlserver}}

    if check_db:
        _check_db(report)

    print(f"\n結果：{'全部通過' if report.failed == 0 else f'{report.failed} 項失敗'}")
    return 0 if report.failed == 0 else 1


def _probe_tcp(report: Report, host: str, port: int) -> bool:
    """連資料庫前先測 DNS 與 TCP 埠，區分「名稱解析失敗／埠不通／帳密或權限問題」。"""
    import socket

    try:
        addrs = sorted({a[4][0] for a in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        report.ok(f"DNS：{host} → {', '.join(addrs)}")
    except OSError as exc:
        report.fail(f"DNS：無法解析主機名稱 {host}（{exc}）。改用 IP 或完整網域名稱（FQDN）")
        return False
    try:
        with socket.create_connection((host, port), timeout=5):
            report.ok(f"TCP：{host}:{port} 可連線")
        return True
    except OSError as exc:
        report.fail(f"TCP：{host}:{port} 連不上（{exc}）。確認埠號與防火牆")
        return False


def _check_db(report: Report) -> None:
    from .config import load_settings

    print("\n== 設定 ==")
    try:
        settings = load_settings()
#{{#sqlserver}}
        driver = settings.sql_driver()
        settings.sqlserver_connection_string(driver)
#{{/sqlserver}}
#{{#oracle}}
        ora = settings.oracle_params()
#{{/oracle}}
    except Exception as exc:
        report.fail(f"設定：{exc}")
        return
    report.ok(f"設定齊全（日誌 {settings.log_dir}，時間預算 {settings.time_budget_sec:g} 秒）")
#{{#sqlserver}}

    print("\n== SQL Server ==")
    from .config import sql_server_target

    server = sql_server_target(os.environ.get("{{PREFIX}}_SQL_SERVER", ""))
    server = server[4:] if server.lower().startswith("tcp:") else server
    host, _, port_text = server.partition(",")
    if "\\" in host and not port_text:
        name, _, instance = host.partition("\\")
        report.warn(f"具名執行個體 {instance}：需要 SQL Browser（UDP 1434）查詢埠號；連不上時改寫成「{name},<埠號>」")
    elif port_text.strip().isdigit():
        _probe_tcp(report, host.split("\\")[0].strip(), int(port_text))
    elif not port_text:
        _probe_tcp(report, host.strip(), 1433)
    else:
        report.fail(f"埠號不是數字：{port_text}")
    try:
        import pyodbc

        conn = pyodbc.connect(settings.sqlserver_connection_string(driver), timeout=10)
    except Exception as exc:
        report.fail(f"連線：{type(exc).__name__}: {exc}")
    else:
        try:
            cur = conn.cursor()
            cur.execute("SELECT GETDATE(), @@SERVERNAME")
            now, name = cur.fetchone()
            report.ok(f"連線 {name}（資料庫 {settings.sql_database}）")
            _skew(report, "SQL Server", now)
            for table in REQUIRED_SQL_TABLES:
                cur.execute("SELECT OBJECT_ID(?)", f"{settings.sql_database}.{table}")
                if cur.fetchone()[0] is None:
                    report.fail(f"資料表 {table} 不存在或無權限，請執行 sql\\ 下的建表腳本並確認授權")
                else:
                    report.ok(f"資料表 {table} 存在")
        except Exception as exc:
            report.fail(f"查詢：{type(exc).__name__}: {exc}")
        finally:
            conn.close()
#{{/sqlserver}}
#{{#oracle}}

    print("\n== Oracle ==")
    dsn_host, _, rest = ora["dsn"].partition(":")
    dsn_port = rest.partition("/")[0]
    if dsn_host and dsn_port.isdigit():
        _probe_tcp(report, dsn_host.strip(), int(dsn_port))
    try:
        import oracledb

        conn = oracledb.connect(**ora, tcp_connect_timeout=10)
    except Exception as exc:
        report.fail(f"連線：{type(exc).__name__}: {exc}")
    else:
        try:
            cur = conn.cursor()
            cur.execute("SELECT SYSDATE FROM dual")
            (now,) = cur.fetchone()
            report.ok(f"連線 {ora['dsn']}（{'thin' if oracledb.is_thin_mode() else 'thick'} 模式）")
            _skew(report, "Oracle", now)
            for table in REQUIRED_ORA_TABLES:
                owner, _, name = table.upper().rpartition(".")
                cur.execute("SELECT COUNT(*) FROM all_tables WHERE owner = :o AND table_name = :t",
                            o=owner or ora["user"].upper(), t=name)
                if cur.fetchone()[0]:
                    report.ok(f"資料表 {table} 可讀取")
                else:
                    report.fail(f"資料表 {table} 不存在或無權限，請 DBA 確認授權")
        except Exception as exc:
            report.fail(f"查詢：{type(exc).__name__}: {exc}")
        finally:
            conn.close()
#{{/oracle}}

    _check_project(report, settings)


def _check_project(report: Report, settings) -> None:
    """TODO(專案)：本程式特有的唯讀檢查，例如預建資料是否存在、設定值是否為正式值。"""
