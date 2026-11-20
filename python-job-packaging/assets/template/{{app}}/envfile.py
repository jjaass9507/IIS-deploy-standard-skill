""".env 設定檔載入（不依賴第三方套件，Nuitka 打包不需額外處理）。

找檔順序（第一個存在的檔案生效）：
  1. 環境變數 {{PREFIX}}_ENV_FILE 指定的路徑（指定了但不存在 → 錯誤）
  2. 目前工作目錄的 .env（工作排程的「起始於」設為安裝目錄）
  3. 程式所在目錄、及其上一層的 .env
     - Nuitka 版：<安裝目錄>\\app\\{{app}}.exe → 找 app\\.env、<安裝目錄>\\.env
     - 原始碼版：python -m {{app}} → 找 {{app}}\\.env、<專案>\\.env

規則：
  - 已存在的環境變數優先，.env 不覆寫（方便臨時用環境變數蓋掉某個值）
  - 格式：KEY=VALUE，一行一個；# 開頭為註解；可加 export 前綴
  - 值的前後空白會去掉；要保留空白或含 # 時用引號包住：KEY="  a#b "
  - 單引號內容原樣保留；雙引號內只處理 \\" 與 \\\\ 兩種跳脫
  - 只接受 {{PREFIX}}_ 開頭的變數，避免誤改其他環境變數
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Optional


class EnvFileError(Exception):
    pass


def candidates() -> list[Path]:
    explicit = os.environ.get("{{PREFIX}}_ENV_FILE")
    if explicit:
        return [Path(explicit)]
    here = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else Path.cwd()
    paths = [Path.cwd() / ".env", here / ".env", here.parent / ".env"]
    unique: list[Path] = []
    for p in paths:
        if p not in unique:
            unique.append(p)
    return unique


def find() -> Optional[Path]:
    paths = candidates()
    if os.environ.get("{{PREFIX}}_ENV_FILE"):
        if not paths[0].is_file():
            raise EnvFileError(f"{{PREFIX}}_ENV_FILE 指定的檔案不存在：{paths[0]}")
        return paths[0]
    return next((p for p in paths if p.is_file()), None)


def _unquote(raw: str, lineno: int) -> str:
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        if quote == '"':
            # 找到未跳脫的結尾引號
            i, out = 1, []
            while i < len(value):
                ch = value[i]
                if ch == "\\" and i + 1 < len(value) and value[i + 1] in ('"', "\\"):
                    out.append(value[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    break
                out.append(ch)
                i += 1
            else:
                raise EnvFileError(f"第 {lineno} 行：雙引號沒有結尾")
            rest = value[i + 1:].strip()
            text = "".join(out)
        else:
            end = value.find(quote, 1)
            if end < 0:
                raise EnvFileError(f"第 {lineno} 行：單引號沒有結尾")
            rest = value[end + 1:].strip()
            text = value[1:end]
        if rest and not rest.startswith("#"):
            raise EnvFileError(f"第 {lineno} 行：引號後面有多餘內容")
        return text
    # 未加引號：行內 # 之後視為註解（# 前需有空白）
    for marker in (" #", "\t#"):
        idx = value.find(marker)
        if idx >= 0:
            value = value[:idx]
    return value.strip()


def parse(lines: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for lineno, line in enumerate(lines, 1):
        text = line.strip().lstrip("﻿")
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[len("export "):].lstrip()
        key, sep, raw = text.partition("=")
        key = key.strip()
        if not sep or not key:
            raise EnvFileError(f"第 {lineno} 行格式錯誤，應為 KEY=VALUE")
        if not key.startswith("{{PREFIX}}_"):
            raise EnvFileError(f"第 {lineno} 行：只接受 {{PREFIX}}_ 開頭的設定（{key}）")
        result[key] = _unquote(raw, lineno)
    return result


def load() -> Optional[Path]:
    """載入 .env 到 os.environ（不覆寫既有值）。回傳實際載入的檔案，沒有則 None。"""
    path = find()
    if path is None:
        return None
    try:
        values = parse(path.read_text(encoding="utf-8-sig").splitlines())
    except EnvFileError as exc:
        raise EnvFileError(f"{path}：{exc}") from None
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return path
