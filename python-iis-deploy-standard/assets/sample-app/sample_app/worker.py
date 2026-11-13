"""背景服務（由 WinSW 管理的常駐程式）：python -m sample_app.worker

每個週期做一次工作，並把最後成功時間與版本寫到 APP_DATA_DIR\\worker-status.json。
"""
import json
import logging
import signal
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from . import config

INTERVAL_SECONDS = 60
log = logging.getLogger("sample_app.worker")
_stop = False


def _on_signal(signum, frame):
    global _stop
    _stop = True


def run_once():
    """實際的工作放在這裡；需設計成重複執行也不會出錯（冪等）。"""
    status = {"scheduler": "running", "version": config.APP_VERSION, "last_success": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    target = config.data_dir() / "worker-status.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    temp.replace(target)


def main():
    config.check_production()
    handler = RotatingFileHandler(config.log_dir() / "worker.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    log.info("worker start version=%s", config.APP_VERSION)
    next_run = 0.0
    while not _stop:
        if time.monotonic() >= next_run:
            try:
                run_once()
            except Exception:
                log.exception("run_once failed")
            next_run = time.monotonic() + INTERVAL_SECONDS
        time.sleep(1)
    log.info("worker stop")


if __name__ == "__main__":
    main()
