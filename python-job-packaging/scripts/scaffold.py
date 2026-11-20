#!/usr/bin/env python3
"""從 assets/template 產生一個符合「排程打包」規範的新專案骨架。

用法：
  python scaffold.py <目的資料夾> --app <套件名> [--db sqlserver,oracle] [選項]

例：
  python scaffold.py D:\\src\\meter_sync --app meter_sync --db sqlserver --description "電表資料同步"
  python scaffold.py ./energy_report --app energy_report --db sqlserver,oracle --prefix ENR --task-name ENR_Report

選項：
  --app           Python 套件名稱（小寫英數與底線，例 meter_sync）。必要
  --app-title     工作排程器與 C:\\ProgramData 資料夾名稱（PascalCase），預設由 --app 轉換（MeterSync）
  --prefix        環境變數前綴（大寫，不含結尾底線），預設為 --app 的第一段（METER）
  --task-name     工作排程名稱，預設同 --app-title
  --description   一句話說明（寫入 exe 檔案描述、--help、排程描述），不可含雙引號
  --db            用到的資料庫：sqlserver、oracle、sqlserver,oracle 或 none（預設 sqlserver）
  --company       exe 版本資訊的公司名稱，預設 ASE
  --into-existing 目的資料夾已有檔案時，只新增不存在的檔案（既有檔案一律不覆寫，並列出略過的檔案）

範本規則：
  - 檔名與內容中的 {{app}}、{{App}}、{{PREFIX}}、{{TaskName}}、{{description}}、{{company}} 會被替換
  - 含 {{#sqlserver}} … {{/sqlserver}}、{{#oracle}} … {{/oracle}} 的「整行」是條件區塊標記：
    選用該資料庫時保留區塊內容（標記行刪除），否則整個區塊刪除
  - 原檔有 UTF-8 BOM 就保留（.ps1 必須有）；requirements*.txt 必須是純 ASCII

只使用 Python 標準函式庫（3.8 以上）。結束碼：0 成功、1 參數或範本錯誤。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"
BOM = b"\xef\xbb\xbf"
DBS = ("sqlserver", "oracle")
# 只在選用某資料庫時才產生的檔案（範本中的相對路徑）
FILE_CONDITIONS = {
    "{{app}}/odbc.py": "sqlserver",
    "tests/test_odbc.py": "sqlserver",
}
BLOCK = re.compile(r"\{\{([#/])(\w+)\}\}")
LEFTOVER = re.compile(r"\{\{[#/]?[A-Za-z]\w*\}\}")


class ScaffoldError(Exception):
    pass


def pascal(app: str) -> str:
    return "".join(part.capitalize() for part in app.split("_") if part)


def render_blocks(text: str, enabled: set[str], where: str) -> str:
    out: list[str] = []
    stack: list[tuple[str, bool]] = []
    for lineno, line in enumerate(text.splitlines(keepends=True), 1):
        m = BLOCK.search(line)
        if m:
            kind, name = m.groups()
            if name not in DBS:
                raise ScaffoldError(f"{where}:{lineno} 未知的區塊 {name}")
            if kind == "#":
                stack.append((name, name in enabled))
            else:
                if not stack or stack[-1][0] != name:
                    raise ScaffoldError(f"{where}:{lineno} 區塊 {name} 結尾不成對")
                stack.pop()
            continue
        if all(keep for _, keep in stack):
            out.append(line)
    if stack:
        raise ScaffoldError(f"{where} 區塊 {stack[-1][0]} 沒有結尾")
    return "".join(out)


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def render(values: dict[str, str], enabled: set[str]) -> dict[str, bytes]:
    """回傳 {輸出相對路徑: 內容}。"""
    files: dict[str, bytes] = {}
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(TEMPLATE).as_posix()
        need = FILE_CONDITIONS.get(rel)
        if need and need not in enabled:
            continue
        raw = src.read_bytes()
        has_bom = raw.startswith(BOM)
        text = raw[len(BOM):].decode("utf-8") if has_bom else raw.decode("utf-8")
        text = substitute(render_blocks(text, enabled, rel), values)
        left = LEFTOVER.search(text)
        if left:
            raise ScaffoldError(f"{rel} 有未替換的佔位符 {left.group(0)}")
        out_rel = substitute(rel, values)
        data = text.encode("utf-8")
        if Path(out_rel).name.startswith("requirements") and not data.isascii():
            raise ScaffoldError(f"{out_rel} 含非 ASCII 字元（pip 在繁中 Windows 以 cp950 讀取會失敗）")
        if out_rel.endswith(".ps1") and not has_bom:
            raise ScaffoldError(f"範本 {rel} 缺少 UTF-8 BOM（Windows PowerShell 5.1 會以 Big5 讀取）")
        files[out_rel] = (BOM + data) if has_bom else data
    return files


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="產生排程打包專案骨架")
    p.add_argument("target", type=Path)
    p.add_argument("--app", required=True)
    p.add_argument("--app-title")
    p.add_argument("--prefix")
    p.add_argument("--task-name")
    p.add_argument("--description")
    p.add_argument("--db", default="sqlserver")
    p.add_argument("--company", default="ASE")
    p.add_argument("--into-existing", action="store_true")
    return p.parse_args(argv)


def build_values(args: argparse.Namespace) -> tuple[dict[str, str], set[str]]:
    app = args.app
    if not re.fullmatch(r"[a-z][a-z0-9_]*", app):
        raise ScaffoldError("--app 只能用小寫英文字母、數字、底線，且以字母開頭（例 meter_sync）")
    title = args.app_title or pascal(app)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", title):
        raise ScaffoldError("--app-title 只能用英文字母與數字（例 MeterSync）")
    prefix = (args.prefix or app.split("_")[0]).upper().rstrip("_")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", prefix):
        raise ScaffoldError("--prefix 只能用大寫英文字母、數字、底線（例 METER）")
    task = args.task_name or title
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", task):
        raise ScaffoldError("--task-name 只能用英數、底線、點、連字號")
    desc = (args.description or f"{app} 排程程式").strip()
    company = args.company.strip()
    for name, value in (("--description", desc), ("--company", company)):
        if any(ch in value for ch in "\"'`$\r\n"):
            raise ScaffoldError(f"{name} 不可含引號、反引號、$ 或換行（會寫進 PowerShell 與 Python 字串）")
    dbs = {d.strip().lower() for d in args.db.split(",") if d.strip()}
    if dbs == {"none"}:
        dbs = set()
    unknown = dbs - set(DBS)
    if unknown:
        raise ScaffoldError(f"--db 不認得：{', '.join(sorted(unknown))}（可用 sqlserver、oracle、none）")
    values = {"app": app, "App": title, "PREFIX": prefix, "TaskName": task,
              "description": desc, "company": company}
    return values, dbs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        values, dbs = build_values(args)
        files = render(values, dbs)
    except ScaffoldError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    target: Path = args.target
    if target.exists() and any(target.iterdir()) and not args.into_existing:
        print(f"錯誤：{target} 已有檔案；要加到既有專案請加 --into-existing（不會覆寫既有檔案）", file=sys.stderr)
        return 1

    written, skipped = [], []
    for rel, data in files.items():
        dest = target / rel
        if dest.exists():
            skipped.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(rel)

    print(f"專案：{target.resolve()}")
    print("  " + "  ".join(f"{k}={v}" for k, v in values.items() if k != "description"))
    print(f"  資料庫：{', '.join(sorted(dbs)) or '（無）'}")
    print(f"新增 {len(written)} 個檔案")
    for rel in written:
        print(f"  + {rel}")
    if skipped:
        print(f"已存在而略過 {len(skipped)} 個檔案（請手動比對範本合併）：")
        for rel in skipped:
            print(f"  = {rel}")
    print("\n下一步：搜尋 TODO(專案) 逐項完成，然後執行")
    print(f"  python -m unittest discover -s tests -t .")
    print(f"  python {Path(__file__).with_name('check_project.py')} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
