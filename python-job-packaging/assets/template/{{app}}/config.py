"""執行設定。

連線資訊與密碼由環境變數提供，**不寫入程式碼**。
啟動時會先載入 .env（見 envfile.py；已設定的環境變數優先），範本見 .env.example。

環境變數（一律以 {{PREFIX}}_ 開頭）：
#{{#sqlserver}}
  {{PREFIX}}_SQL_SERVER        SQL Server 主機（必要）。主機、主機,埠號、主機\\執行個體；埠號用「逗號」不是冒號。一律以 TCP 連線
  {{PREFIX}}_SQL_DATABASE      資料庫名稱（必要）
  {{PREFIX}}_SQL_DRIVER        不設 = 自動挑選本機已安裝的最新版（見 odbc.py）；設定時必須是已安裝的驅動名稱
  {{PREFIX}}_SQL_TRUSTED       yes = Windows 整合驗證（以排程執行帳號登入），預設 no
  {{PREFIX}}_SQL_USER          SQL 驗證帳號（{{PREFIX}}_SQL_TRUSTED=no 時必要）
  {{PREFIX}}_SQL_PASSWORD      SQL 驗證密碼（{{PREFIX}}_SQL_TRUSTED=no 時必要）
  {{PREFIX}}_SQL_ENCRYPT       預設 yes（Windows 內建舊版「SQL Server」驅動不支援，未明確設定時不送出）
  {{PREFIX}}_SQL_TRUST_CERT    預設 yes（內網自簽憑證；同上）
#{{/sqlserver}}
#{{#oracle}}
  {{PREFIX}}_ORA_DSN           Oracle 連線，例如 host:1521/service_name（必要）
  {{PREFIX}}_ORA_USER          （必要）
  {{PREFIX}}_ORA_PASSWORD      （必要）
#{{/oracle}}
  {{PREFIX}}_TIME_BUDGET_SEC   每輪時間預算（秒），超過記錄警告，預設 60
  {{PREFIX}}_LOG_DIR           預設 Windows: C:\\ProgramData\\{{App}}\\logs，其他: ./logs

TODO(專案)：本程式自己的設定項目加在 Settings 與 load_settings()，並同步更新上表與 .env.example。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#{{#sqlserver}}
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .odbc import Driver
#{{/sqlserver}}

APP_DIR_NAME = "{{App}}"   # C:\ProgramData\<這個名稱>\logs


class ConfigError(Exception):
    pass


#{{#sqlserver}}
_PROTOCOL_PREFIXES = ("tcp:", "np:", "lpc:", "admin:")


def sql_server_target(raw: str) -> str:
    """{{PREFIX}}_SQL_SERVER → ODBC SERVER 值。

    - 去掉誤貼的「Data Source=」「Server=」前綴
    - 「主機:埠號」是常見錯誤寫法（ODBC 會把整串當主機名稱，出現錯誤 53），直接擋下
    - 沒有指定通訊協定時加上 tcp:，避免 TCP 失敗後退回 Named Pipes、錯誤訊息難以判讀
    """
    value = raw.strip().strip(";")
    for prefix in ("data source=", "server=", "address=", "addr="):
        if value.lower().startswith(prefix):
            value = value[len(prefix):].strip()
    if value.lower().startswith(_PROTOCOL_PREFIXES):
        return value
    if ":" in value:
        host, _, port = value.rpartition(":")
        raise ConfigError(
            f"{{PREFIX}}_SQL_SERVER「{raw}」格式錯誤：SQL Server 的埠號要用逗號，例如「{host},{port}」"
        )
    return "tcp:" + value


#{{/sqlserver}}
def _env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        if required:
            raise ConfigError(f"缺少環境變數 {name}")
        return default
    return value.strip()


def _yes(value: Optional[str]) -> bool:
    return (value or "").lower() in ("1", "y", "yes", "true")


def _secret(env_name: str) -> str:
    """密碼：不 strip（密碼可能含前後空白以外的任何字元），未設定即錯誤。"""
    value = os.environ.get(env_name)
    if not value:
        raise ConfigError(f"缺少環境變數 {env_name}")
    return value


def _default_log_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / APP_DIR_NAME / "logs"
    return Path("logs")


@dataclass(frozen=True)
class Settings:
    log_dir: Path
    time_budget_sec: float
#{{#sqlserver}}
    sql_database: str
#{{/sqlserver}}
    # TODO(專案)：加入本程式自己的設定項目（只放非機密值；密碼在需要時才用 _secret() 讀取）

#{{#sqlserver}}
    def sql_driver(self) -> "Driver":
        """自動偵測（或依 {{PREFIX}}_SQL_DRIVER）本機可用的 SQL Server ODBC 驅動。"""
        from .odbc import DriverError, detect

        try:
            return detect(_env("{{PREFIX}}_SQL_DRIVER"))
        except DriverError as exc:
            raise ConfigError(str(exc)) from exc

    def sqlserver_connection_string(self, driver: Optional["Driver"] = None) -> str:
        driver = driver or self.sql_driver()
        parts = [
            f"DRIVER={{{driver.name}}}",
            f"SERVER={sql_server_target(_env('{{PREFIX}}_SQL_SERVER', required=True))}",  # type: ignore[arg-type]
            f"DATABASE={self.sql_database}",
        ]
        # 加密參數：新版驅動依設定（預設 yes）；內建舊版驅動不支援，只有明確設定時才送出
        for key, env_name in (("Encrypt", "{{PREFIX}}_SQL_ENCRYPT"), ("TrustServerCertificate", "{{PREFIX}}_SQL_TRUST_CERT")):
            raw = _env(env_name)
            if driver.supports_tls_options or raw is not None:
                parts.append(f"{key}={'yes' if _yes(raw if raw is not None else 'yes') else 'no'}")
        parts.append("APP={{app}}")
        if _yes(_env("{{PREFIX}}_SQL_TRUSTED", "no")):
            parts.append("Trusted_Connection=yes")
        else:
            parts.append(f"UID={_env('{{PREFIX}}_SQL_USER', required=True)}")
            parts.append(f"PWD={{{_secret('{{PREFIX}}_SQL_PASSWORD').replace('}', '}}')}}}")
        return ";".join(parts)

#{{/sqlserver}}
#{{#oracle}}
    def oracle_params(self) -> dict[str, str]:
        return {
            "dsn": _env("{{PREFIX}}_ORA_DSN", required=True),  # type: ignore[dict-item]
            "user": _env("{{PREFIX}}_ORA_USER", required=True),  # type: ignore[dict-item]
            "password": _secret("{{PREFIX}}_ORA_PASSWORD"),
        }

#{{/oracle}}

def load_settings() -> Settings:
    try:
        budget = float(_env("{{PREFIX}}_TIME_BUDGET_SEC", "60"))  # type: ignore[arg-type]
    except ValueError as exc:
        raise ConfigError(f"數值設定格式錯誤：{exc}") from exc
    if budget <= 0:
        raise ConfigError("{{PREFIX}}_TIME_BUDGET_SEC 必須大於 0")
    return Settings(
        log_dir=Path(_env("{{PREFIX}}_LOG_DIR") or _default_log_dir()),
        time_budget_sec=budget,
#{{#sqlserver}}
        sql_database=_env("{{PREFIX}}_SQL_DATABASE", required=True),  # type: ignore[arg-type]
#{{/sqlserver}}
    )
