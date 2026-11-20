"""本程式的業務邏輯。

架構（規範 §6：先唯讀、後寫入；錯誤不能靜默）：
  open_connections()  依設定開啟資料庫連線，交給 ExitStack 在結束時關閉
  collect()           **只讀**：從來源讀資料、計算出要寫入的列。dryrun 與 run 共用同一段
  write()             **寫入**：只有 run 會呼叫；逐筆處理，單筆失敗記 ERROR 並計數，其餘繼續
  run_job()           串起來：dryrun 輸出 CSV、run 寫入；回傳 Result（摘要與結束碼）

TODO(專案)：實作 collect() 與 write()。SQL 一律參數化；表名、欄位名只能來自程式內白名單。
"""

from __future__ import annotations

import csv
import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import Settings

log = logging.getLogger(__name__)

EXIT_OK = 0        # 成功
EXIT_PARTIAL = 1   # 部分失敗（其餘已完成）
EXIT_FATAL = 2     # 整輪失敗（設定、連線、未預期例外）


@dataclass
class Result:
    rows: int = 0
    written: int = 0
    errors: int = 0
    elapsed: float = 0.0

    @property
    def exit_code(self) -> int:
        return EXIT_PARTIAL if self.errors else EXIT_OK

    def summary(self, mode: str) -> str:
        """每輪固定格式的一行摘要（規範 §6.4），維運以此判斷是否正常。"""
        return (f"[{mode}] rows={self.rows} written={self.written} "
                f"errors={self.errors} elapsed={self.elapsed:.1f}s")


def open_connections(settings: Settings, stack: ExitStack) -> dict[str, Any]:
    """開啟本程式需要的連線。連線失敗直接拋出（由呼叫端記錄並以 EXIT_FATAL 結束）。"""
    conns: dict[str, Any] = {}
#{{#sqlserver}}
    import pyodbc

    driver = settings.sql_driver()
    log.debug("SQL Server 驅動：%s%s", driver.name, driver.note)
    sql = pyodbc.connect(settings.sqlserver_connection_string(driver), timeout=30, autocommit=False)
    stack.callback(sql.close)
    conns["sql"] = sql
#{{/sqlserver}}
#{{#oracle}}
    import oracledb

    ora = oracledb.connect(**settings.oracle_params(), tcp_connect_timeout=30)
    stack.callback(ora.close)
    conns["ora"] = ora
#{{/oracle}}
    return conns


def collect(settings: Settings, conns: dict[str, Any]) -> list[dict[str, Any]]:
    """唯讀：讀來源、計算要寫入的列。不得有任何寫入。

    TODO(專案)：改成實際的查詢與計算。每一列是一個 dict，dryrun 會原樣輸出成 CSV 的一列，
    欄位請包含足以對照來源的鍵值（時間、代號…）。
    """
    raise NotImplementedError("尚未實作 job.collect()：請依專案需求讀取來源資料")


def write(settings: Settings, conns: dict[str, Any], rows: list[dict[str, Any]], result: Result) -> None:
    """寫入：逐筆處理，單筆失敗不中斷整輪，但一定要記 ERROR 並計入 result.errors。

    TODO(專案)：改成實際的寫入（參數化 SQL），並決定 commit 的粒度。
    """
    for row in rows:
        try:
            _write_one(conns, row)
        except Exception:
            result.errors += 1
            log.error("寫入失敗：%s", row, exc_info=True)
        else:
            result.written += 1


def _write_one(conns: dict[str, Any], row: dict[str, Any]) -> None:
    """TODO(專案)：寫入一列，例如 cur.execute("UPDATE dbo.X SET v = ? WHERE k = ?", row["v"], row["k"]) 後 commit。"""
    raise NotImplementedError("尚未實作 job._write_one()")


def run_job(settings: Settings, *, commit: bool, out_csv: Optional[Path] = None) -> Result:
    """執行一輪。commit=False 為 dryrun：只讀、輸出 CSV，不寫入任何資料。"""
    started = time.monotonic()
    result = Result()
    with ExitStack() as stack:
        conns = open_connections(settings, stack)
        rows = collect(settings, conns)
        result.rows = len(rows)
        if out_csv is not None:
            write_csv(out_csv, rows)
            log.info("dryrun 結果：%s", out_csv)
        if commit:
            write(settings, conns, rows, result)
    result.elapsed = time.monotonic() - started
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        fields.extend(k for k in row if k not in fields)
    # utf-8-sig：Excel 直接開啟中文不亂碼
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
