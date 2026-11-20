"""命令列入口。

  python -m {{app}} --version            印出版本
  python -m {{app}} selfcheck [--db]     部署自我檢查（套件、ODBC；--db 再測設定、資料庫連線與時間差），不寫入
  python -m {{app}} dryrun [--out x.csv] 唯讀試算一輪，結果輸出 CSV，不寫入
  python -m {{app}} run                  正式執行（寫入）

Nuitka 打包後以 {{app}}.exe 取代 `python -m {{app}}`，參數相同。

結束碼：0 成功、1 部分失敗、2 整輪失敗（工作排程器的「上次執行結果」即為此值）。

TODO(專案)：需要時加上診斷命令（讀不到資料時的唯讀診斷）與 `run --cycle <時間>` 補跑（規範 §6.3 建議）。
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, envfile
from .config import ConfigError, Settings, load_settings
from .job import EXIT_FATAL, run_job

log = logging.getLogger("{{app}}")


def _setup_logging(settings: Settings, verbose: bool) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        settings.log_dir / "{{app}}.log", when="midnight", backupCount=90, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for handler in list(root.handlers):   # 同一程序內重複呼叫 main()（測試）時不重複輸出
        root.removeHandler(handler)
        handler.close()
    root.addHandler(file_handler)
    root.addHandler(console)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="{{app}}", description="{{description}}")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"{{app}} {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="正式執行（寫入）")

    dry = sub.add_parser("dryrun", help="唯讀試算，輸出 CSV，不寫入")
    dry.add_argument("--out", type=Path, help="輸出檔，預設 <log_dir>/dryrun/dryrun_<時間>.csv")

    chk = sub.add_parser("selfcheck", help="部署自我檢查，不寫入任何資料")
    chk.add_argument("--db", action="store_true", help="同時檢查設定、資料庫連線與時間差")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        env_path = envfile.load()
    except envfile.EnvFileError as exc:
        print(f"設定檔錯誤：{exc}", file=sys.stderr)
        return EXIT_FATAL
    if args.command == "selfcheck":
        from .selfcheck import run as selfcheck

        return selfcheck(args.db, env_path)
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"設定錯誤：{exc}", file=sys.stderr)
        return EXIT_FATAL
    _setup_logging(settings, args.verbose)
    log.debug("設定來源：%s", env_path or "環境變數（未使用 .env）")

    try:
        if args.command == "run":
            result = run_job(settings, commit=True)
        else:
            out = args.out or settings.log_dir / "dryrun" / f"dryrun_{datetime.now():%Y%m%d_%H%M%S}.csv"
            result = run_job(settings, commit=False, out_csv=out)
    except ConfigError as exc:
        log.error("設定錯誤：%s", exc)
        return EXIT_FATAL
    except Exception:
        log.exception("整輪失敗")
        return EXIT_FATAL

    log.info(result.summary(args.command))
    if result.elapsed > settings.time_budget_sec:
        log.warning("本輪耗時 %.1fs 超過預算 %.0fs", result.elapsed, settings.time_budget_sec)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
