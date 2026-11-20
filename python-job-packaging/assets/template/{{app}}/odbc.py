"""SQL Server ODBC Driver 自動選擇。

不寫死驅動版本：從本機已安裝的驅動（pyodbc.drivers()）中依下列優先順序挑選，
{{PREFIX}}_SQL_DRIVER 有設定時以它為準（必須已安裝）。

  1. ODBC Driver N for SQL Server（版本越新越優先：18 → 17 → 13.1 → 13 → 11）
  2. SQL Server Native Client N（11.0 → 10.0），已停止維護
  3. SQL Server（Windows 內建舊版驅動），不支援新的 TLS 設定，只作最後手段

注意：pyodbc.drivers() 只列出與程式同位元（64 位元）的驅動。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

_MODERN = re.compile(r"^ODBC Driver (\d+(?:\.\d+)?) for SQL Server$")
_SNAC = re.compile(r"^SQL Server Native Client (\d+(?:\.\d+)?)$")
LEGACY = "SQL Server"


class DriverError(Exception):
    pass


@dataclass(frozen=True)
class Driver:
    name: str
    kind: str  # modern / snac / legacy / custom

    @property
    def supports_tls_options(self) -> bool:
        """是否支援 Encrypt／TrustServerCertificate 連線參數。"""
        return self.kind in ("modern", "snac", "custom")

    @property
    def note(self) -> str:
        return {
            "modern": "",
            "snac": "（SQL Server Native Client 已停止維護，建議安裝 ODBC Driver 17 或 18）",
            "legacy": "（Windows 內建舊版驅動，不支援 TLS 1.2 以後的加密設定，建議安裝 ODBC Driver 17 或 18）",
            "custom": "（{{PREFIX}}_SQL_DRIVER 指定）",
        }[self.kind]


def _version(pattern: re.Pattern, name: str) -> Optional[float]:
    m = pattern.match(name)
    return float(m.group(1)) if m else None


def choose(installed: Sequence[str], preferred: Optional[str] = None) -> Driver:
    """從已安裝的驅動中挑選。preferred 為 {{PREFIX}}_SQL_DRIVER 的值。"""
    names = [d.strip() for d in installed]
    if preferred:
        preferred = preferred.strip().strip("{}")
        if preferred not in names:
            raise DriverError(f"{{PREFIX}}_SQL_DRIVER 指定的「{preferred}」未安裝。{_listing(names)}")
        if _MODERN.match(preferred):
            return Driver(preferred, "modern")
        if _SNAC.match(preferred):
            return Driver(preferred, "snac")
        if preferred == LEGACY:
            return Driver(preferred, "legacy")
        return Driver(preferred, "custom")

    for pattern, kind in ((_MODERN, "modern"), (_SNAC, "snac")):
        found = [(v, n) for n in names if (v := _version(pattern, n)) is not None]
        if found:
            return Driver(max(found)[1], kind)
    if LEGACY in names:
        return Driver(LEGACY, "legacy")
    raise DriverError(
        "找不到 SQL Server 的 ODBC 驅動，請安裝 Microsoft ODBC Driver 18（或 17）for SQL Server。"
        + _listing(names)
    )


def _listing(names: Sequence[str]) -> str:
    return f"本機已安裝的 ODBC 驅動：{list(names) if names else '（無）'}"


def detect(preferred: Optional[str] = None) -> Driver:
    import pyodbc

    return choose(pyodbc.drivers(), preferred)
