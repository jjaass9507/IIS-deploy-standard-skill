#!/usr/bin/env python3
"""「排程打包」專案靜態檢查（對照規範 §5、§6、§8～§11、§14）。

用法：
  python check_project.py <專案資料夾> [--app <套件名>] [--strict] [--json]

  --app     套件名稱；不指定時由根目錄的 run_<app>.py 推得
  --strict  交付前使用：還留有 TODO(專案) 也算必須修正

它只讀檔案，不會執行程式、不連資料庫、不需要 Windows。通過後仍要依規範做
selfcheck --db、dryrun、編譯版驗證與目標主機 preflight。

結束碼：0＝沒有必須修正的項目；1＝有。只使用 Python 標準函式庫（3.8 以上）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ERROR, WARNING = "必須修正", "警告"
BOM = b"\xef\xbb\xbf"
SKIP_DIRS = {".git", ".venv", ".venv-build", "build", "release", "__pycache__", "logs", "wheels", "node_modules"}
TEXT_EXT = {".py", ".ps1", ".md", ".txt", ".sql", ".example", ".gitignore"}
PLACEHOLDER = re.compile(r"\{\{[#/]?[A-Za-z]\w*\}\}")
README_CHAPTERS = ["總覽", "建置", "申請", "安裝", "設定", "驗證", "上線", "維運", "疑難排解", "回滾"]
DEV_TEST_CHAPTERS = ["準備", "單元測試", "設定", "自我檢查", "dry", "寫入", "編譯版", "回報"]
GITIGNORE_NEEDED = [".env", "build/", "release/", "logs/", "build-freeze.txt"]


class Checker:
    def __init__(self, root: Path, app: str, strict: bool):
        self.root, self.app, self.strict = root, app, strict
        self.findings: list[dict] = []

    def add(self, level: str, rule: str, message: str, where: str = "") -> None:
        self.findings.append({"level": level, "rule": rule, "message": message, "where": where})

    def text(self, rel: str) -> str | None:
        p = self.root / rel
        if not p.is_file():
            return None
        return p.read_bytes().decode("utf-8-sig", errors="replace")

    def files(self):
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root)
            if p.is_file() and not (set(rel.parts) & SKIP_DIRS):
                yield p, rel.as_posix()

    # ------------------------------------------------------------------ 結構 §5
    def check_structure(self) -> None:
        a = self.app
        required = [
            f"{a}/__init__.py", f"{a}/__main__.py", f"{a}/config.py", f"{a}/envfile.py", f"{a}/selfcheck.py",
            f"run_{a}.py", "requirements.txt", "requirements-build.txt", ".env.example", ".gitignore",
            "deploy/build_nuitka.ps1", "deploy/protect_env.ps1", "deploy/preflight.ps1", "deploy/register_task.ps1",
            "deploy/README.md", "deploy/DEV_TEST.md",
        ]
        for rel in required:
            if not (self.root / rel).is_file():
                self.add(ERROR, "STRUCT-01", f"缺少 {rel}", rel)
        reqs = (self.text("requirements.txt") or "").lower()
        if "pyodbc" in reqs and not (self.root / a / "odbc.py").is_file():
            self.add(ERROR, "STRUCT-02", "用到 pyodbc 但沒有 odbc.py（ODBC Driver 自動偵測，規範 §6.2）", f"{a}/odbc.py")
        tests = list((self.root / "tests").glob("test_*.py")) if (self.root / "tests").is_dir() else []
        if not tests:
            self.add(ERROR, "STRUCT-03", "tests/ 沒有 test_*.py（建置腳本會先跑單元測試，規範 §6.5）", "tests/")
        init = self.text(f"{a}/__init__.py") or ""
        if not re.search(r'^__version__\s*=\s*["\']\d+\.\d+\.\d+["\']', init, re.M):
            self.add(ERROR, "STRUCT-04", '__init__.py 需要 __version__ = "x.y.z"（建置時寫入 exe 版本與 zip 檔名）',
                     f"{a}/__init__.py")
        if (self.root / "sql").is_dir() is False:
            self.add(WARNING, "STRUCT-05", "沒有 sql/ 資料夾（DDL、預建資料、權限範本）；確實不需要可忽略", "sql/")

    # ------------------------------------------------------------------ 編碼 §5
    def check_encoding(self) -> None:
        for p, rel in self.files():
            if p.suffix.lower() == ".ps1" and not p.read_bytes().startswith(BOM):
                self.add(ERROR, "ENC-01", ".ps1 必須是 UTF-8 with BOM（PowerShell 5.1 沒有 BOM 會以 Big5 讀取）", rel)
            if p.name.startswith("requirements") and p.suffix == ".txt" and not p.read_bytes().isascii():
                self.add(ERROR, "ENC-02", "requirements*.txt 只能用 ASCII（pip 以 cp950 讀取，中文會 UnicodeDecodeError）", rel)

    # ------------------------------------------------------------------ 殘留 §4
    def check_leftovers(self) -> None:
        legacy = [] if self.app == "pms_ingest" else ["pms_ingest", "PmsIngest", "PMS_Ingest"]
        for p, rel in self.files():
            if p.suffix not in TEXT_EXT and p.name not in (".gitignore", ".env.example"):
                continue
            if rel.startswith("tests/") and p.name == "test_check_project.py":
                continue
            text = p.read_bytes().decode("utf-8-sig", errors="replace")
            m = PLACEHOLDER.search(text)
            if m:
                self.add(ERROR, "LEFT-01", f"未替換的範本佔位符 {m.group(0)}", rel)
            for word in legacy:
                if word in text:
                    self.add(ERROR, "LEFT-02", f"仍有參考實作的名稱「{word}」，請全域取代成本專案名稱", rel)
                    break
            todo = text.count("TODO(專案)")
            if todo:
                self.add(ERROR if self.strict else WARNING, "LEFT-03",
                         f"還有 {todo} 處 TODO(專案) 未完成（交付前必須處理，用 --strict 檢查）", rel)

    # ------------------------------------------------------------------ 程式 §6
    def check_program(self) -> None:
        a = self.app
        main = self.text(f"{a}/__main__.py") or ""
        for cmd in ("run", "dryrun", "selfcheck"):
            if not re.search(r"add_parser\(\s*[\"']%s[\"']" % cmd, main):
                self.add(ERROR, "CLI-01", f"缺少必備子命令 {cmd}（規範 §6.3）", f"{a}/__main__.py")
        if "--db" not in main:
            self.add(ERROR, "CLI-02", "selfcheck 缺少 --db 選項（規範 §6.3）", f"{a}/__main__.py")
        if "--version" not in main:
            self.add(ERROR, "CLI-03", "缺少 --version（規範 §6.3）", f"{a}/__main__.py")
        if "TimedRotatingFileHandler" not in main or "backupCount=90" not in main:
            self.add(WARNING, "LOG-01", "日誌應每日輪替、保留 90 天（規範 §6.4）", f"{a}/__main__.py")
        config = self.text(f"{a}/config.py") or ""
        if "ProgramData" not in config and "PROGRAMDATA" not in config:
            self.add(WARNING, "LOG-02", r"日誌預設位置應為 C:\ProgramData\<App>\logs（規範 §6.4）", f"{a}/config.py")

        envfile = self.text(f"{a}/envfile.py") or ""
        m = re.search(r'startswith\(\s*"([A-Z][A-Z0-9_]*_)"\s*\)', envfile)
        prefix = m.group(1) if m else ""
        if not prefix:
            self.add(ERROR, "ENV-01", ".env 解析必須只接受 <PREFIX>_ 開頭的變數（規範 §6.1）", f"{a}/envfile.py")
        example = self.text(".env.example") or ""
        for lineno, line in enumerate(example.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            key, _, value = s.partition("=")
            key = key.strip()
            if prefix and not key.startswith(prefix):
                self.add(ERROR, "ENV-02", f"第 {lineno} 行 {key} 不是 {prefix} 開頭，.env 載入時會被拒絕", ".env.example")
            if "PASSWORD" in key and value.strip():
                self.add(ERROR, "SEC-01", f"第 {lineno} 行 {key} 有值；範本不可含真實密碼（規範 §9 S1）", ".env.example")
        if prefix:
            for p, rel in self.files():
                if p.suffix != ".py" or rel.startswith("tests/"):
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                for name in sorted(set(re.findall(r'environ(?:\.get\(|\[)\s*["\']([A-Z][A-Z0-9_]+)["\']', text))):
                    if not name.startswith(prefix) and name not in {"PROGRAMDATA"}:
                        self.add(WARNING, "ENV-03", f"讀取了不是 {prefix} 開頭的環境變數 {name}", rel)

    # ------------------------------------------------------------------ 安全 §9
    def check_security(self) -> None:
        gi = self.text(".gitignore") or ""
        lines = {line.strip() for line in gi.splitlines()}
        for need in GITIGNORE_NEEDED:
            if need not in lines and need.rstrip("/") not in lines:
                self.add(ERROR if need == ".env" else WARNING, "SEC-02", f".gitignore 缺少 {need}", ".gitignore")
        if (self.root / ".git").exists() or (self.root.parent / ".git").exists():
            try:
                out = subprocess.run(["git", "ls-files", "--", ".env"], cwd=self.root, capture_output=True,
                                     text=True, timeout=10).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                out = ""
            if out:
                self.add(ERROR, "SEC-03", ".env 已提交到版控：移除並更換其中的密碼（規範 §9 S1、S6）", ".env")

    # ------------------------------------------------------------------ 建置 §8
    def check_build(self) -> None:
        a = self.app
        build = self.text("deploy/build_nuitka.ps1") or ""
        if build:
            if "--mode=standalone" not in build:
                self.add(ERROR, "BUILD-01", "Nuitka 必須用 --mode=standalone（規範 §8.2）", "deploy/build_nuitka.ps1")
            if re.search(r"--onefile|--mode=onefile", build):
                self.add(ERROR, "BUILD-02", "不可用 onefile：排程頻繁啟動時每次解壓，慢且易被防毒攔截（規範 §8.2）",
                         "deploy/build_nuitka.ps1")
            if a not in build:
                self.add(ERROR, "BUILD-03", f"建置腳本沒有提到套件 {a}（是否沒改名？）", "deploy/build_nuitka.ps1")
            for word in ("SHA256", "build-freeze.txt", "unittest"):
                if word not in build:
                    self.add(WARNING, "BUILD-04", f"建置腳本沒有 {word}（規範 §7 階段 1、§8.1）", "deploy/build_nuitka.ps1")
            reqs = (self.text("requirements.txt") or "").lower()
            if "oracledb" in reqs and "cryptography.x509" not in build:
                self.add(ERROR, "BUILD-05", "用到 oracledb 但沒有列入隱藏相依（規範 §8.2 表格）", "deploy/build_nuitka.ps1")
            if "pyodbc" in reqs and "pyodbc" not in build:
                self.add(ERROR, "BUILD-05", "用到 pyodbc 但沒有 --include-module=pyodbc（規範 §8.2 表格）",
                         "deploy/build_nuitka.ps1")
        rb = self.text("requirements-build.txt") or ""
        if not re.search(r"^nuitka\s*>=\s*4\.2\s*,\s*<\s*5", rb, re.M):
            self.add(ERROR, "BUILD-06", "requirements-build.txt 應固定 nuitka>=4.2,<5（規範 §8.1）", "requirements-build.txt")

    # ------------------------------------------------------------------ 排程 §10
    def check_schedule(self) -> None:
        task = self.text("deploy/register_task.ps1") or ""
        if not task:
            return
        if "IgnoreNew" not in task:
            self.add(ERROR, "TASK-01", "排程必須 MultipleInstances IgnoreNew（規範 §10）", "deploy/register_task.ps1")
        if "ExecutionTimeLimit" not in task:
            self.add(ERROR, "TASK-02", "排程必須設定 ExecutionTimeLimit 且小於間隔（規範 §10）", "deploy/register_task.ps1")
        if "NT AUTHORITY\\SYSTEM" not in task:
            self.add(ERROR, "TASK-03", "register_task.ps1 -RunAs SYSTEM 必須用 NT AUTHORITY\\SYSTEM 且不詢問密碼（FAQ T7）",
                     "deploy/register_task.ps1")
        if "WorkingDirectory" not in task:
            self.add(ERROR, "TASK-04", "排程起始目錄必須是安裝目錄（exe 依此找到 .env，規範 §10）", "deploy/register_task.ps1")
        protect = self.text("deploy/protect_env.ps1") or ""
        if protect and "/inheritance:r" not in protect:
            self.add(ERROR, "SEC-04", "protect_env.ps1 必須移除繼承權限（規範 §9 S2）", "deploy/protect_env.ps1")

    # ------------------------------------------------------------------ 文件 §14
    def check_docs(self) -> None:
        for rel, chapters in (("deploy/README.md", README_CHAPTERS), ("deploy/DEV_TEST.md", DEV_TEST_CHAPTERS)):
            text = self.text(rel)
            if text is None:
                continue
            headings = "\n".join(line for line in text.splitlines() if line.startswith("#")).lower()
            missing = [c for c in chapters if c.lower() not in headings]
            if missing:
                self.add(ERROR, "DOC-01", f"缺少規範 §14 要求的章節：{'、'.join(missing)}", rel)

    def run(self) -> list[dict]:
        self.check_structure()
        self.check_encoding()
        self.check_leftovers()
        self.check_program()
        self.check_security()
        self.check_build()
        self.check_schedule()
        self.check_docs()
        return self.findings


def detect_app(root: Path) -> str | None:
    names = [p.stem[len("run_"):] for p in root.glob("run_*.py") if (root / p.stem[len("run_"):]).is_dir()]
    return names[0] if len(names) == 1 else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="排程打包專案靜態檢查")
    p.add_argument("project", type=Path)
    p.add_argument("--app")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    root = args.project.resolve()
    app = args.app or detect_app(root)
    if not app:
        print("錯誤：找不到唯一的 run_<app>.py 與 <app>/ 套件，請以 --app 指定", file=sys.stderr)
        return 1
    findings = Checker(root, app, args.strict).run()
    errors = [f for f in findings if f["level"] == ERROR]

    if args.json:
        print(json.dumps({"project": str(root), "app": app, "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(f"排程打包檢查：{root}（套件 {app}{'，strict' if args.strict else ''}）")
        for level in (ERROR, WARNING):
            items = [f for f in findings if f["level"] == level]
            if items:
                print(f"\n[{level}] {len(items)} 項")
                for f in items:
                    print(f"  {f['rule']:<10} {f['where']:<28} {f['message']}")
        print(f"\n結果：{'沒有必須修正的項目' if not errors else f'{len(errors)} 項必須修正'}"
              f"（警告 {len(findings) - len(errors)} 項）")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
