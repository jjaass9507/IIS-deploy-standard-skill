import unittest

from {{app}}.odbc import Driver, DriverError, choose


class ChooseTest(unittest.TestCase):
    def test_newest_modern_driver_wins(self):
        installed = ["SQL Server", "SQL Server Native Client 11.0", "ODBC Driver 13 for SQL Server",
                     "ODBC Driver 17 for SQL Server", "ODBC Driver 13.1 for SQL Server", "Microsoft Access Driver (*.mdb)"]
        self.assertEqual(choose(installed), Driver("ODBC Driver 17 for SQL Server", "modern"))
        self.assertEqual(choose(installed + ["ODBC Driver 18 for SQL Server"]).name, "ODBC Driver 18 for SQL Server")
        # 數值比較而非字串比較：13.1 > 13，且 9 < 11
        self.assertEqual(choose(["ODBC Driver 13 for SQL Server", "ODBC Driver 13.1 for SQL Server"]).name,
                         "ODBC Driver 13.1 for SQL Server")
        self.assertEqual(choose(["ODBC Driver 9 for SQL Server", "ODBC Driver 11 for SQL Server"]).name,
                         "ODBC Driver 11 for SQL Server")

    def test_fallbacks(self):
        d = choose(["SQL Server", "SQL Server Native Client 10.0", "SQL Server Native Client 11.0"])
        self.assertEqual((d.name, d.kind), ("SQL Server Native Client 11.0", "snac"))
        d = choose(["SQL Server", "Microsoft Excel Driver"])
        self.assertEqual((d.name, d.kind, d.supports_tls_options), ("SQL Server", "legacy", False))

    def test_none_installed(self):
        with self.assertRaises(DriverError) as ctx:
            choose(["Microsoft Access Driver (*.mdb)"])
        self.assertIn("Microsoft Access Driver", str(ctx.exception))

    def test_preferred(self):
        installed = ["SQL Server", "ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]
        self.assertEqual(choose(installed, "ODBC Driver 17 for SQL Server").name, "ODBC Driver 17 for SQL Server")
        self.assertEqual(choose(installed, "{ODBC Driver 17 for SQL Server}").name, "ODBC Driver 17 for SQL Server")
        self.assertEqual(choose(installed, "SQL Server").kind, "legacy")
        with self.assertRaises(DriverError) as ctx:
            choose(installed, "ODBC Driver 99 for SQL Server")
        self.assertIn("ODBC Driver 17 for SQL Server", str(ctx.exception))   # 錯誤訊息列出已安裝的


if __name__ == "__main__":
    unittest.main()
