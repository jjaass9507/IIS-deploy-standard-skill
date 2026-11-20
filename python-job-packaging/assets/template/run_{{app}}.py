"""Nuitka 建置入口（deploy/build_nuitka.ps1 以此檔編譯成 {{app}}.exe）。

原始碼執行請用 `python -m {{app}} ...`，兩者功能相同。
"""

import sys

from {{app}}.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
