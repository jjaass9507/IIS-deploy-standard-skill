import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from {{app}} import envfile
from {{app}}.config import load_settings


class ParseTest(unittest.TestCase):
    def test_basic(self):
        v = envfile.parse([
            "\ufeff# 註解",
            "",
            "{{PREFIX}}_A = sqlhost,1433 ",
            "export {{PREFIX}}_B=user",
            "{{PREFIX}}_C=orahost:1521/svc  # 行內註解",
            "{{PREFIX}}_EMPTY=",
        ])
        self.assertEqual(v, {"{{PREFIX}}_A": "sqlhost,1433", "{{PREFIX}}_B": "user",
                             "{{PREFIX}}_C": "orahost:1521/svc", "{{PREFIX}}_EMPTY": ""})

    def test_passwords_with_special_chars(self):
        v = envfile.parse([
            '{{PREFIX}}_P1=p@ss}w;rd#1',           # # 前沒有空白 → 屬於值
            '{{PREFIX}}_P2="  a #b \\" c\\\\ "  # 註解',
            "{{PREFIX}}_P3='raw\\n \"x\"'",
            "{{PREFIX}}_EQ=a=b=c",
        ])
        self.assertEqual(v["{{PREFIX}}_P1"], "p@ss}w;rd#1")
        self.assertEqual(v["{{PREFIX}}_P2"], '  a #b " c\\ ')
        self.assertEqual(v["{{PREFIX}}_P3"], 'raw\\n "x"')
        self.assertEqual(v["{{PREFIX}}_EQ"], "a=b=c")

    def test_errors(self):
        for line in ("{{PREFIX}}_A", "=x", "PATH=C:\\evil", '{{PREFIX}}_A="open', "{{PREFIX}}_A='open",
                     '{{PREFIX}}_A="x" y'):
            with self.subTest(line=line), self.assertRaises(envfile.EnvFileError):
                envfile.parse([line])


class LoadTest(unittest.TestCase):
    def test_env_vars_win_over_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("{{PREFIX}}_TIME_BUDGET_SEC=10\n{{PREFIX}}_LOG_DIR=fromfile\n"
                         "{{PREFIX}}_SQL_DATABASE=db\n", encoding="utf-8")
            env = {"{{PREFIX}}_ENV_FILE": str(p), "{{PREFIX}}_LOG_DIR": "fromenv"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(envfile.load(), p)
                self.assertEqual(os.environ["{{PREFIX}}_LOG_DIR"], "fromenv")   # 既有環境變數優先
                s = load_settings()
                self.assertEqual(s.time_budget_sec, 10)
                self.assertEqual(s.log_dir, Path("fromenv"))

    def test_explicit_missing_file(self):
        with mock.patch.dict(os.environ, {"{{PREFIX}}_ENV_FILE": "/nonexistent/.env"}, clear=True):
            with self.assertRaises(envfile.EnvFileError):
                envfile.load()

    def test_found_in_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".env").write_text("{{PREFIX}}_X=cwd\n", encoding="utf-8-sig")  # 含 BOM（記事本存檔）
            old = os.getcwd()
            try:
                os.chdir(d)
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(envfile.load().resolve(), (Path(d) / ".env").resolve())
                    self.assertEqual(os.environ["{{PREFIX}}_X"], "cwd")
            finally:
                os.chdir(old)

    def test_none_found(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(envfile, "candidates", return_value=[Path(d) / ".env"]):
            self.assertIsNone(envfile.load())


if __name__ == "__main__":
    unittest.main()
