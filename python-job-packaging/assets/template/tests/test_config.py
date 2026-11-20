import os
import unittest
from pathlib import Path
from unittest import mock

from {{app}}.config import ConfigError, load_settings
# {{#sqlserver}}
from {{app}}.config import sql_server_target
from {{app}}.odbc import Driver

SQL_ENV = {"{{PREFIX}}_SQL_SERVER": "sqlhost,1433", "{{PREFIX}}_SQL_DATABASE": "db",
           "{{PREFIX}}_SQL_USER": "u", "{{PREFIX}}_SQL_PASSWORD": "p}w;d"}
MODERN = Driver("ODBC Driver 18 for SQL Server", "modern")
LEGACY = Driver("SQL Server", "legacy")
# {{/sqlserver}}
BASE_ENV = {"{{PREFIX}}_SQL_DATABASE": "db"}


class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        with mock.patch.dict(os.environ, BASE_ENV, clear=True):
            s = load_settings()
        self.assertEqual(s.time_budget_sec, 60)
        self.assertTrue(str(s.log_dir).endswith("logs"))

    def test_bad_numbers(self):
        for value in ("abc", "0", "-1"):
            with self.subTest(value=value), \
                    mock.patch.dict(os.environ, {**BASE_ENV, "{{PREFIX}}_TIME_BUDGET_SEC": value}, clear=True):
                with self.assertRaises(ConfigError):
                    load_settings()

    def test_log_dir_override(self):
        with mock.patch.dict(os.environ, {**BASE_ENV, "{{PREFIX}}_LOG_DIR": "x/logs"}, clear=True):
            self.assertEqual(load_settings().log_dir, Path("x/logs"))
# {{#sqlserver}}


class SqlServerTest(unittest.TestCase):
    def test_target(self):
        self.assertEqual(sql_server_target("sqlhost"), "tcp:sqlhost")
        self.assertEqual(sql_server_target("sqlhost,1433"), "tcp:sqlhost,1433")
        self.assertEqual(sql_server_target("Data Source=sqlhost\\INST;"), "tcp:sqlhost\\INST")
        self.assertEqual(sql_server_target("np:sqlhost"), "np:sqlhost")
        with self.assertRaises(ConfigError) as ctx:
            sql_server_target("sqlhost:1433")
        self.assertIn("sqlhost,1433", str(ctx.exception))

    def test_database_required(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(ConfigError):
            load_settings()

    def test_connection_string(self):
        with mock.patch.dict(os.environ, SQL_ENV, clear=True):
            cs = load_settings().sqlserver_connection_string(MODERN)
        self.assertIn("DRIVER={ODBC Driver 18 for SQL Server}", cs)
        self.assertIn("SERVER=tcp:sqlhost,1433", cs)
        self.assertIn("Encrypt=yes", cs)
        self.assertIn("PWD={p}}w;d}", cs)            # } 跳脫、; 包在大括號內
        self.assertIn("APP={{app}}", cs)

    def test_legacy_driver_omits_tls_options(self):
        with mock.patch.dict(os.environ, SQL_ENV, clear=True):
            cs = load_settings().sqlserver_connection_string(LEGACY)
        self.assertNotIn("Encrypt", cs)
        with mock.patch.dict(os.environ, {**SQL_ENV, "{{PREFIX}}_SQL_ENCRYPT": "no"}, clear=True):
            self.assertIn("Encrypt=no", load_settings().sqlserver_connection_string(LEGACY))

    def test_trusted(self):
        env = {"{{PREFIX}}_SQL_SERVER": "h", "{{PREFIX}}_SQL_DATABASE": "db", "{{PREFIX}}_SQL_TRUSTED": "yes"}
        with mock.patch.dict(os.environ, env, clear=True):
            cs = load_settings().sqlserver_connection_string(MODERN)
        self.assertIn("Trusted_Connection=yes", cs)
        self.assertNotIn("UID=", cs)
# {{/sqlserver}}
# {{#oracle}}


class OracleTest(unittest.TestCase):
    def test_params(self):
        env = {**BASE_ENV, "{{PREFIX}}_ORA_DSN": "h:1521/s", "{{PREFIX}}_ORA_USER": "u", "{{PREFIX}}_ORA_PASSWORD": " pw "}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(load_settings().oracle_params(), {"dsn": "h:1521/s", "user": "u", "password": " pw "})
        with mock.patch.dict(os.environ, BASE_ENV, clear=True), self.assertRaises(ConfigError):
            load_settings().oracle_params()
# {{/oracle}}


if __name__ == "__main__":
    unittest.main()
