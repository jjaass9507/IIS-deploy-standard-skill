import csv
import io
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from {{app}} import __version__, job
from {{app}}.__main__ import main


def _close_log_handlers():
    root = logging.getLogger()
    for handler in list(root.handlers):   # Windows 上日誌檔開著會無法刪除暫存目錄
        root.removeHandler(handler)
        handler.close()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(_close_log_handlers)
        d = Path(self.tmp.name)
        (d / ".env").write_text("", encoding="utf-8")   # 不讀到開發者自己的 .env
        self.env = {"{{PREFIX}}_ENV_FILE": str(d / ".env"), "{{PREFIX}}_LOG_DIR": str(d / "logs"),
                    "{{PREFIX}}_SQL_DATABASE": "db"}
        patcher = mock.patch.object(job, "open_connections", return_value={})   # 不連資料庫
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *argv, env=None):
        with mock.patch.dict(os.environ, self.env if env is None else env, clear=True), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_version(self):
        with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), f"{{app}} {__version__}")

    def test_selfcheck_needs_no_settings(self):
        # 目標主機剛安裝、尚未設定時也要能執行 selfcheck（套件缺少時回 1，不拋例外）
        code, out = self.run_main("selfcheck", env={"{{PREFIX}}_ENV_FILE": self.env["{{PREFIX}}_ENV_FILE"]})
        self.assertIn(code, (0, 1))
        self.assertIn(f"{{app}} {__version__}", out)

    def test_dryrun_writes_csv_and_never_writes_db(self):
        out_csv = Path(self.tmp.name) / "out.csv"
        rows = [{"key": "A", "value": 1}, {"key": "B", "value": 2}]
        with mock.patch.object(job, "collect", return_value=rows), \
                mock.patch.object(job, "write") as write:
            code, out = self.run_main("dryrun", "--out", str(out_csv))
        self.assertEqual(code, 0, out)
        write.assert_not_called()
        with out_csv.open(encoding="utf-8-sig", newline="") as fh:
            self.assertEqual([r["key"] for r in csv.DictReader(fh)], ["A", "B"])
        self.assertIn("[dryrun] rows=2 written=0 errors=0", out)

    def test_run_partial_failure_exit_1(self):
        def fake_write(settings, conns, rows, result):
            result.written, result.errors = 1, 1

        with mock.patch.object(job, "collect", return_value=[{"k": 1}, {"k": 2}]), \
                mock.patch.object(job, "write", side_effect=fake_write):
            code, out = self.run_main("run")
        self.assertEqual(code, 1)
        self.assertIn("[run] rows=2 written=1 errors=1", out)

    def test_unexpected_error_exit_2(self):
        with mock.patch.object(job, "collect", side_effect=RuntimeError("boom")):
            code, out = self.run_main("run")
        self.assertEqual(code, 2)
        self.assertIn("整輪失敗", out)

    def test_template_collect_not_implemented_is_fatal(self):
        code, _ = self.run_main("dryrun")
        self.assertEqual(code, 2)

    def test_bad_env_file_exit_2(self):
        Path(self.env["{{PREFIX}}_ENV_FILE"]).write_text("OTHER_X=1\n", encoding="utf-8")
        code, out = self.run_main("run")
        self.assertEqual(code, 2)
        self.assertIn("設定檔錯誤", out)


if __name__ == "__main__":
    unittest.main()
