#!/usr/bin/env python3
"""Python 部署標準 v1.2 與 PostgreSQL 資料庫權限標準 v1.0 自我檢查（靜態）。

用法：python self_check.py <專案資料夾> [--json]

涵蓋「IIS 部署助手」的主要靜態規則，讓你在交給使用者之前先自己檢查一遍。
它不會啟動程式，所以 /health、/version、子路徑、「執行時不寫入程式目錄」等仍需另外實測；
最終以使用者在 Windows 上用部署助手做的完整檢查為準。

結束碼：0＝沒有必須修正或需要宣告的項目；1＝有。只使用標準函式庫。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ERROR, DECLARE, WARNING = "必須修正", "需要宣告", "警告"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "dist-package"}
TEXT_EXT = {".py", ".ps1", ".psm1", ".bat", ".cmd", ".json", ".toml", ".cfg", ".ini", ".yml", ".yaml", ".config", ".xml", ".txt", ".sh", ".sql"}


class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.findings = []
        self.manifest = None

    def add(self, level, rule, message, fix, where=None):
        self.findings.append({"level": level, "rule": rule, "message": message, "fix": fix, "where": where})

    # ------------------------------------------------------------ 檔案
    def read(self, rel):
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace") if path.is_file() else None
        except OSError:
            return None

    def packaged_files(self):
        files = []
        for item in (self.manifest or {}).get("include") or []:
            path = self.root / item
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(p for p in path.rglob("*") if p.is_file())
        return files

    def python_sources(self):
        result = []
        for path in self.packaged_files():
            rel = path.relative_to(self.root).as_posix()
            parts = rel.split("/")
            if path.suffix != ".py" or "tests" in parts or "__pycache__" in parts or path.name.startswith("test_") or "migrations/versions/" in rel:
                continue
            try:
                result.append((rel, path.read_text(encoding="utf-8", errors="replace").splitlines()))
            except OSError:
                pass
        return result

    @staticmethod
    def grep(sources, pattern, flags=0):
        regex = re.compile(pattern, flags)
        for rel, lines in sources:
            for number, line in enumerate(lines, 1):
                if regex.search(line):
                    return f"{rel} 第 {number} 行：{line.strip()[:140]}"
        return None

    # ------------------------------------------------------------ 檢查
    def run(self):
        raw = self.read("deployment.json")
        if raw is None:
            self.add(ERROR, "DECL-01", "專案根目錄沒有 deployment.json", "依 references/deployment-json.md 建立")
            return self.findings
        try:
            self.manifest = json.loads(raw)
        except json.JSONDecodeError as error:
            self.add(ERROR, "DECL-01", f"deployment.json 不是合法的 JSON：{error}", "修正格式")
            return self.findings
        m = self.manifest
        self.declaration(m)
        self.packaging(m)
        sources = self.python_sources()
        self.architecture(m, sources)
        self.paths(sources)
        self.auth(m, sources)
        self.services(m)
        self.migrations(m)
        self.database(m)
        self.apply_overrides(m)
        return self.findings

    def declaration(self, m):
        if m.get("standard") != "1.2":
            self.add(ERROR, "DECL-01", f'standard 為 "{m.get("standard")}"', '改為 "1.2"', "deployment.json")
        app = m.get("application") or ""
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", app):
            self.add(ERROR, "DECL-02", f'application 為 "{app}"', "小寫英數加連字號，例如 power-bill-agent", "deployment.json")
        version = m.get("version") or ""
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            self.add(ERROR, "DECL-03", f'version 為 "{version}"', "使用 主.次.修，例如 1.4.0", "deployment.json")
        else:
            changelog = self.read("CHANGELOG.md")
            if changelog is None:
                self.add(ERROR, "DECL-03", "沒有 CHANGELOG.md", f"新增 CHANGELOG.md，寫上 {version} 的修訂內容")
            elif version not in changelog:
                self.add(ERROR, "DECL-03", f"CHANGELOG.md 沒有提到 {version}", "加上這一版的條目", "CHANGELOG.md")
        problems = []
        kind = m.get("type")
        if kind not in ("web", "services", "web+services"):
            problems.append(f'type 為 "{kind}"（應為 web、services 或 web+services）')
        web = m.get("web") or {}
        if kind and "web" in kind:
            if web.get("framework") not in ("wsgi", "asgi"):
                problems.append(f'web.framework 為 "{web.get("framework")}"（應為 wsgi 或 asgi）')
            if not re.fullmatch(r"[A-Za-z_][\w.]*:[A-Za-z_]\w*", web.get("entry") or ""):
                problems.append(f'web.entry 為 "{web.get("entry")}"（應為 模組:物件）')
        if kind and "services" in kind and not m.get("services"):
            problems.append("type 含 services 但 services 是空的")
        include = m.get("include") or []
        if not include:
            problems.append("include 是空的")
        problems += [f'include 的 "{item}" 不存在' for item in include if not (self.root / item).exists()]
        if problems:
            self.add(ERROR, "DECL-04", "；".join(problems), "修正 deployment.json", "deployment.json")
        if (web.get("scheduling") or "split") != "split":
            self.add(ERROR, "DECL-05", f'web.scheduling 為 "{web.get("scheduling")}"', "把排程拆成背景服務，或登記例外", "deployment.json")
        if not re.fullmatch(r"3\.\d{1,2}", m.get("python") or ""):
            self.add(ERROR, "DECL-06", f'python 為 "{m.get("python")}"', "填部署機的 Python 版本，例如 3.12", "deployment.json")
        if not (m.get("selfTest") or {}).get("env"):
            self.add(WARNING, "DECL-04", "沒有 selfTest.env", "提供讓程式在沒有正式資料庫與 AD 時也能啟動的設定（例如 APP_ENV=development、AUTH_MODE=mock）", "deployment.json")

    def packaging(self, m):
        lock = self.read("requirements.lock")
        names = set()
        if lock is None:
            self.add(ERROR, "PKG-01", "沒有 requirements.lock", "在 Windows、與部署機相同的 Python 版本上執行 pip-compile --generate-hashes -o requirements.lock requirements.txt")
        else:
            loose, entries, previous = [], 0, None
            for number, raw in enumerate(lock.splitlines(), 1):
                if any(ord(ch) > 127 for ch in raw):
                    self.add(ERROR, "PKG-03", f"requirements.lock 第 {number} 行含非英文字元", "刪除中文註解（Windows 的 pip 以系統編碼讀檔）", "requirements.lock")
                    break
            for number, raw in enumerate(lock.splitlines(), 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("--hash"):
                    if previous is not None:
                        previous["hashed"] = True
                    continue
                if line.startswith("-e ") or "file:" in line or "git+" in line or re.match(r"^(\.|/|[A-Za-z]:\\)", line):
                    self.add(ERROR, "PKG-03", f"requirements.lock 第 {number} 行：{line}", "只列已發佈的套件版本，不用本機路徑、-e 或 git 網址", "requirements.lock")
                    previous = None
                    continue
                if line.startswith("-"):
                    continue
                match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*(==)?\s*([^\s;\\,]+)?(.*)$", line)
                if not match:
                    continue
                entries += 1
                names.add(match.group(1).lower().replace("_", "-"))
                previous = {"hashed": "--hash" in line}
                if match.group(3) != "==" or match.group(5).strip().startswith(","):
                    loose.append(line.rstrip("\\").strip())
            if entries == 0:
                self.add(ERROR, "PKG-01", "requirements.lock 沒有任何套件", "重新產生")
            if loose:
                self.add(ERROR, "PKG-01", f"{len(loose)} 個套件沒有固定版本，例如 {'、'.join(loose[:3])}", "每個套件寫成 名稱==版本（含間接相依）", "requirements.lock")
            if "--hash" not in lock and entries:
                self.add(WARNING, "PKG-02", "requirements.lock 沒有 --hash", "以 pip-compile --generate-hashes 產生，安裝時可驗證檔案")
        self.lock_names = names

        bad = []
        for path in self.packaged_files():
            rel = path.relative_to(self.root).as_posix()
            parts = rel.split("/")
            name = parts[-1]
            if {".venv", "venv", "node_modules", ".git", "logs"} & set(parts):
                bad.append(rel)
            elif name == ".env" or (name.startswith(".env.") and name != ".env.example"):
                bad.append(rel)
            elif name.endswith((".sqlite3", ".sqlite", ".db", ".log")):
                bad.append(rel)
        if bad:
            self.add(ERROR, "PKG-06", f"include 範圍內有不該打包的檔案：{'、'.join(bad[:4])}" + (f" 等 {len(bad)} 個" if len(bad) > 4 else ""),
                     "調整 include，或把這些檔案移出打包的資料夾；執行時產生的檔案要改寫到 APP_DATA_DIR／APP_LOG_DIR")
        for path in self.packaged_files():
            if path.suffix.lower() in TEXT_EXT or path.name == "requirements.lock":
                try:
                    if "PRIVATE KEY-----" in path.read_text(encoding="utf-8", errors="replace"):
                        self.add(ERROR, "PKG-07", f"{path.relative_to(self.root).as_posix()} 內有私鑰", "把私鑰移出 repo")
                        break
                except OSError:
                    pass
        if (self.root / "web.config").exists():
            self.add(WARNING, "PKG-08", "專案內有 web.config", "web.config 由部署助手產生，專案的不會被使用，建議刪除")
        template = m.get("configTemplate") or ".env.example"
        self.template = self.read(template)
        if self.template is None:
            self.add(ERROR, "PKG-09", f"沒有 {template}", "新增設定範本，列出所有設定 key（不含真實密碼）")
        self.dev_env(template)

    @staticmethod
    def env_values(text):
        values, keys = {}, set()
        for line in (text or "").splitlines():
            match = re.match(r"^\s*(#\s*)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", line)
            if not match:
                continue
            keys.add(match.group(2))
            if not match.group(1):
                value = match.group(3).split(" #")[0].strip().strip("'\"")
                values[match.group(2)] = value
        return values, keys

    def dev_env(self, template_name):
        """開發者自己的 .env：只比對項目名稱與機密值是否外流到範本，不以正式環境標準檢查。"""
        dev = self.read(".env")
        if dev is None:
            return
        dev_values, _ = self.env_values(dev)
        if self.template is not None:
            template_values, template_keys = self.env_values(self.template)
            missing = [k for k in dev_values if k not in template_keys and k != "MIGRATION_DATABASE_URL"]
            if missing:
                self.add(WARNING, "PKG-11", f".env 有 {len(missing)} 個項目不在 {template_name}：{'、'.join(missing[:8])}",
                         f"把這些項目加到 {template_name}（值留空或填範例）", template_name)
            for key, value in dev_values.items():
                if re.search(r"PASSWORD|PASSWD|SECRET|TOKEN|COOKIE|API_KEY|APIKEY|PRIVATE", key, re.I) and len(value) >= 6 and template_values.get(key) == value:
                    self.add(ERROR, "PKG-07", f"{template_name} 的 {key} 與 .env 的值相同（看起來是真實的密碼或金鑰）",
                             f"把 {template_name} 的 {key} 改成空白；若已提交到 repo，請一併更換", template_name)
                    break
        ignore = self.read(".gitignore")
        ignored = ignore is None and not (self.root / ".git").exists()
        for raw in (ignore or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            pattern = (line[1:] if negate else line).lstrip("/")
            pattern = pattern[3:] if pattern.startswith("**/") else pattern
            if re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]*").replace(r"\?", "[^/]"), ".env"):
                ignored = not negate
        if not ignored:
            self.add(WARNING, "PKG-12", ".gitignore 沒有排除 .env", "在 .gitignore 加上一行 .env", ".gitignore")

    def architecture(self, m, sources):
        kind = m.get("type") or ""
        web = m.get("web") or {}
        if "web" in kind:
            server = "uvicorn" if web.get("framework") == "asgi" else "waitress"
            if self.lock_names and server not in self.lock_names:
                self.add(ERROR, "ARCH-01", f"requirements.lock 沒有 {server}", f"加入 {server} 並重新產生 lock")
        text_sources = []
        for path in self.packaged_files():
            if path.suffix.lower() in TEXT_EXT:
                try:
                    text_sources.append((path.relative_to(self.root).as_posix(), path.read_text(encoding="utf-8", errors="replace").splitlines()))
                except OSError:
                    pass
        hit = self.grep(text_sources, r"--reload\b|\breload\s*=\s*True\b")
        if hit:
            self.add(ERROR, "ARCH-03", hit, "正式環境不使用自動重新載入；從會打包的檔案中移除")
        hit = self.grep(text_sources, r"\bnssm(\.exe)?\b|\bschtasks\b|Register-ScheduledTask|New-ScheduledTask|shell:startup", re.I)
        if hit:
            self.add(ERROR, "ARCH-04", hit, "背景程式改在 deployment.json 的 services 宣告，由 WinSW 管理")
        if "web" in kind:
            service_modules = set()
            for service in m.get("services") or []:
                for arg in service.get("args") or []:
                    service_modules.add(arg.replace("\\", "/"))
                    service_modules.add(arg.replace(".", "/") + ".py")
            web_sources = [(rel, lines) for rel, lines in sources if rel not in service_modules]
            hit = self.grep(web_sources, r"\b(BackgroundScheduler|BlockingScheduler|AsyncIOScheduler)\s*\(|threading\.Timer\s*\(|\bschedule\.every\s*\(|threading\.Thread\s*\(")
            if hit:
                self.add(WARNING, "ARCH-05", hit, "網站程序內不執行排程或背景工作；改由背景服務處理。確認沒有問題時在 reviewed 註記")

    def paths(self, sources):
        def uses(name):
            return any(name in line for _, lines in sources for line in lines)
        if not uses("APP_CONFIG_FILE"):
            hit = self.grep(sources, r"load_dotenv\s*\(|dotenv_values\s*\(")
            self.add(ERROR, "PATH-01", (hit + "；" if hit else "") + "程式沒有讀取 APP_CONFIG_FILE",
                     '設定檔位置改為 os.environ.get("APP_CONFIG_FILE") or <開發機預設>')
        if not any(uses(name) for name in ("APP_LOG_DIR", "APP_DATA_DIR", "APP_UPLOAD_DIR", "APP_TEMP_DIR")):
            hit = self.grep(sources, r"FileHandler\s*\(|open\s*\([^)]*,\s*[\"'][wax]b?\+?[\"']|\.write_text\s*\(|\.write_bytes\s*\(|\.mkdir\s*\(|os\.makedirs\s*\(")
            if hit:
                self.add(ERROR, "PATH-02", hit + "；程式會寫檔，但沒有讀取 APP_LOG_DIR／APP_DATA_DIR／APP_UPLOAD_DIR／APP_TEMP_DIR",
                         "寫入位置改讀對應的環境變數，未設定時才用開發機預設（放在專案資料夾外）")
        hit = self.grep(sources, r"sqlite:///(?!:memory:)[^{\"']*[\"']|instance_relative_config\s*=\s*True|instance_path")
        if hit:
            self.add(WARNING, "PATH-03", hit, "確認執行時不會在程式目錄產生資料庫或 instance 資料夾；本機資料庫檔放到 APP_DATA_DIR")

    def auth(self, m, sources):
        auth = m.get("auth") or {}
        if "web" not in (m.get("type") or "") or not auth.get("ad"):
            return
        template = self.template or ""
        missing = [key for key in ("AUTH_MODE", "AUTH_SSO_ENABLED") if not re.search(rf"^\s*#?\s*{key}\s*=", template, re.M)]
        if missing:
            self.add(ERROR, "AUTH-01", f"設定範本沒有 {'、'.join(missing)}", "程式以 AUTH_MODE（off／mock／ad）與 AUTH_SSO_ENABLED 控制登入，並加入設定範本")
        if not self.grep(sources, r"production") or not self.grep(sources, r"AUTH_MODE"):
            self.add(ERROR, "AUTH-02", "程式碼中找不到「正式環境拒絕非 ad 登入」的檢查", "啟動時檢查：APP_ENV 為 production 而 AUTH_MODE 不是 ad 就結束程式")
        match = re.search(r"^\s*AD_SERVER\s*=\s*(\S+)", template, re.M)
        if match and not match.group(1).lower().startswith("ldaps://"):
            self.add(WARNING, "AUTH-03", f"設定範本的 AD_SERVER 為 {match.group(1)}", "建議使用 ldaps:// 並驗證憑證（部門預設不強制）")
        if not auth.get("rbac"):
            self.add(DECLARE, "AUTH-09", "auth.rbac 沒有填寫", "用一兩句話說明平台如何記錄已開通的帳號與角色", "deployment.json")
        if not self.grep(sources, r"SESSION_COOKIE_SECURE|https_only|secure\s*=", re.I):
            self.add(ERROR, "AUTH-08", "程式沒有可開啟 Cookie Secure 旗標的設定", "加入可由設定開啟的 Secure；並設定 HttpOnly、SameSite")
        for label, endpoint in (("me", auth.get("meEndpoint") or "/api/auth/me"), ("logout", auth.get("logoutEndpoint") or "/api/auth/logout")):
            tail = endpoint.rsplit("/", 1)[-1]
            if not self.grep(sources, rf"[\"'][^\"']*/{re.escape(tail)}[\"']"):
                self.add(WARNING, "AUTH-06" if label == "me" else "AUTH-07", f"程式碼中找不到 {endpoint}", "新增此端點，或在 deployment.json 的 auth 指定實際路徑")
        hit = self.grep(sources, r"(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[\"`]?base\.kh_ad_employees", re.I)
        if hit:
            self.add(ERROR, "AUTH-10", hit, "員工資料表只讀不寫")
        if not auth.get("sso"):
            self.add(ERROR, "SSO-00", "auth.sso 為 false", "有使用者登入的網站必須提供 Windows SSO（/auth/sso）；確實無法提供時登記例外", "deployment.json")
            return
        if not self.grep(sources, r"[\"'](/auth)?/sso[\"']"):
            self.add(WARNING, "SSO-01", "程式碼中找不到 /auth/sso", "新增 SSO 入口，或在 auth.ssoEndpoint 指定實際路徑")
        header = self.grep(sources, r"X-IIS-WindowsAuthToken|X_IIS_WINDOWSAUTHTOKEN", re.I)
        if not header:
            self.add(WARNING, "SSO-01", "程式碼中找不到讀取 X-IIS-WindowsAuthToken 的地方", "SSO 的身分來自這個標頭中的權杖 Handle")
        else:
            if not self.grep(sources, r"GetTokenInformation|LookupAccountSid|win32security|OpenThreadToken"):
                self.add(ERROR, "SSO-01", header + "；讀了標頭但沒有用權杖 API 解析", "標頭的值是 Handle，不是帳號；用 GetTokenInformation／LookupAccountSid 取得帳號")
            if not self.grep(sources, r"CloseHandle"):
                self.add(ERROR, "SSO-02", "讀取權杖後沒有呼叫 CloseHandle", "在 try/finally 中呼叫 CloseHandle")

    def services(self, m):
        for service in m.get("services") or []:
            name = service.get("id") or "（未命名）"
            problems = []
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", service.get("id") or ""):
                problems.append("id 需為小寫英數加連字號")
            if service.get("kind", "venv") != "pyinstaller" and not service.get("args"):
                problems.append("沒有 args")
            if not service.get("restart"):
                problems.append("沒有 restart")
            if service.get("stopTimeoutSeconds") is None:
                problems.append("沒有 stopTimeoutSeconds")
            if problems:
                self.add(ERROR, "SVC-01", f"服務 {name}：{'、'.join(problems)}", "補齊服務宣告", "deployment.json")
            if not service.get("lastSuccess"):
                self.add(DECLARE, "HLTH-04", f"服務 {name} 沒有 lastSuccess", "說明如何取得最後成功時間（狀態檔或端點）", "deployment.json")
            if service.get("scheduled") and not (service.get("dedup") and service.get("catchUp")):
                self.add(DECLARE, "SVC-03", f"排程服務 {name} 沒有 dedup／catchUp", "說明如何防止重複執行，以及停機後如何補跑", "deployment.json")

    def migrations(self, m):
        migration = m.get("migrations")
        if migration is None:
            if (self.root / "migrations").exists() or (self.root / "alembic.ini").exists():
                self.add(DECLARE, "MIG-01", "專案有 migrations，但 deployment.json 沒有 migrations 區段", "宣告 Migration 指令與本版的相容性", "deployment.json")
            return
        compatibility = migration.get("compatibility")
        if compatibility == "none":
            return
        if compatibility not in ("backward-compatible", "restore-plan"):
            self.add(DECLARE, "MIG-01", f'migrations.compatibility 為 "{compatibility}"', "填 backward-compatible、restore-plan 或 none", "deployment.json")
        elif not migration.get("notes"):
            self.add(DECLARE, "MIG-01", "migrations.notes 沒有填寫", "說明本版的資料庫變更，以及舊版程式為何仍可運作（或還原計畫）", "deployment.json")

    # ------------------------------------------------------------ PostgreSQL（docs/09、PostgreSQL 標準 v1.0）
    DB_DRIVERS = ("psycopg", "psycopg2", "psycopg2-binary", "psycopg-binary", "asyncpg", "pg8000")
    IDENT = re.compile(r"[a-z_][a-z0-9_]{0,62}")
    DBA_ONLY = re.compile(r"\b(CREATE|ALTER|DROP)\s+(ROLE|USER|GROUP)\b|\bREASSIGN\s+OWNED\b|\bDROP\s+OWNED\b|\b(CREATE|ALTER|DROP)\s+DATABASE\b"
                          r"|\bALTER\s+SYSTEM\b|\bREVOKE\b.*\bON\s+DATABASE\b|\bGRANT\b.*\bON\s+DATABASE\b|\bOWNER\s+TO\b|\bCREATE\s+SCHEMA\b"
                          r"|\bDROP\s+SCHEMA\b|\bCREATE\s+EXTENSION\b|\bpg_terminate_backend\b", re.I)
    GRANT = re.compile(r"\bGRANT\s+(?P<privs>.+?)\s+ON\s+(?P<obj>.+?)\s+TO\s+(?P<to>[^;\"')]+)", re.I)
    MEMBERSHIP = re.compile(r"\bGRANT\s+\"?[A-Za-z_][\w$]*\"?\s+TO\s+", re.I)
    BROAD = re.compile(r"\b(ALL|TRUNCATE|CREATE|TRIGGER|REFERENCES|MAINTAIN)\b", re.I)
    DDL = re.compile(r"\b(CREATE(\s+OR\s+REPLACE)?|ALTER|DROP)\s+(TABLE|VIEW|MATERIALIZED\s+VIEW|SEQUENCE|FUNCTION|PROCEDURE|TYPE|TRIGGER|INDEX(\s+CONCURRENTLY)?)\s+"
                     r"(IF\s+(NOT\s+)?EXISTS\s+)?\"?(?P<s>[A-Za-z_]\w*)\"?\.\"?(?P<t>[A-Za-z_]\w*)", re.I)
    DML = re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE(\s+TABLE)?)\s+\"?(?P<s>[A-Za-z_]\w*)\"?\.\"?(?P<t>[A-Za-z_]\w*)", re.I)
    SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_temp"}

    def template_values(self, m):
        text = self.read(m.get("configTemplate") or ".env.example") or ""
        values = {}
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def database_sources(self):
        """會下 SQL 的檔案：Python（含 migration 版本檔）與 .sql，不含測試；略過註解行。"""
        result = []
        for path in self.packaged_files():
            rel = path.relative_to(self.root).as_posix()
            parts = rel.split("/")
            if path.suffix not in (".py", ".sql") or "tests" in parts or "__pycache__" in parts or path.name.startswith("test_"):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            result.append((rel, ["" if l.lstrip().startswith(("#", "--")) else l for l in lines]))
        return result

    def database(self, m):
        db = m.get("database")
        lock = (self.read("requirements.lock") or "").lower()
        values = self.template_values(m)
        # 部門正式環境一律使用 PostgreSQL；SQLite 只用於開發與檢查，所以用到 SQLite 也要宣告 database
        urls = [values.get("DATABASE_URL", ""), str(((m.get("selfTest") or {}).get("env") or {}).get("DATABASE_URL") or "")]
        uses_db = any(re.search(rf"^{re.escape(d)}==", lock, re.M) for d in self.DB_DRIVERS + ("aiosqlite",)) \
            or any(u.lower().startswith(("postgres", "sqlite")) for u in urls) \
            or self.grep(self.python_sources(), r"^\s*(import|from)\s+(sqlite3|aiosqlite)\b|sqlite(\+\w+)?://", re.I)
        if db is None:
            if uses_db:
                self.add(DECLARE, "DB-01", "專案使用資料庫（PostgreSQL 或開發用的 SQLite），但 deployment.json 沒有 database 區段",
                         '加上 "database": {"name": "CIM", "schema": "<系統 schema>", "prefix": "<角色前綴>"}（見 references/deployment-json.md）', "deployment.json")
            return
        prefix = db.get("prefix") or ""
        roles_cfg = db.get("roles") or {}

        def role(key, suffix):
            return roles_cfg.get(key) or (prefix + suffix if prefix else "")
        roles = {"owner": role("owner", "_owner"), "rw": role("rw", "_rw"), "ro": role("ro", "_ro"),
                 "migrator": role("migrator", "_migrator"), "service": role("service", "_svc")}
        schema = db.get("schema") or ""
        problems = []
        if db.get("engine", "postgresql") != "postgresql":
            problems.append(f'engine 為 "{db.get("engine")}"（目前只支援 postgresql）')
        if not db.get("name"):
            problems.append("沒有 name（資料庫名稱）")
        if not self.IDENT.fullmatch(schema):
            problems.append(f'schema 為 "{schema}"（小寫英數與底線）')
        elif schema in ("public", "base") or schema.startswith("pg_"):
            problems.append(f"schema 不可為 {schema}")
        if not all(roles.values()):
            problems.append("沒有 prefix，也沒有在 roles 指定全部角色名稱")
        else:
            problems += [f'角色 {k} 為 "{v}"（小寫英數與底線）' for k, v in roles.items() if not self.IDENT.fullmatch(v)]
            if len(set(roles.values())) < len(roles):
                problems.append("owner、rw、ro、migrator、service 必須是不同的角色")
        for table in (db.get("sharedReads") or []) + (db.get("sharedWrites") or []):
            if not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", table or ""):
                problems.append(f'共用資料表 "{table}" 需寫成 schema.table')
        if db.get("sharedWrites") and not db.get("sharedWritesApproval"):
            problems.append("有 sharedWrites 但沒有 sharedWritesApproval（DBA 的核准紀錄）")
        if problems:
            self.add(ERROR, "DB-01", "；".join(problems), "修正 deployment.json 的 database", "deployment.json")
            return

        match = re.match(r"^[a-z][a-z0-9+.-]*://([^:@/\s]+)(:[^@]*)?@", values.get("DATABASE_URL", ""), re.I)
        if match and match.group(1).lower() in ("postgres", roles["owner"], roles["migrator"]):
            self.add(ERROR, "DB-02", f"設定範本的 DATABASE_URL 使用 {match.group(1)} 連線",
                     f"網站與服務改用 {roles['service']}；owner 不可登入，migration 帳號只在部署時輸入", m.get("configTemplate") or ".env.example")

        sources = self.database_sources()
        migration = m.get("migrations") or {}
        if migration.get("args") and not self.grep(sources, r"\bSET\s+(SESSION\s+|LOCAL\s+)?ROLE\b", re.I):
            self.add(ERROR, "DB-03", "有 Migration，但程式碼中找不到 SET ROLE",
                     f"Migration 連線後、建表前執行 SET ROLE {roles['owner']}（見 references/code-patterns.md §10）")
        hit = self.grep(sources, self.DBA_ONLY.pattern, re.I)
        if hit:
            self.add(ERROR, "DB-04", hit, "建立帳號、密碼、Schema、Owner 與資料庫層級的變更由 DBA 執行；從程式移除，改請使用者交給 DBA")
        allowed = {roles["rw"].lower(), roles["ro"].lower()}
        writable = {t.lower() for t in db.get("sharedWrites") or []}
        grant_hit = other_hit = None
        for rel, lines in sources:
            for number, line in enumerate(lines, 1):
                where = f"{rel} 第 {number} 行：{line.strip()[:140]}"
                g = self.GRANT.search(line)
                if not grant_hit:
                    if g:
                        to = g.group("to")
                        targets = [t.strip().split(" ")[0].lower() for t in to.replace('"', "").split(",") if t.strip()]
                        if self.BROAD.search(g.group("privs")) or (not re.search(r"[{%:]", to) and any(t not in allowed for t in targets)):
                            grant_hit = where
                    elif self.MEMBERSHIP.search(line):
                        grant_hit = where
                if not other_hit:
                    d = self.DDL.search(line)
                    w = self.DML.search(line)
                    if d and d.group("s").lower() != schema and d.group("s").lower() not in self.SYSTEM_SCHEMAS:
                        other_hit = where
                    elif w and w.group("s").lower() != schema and w.group("s").lower() not in self.SYSTEM_SCHEMAS:
                        table = f'{w.group("s")}.{w.group("t")}'.lower()
                        if table not in writable and not table.endswith(".kh_ad_employees"):
                            other_hit = where
        if grant_hit:
            self.add(ERROR, "DB-05", grant_hit, f"只授予 {roles['rw']}（SELECT/INSERT/UPDATE/DELETE）與 {roles['ro']}（SELECT）；不給 ALL、TRUNCATE、CREATE，不授予登入帳號或 PUBLIC")
        if other_hit:
            self.add(ERROR, "DB-06", other_hit, f"只修改本系統 Schema（{schema}）；共用資料要寫入時列在 sharedWrites 並附 DBA 核准")
        serial = self.grep(sources, r"\b(BIG|SMALL)?SERIAL\b")
        if serial:
            self.add(WARNING, "DB-07", serial, "新表改用 GENERATED ALWAYS AS IDENTITY")

    REVIEWABLE_ERRORS = {"DB-03", "DB-04", "DB-05", "DB-06"}   # 推測性規則：確認無誤後可用 reviewed 排除

    def apply_overrides(self, m):
        today = date.today().isoformat()
        exceptions = {e.get("rule"): e for e in m.get("exceptions") or []
                      if all(e.get(k) for k in ("rule", "reason", "risk", "owner", "plan", "until")) and e["until"] >= today}
        reviewed = {r.get("rule") for r in m.get("reviewed") or [] if r.get("note") and r.get("by")}
        can_except = {"DECL-05", "ARCH-04", "ARCH-05", "PATH-01", "PATH-02", "SSO-00", "SVC-02"}
        for finding in self.findings:
            if finding["rule"] in exceptions and finding["rule"] in can_except and finding["level"] == ERROR:
                finding["level"] = "已核准例外"
                finding["fix"] = f'例外至 {exceptions[finding["rule"]]["until"]}'
            elif finding["rule"] in reviewed and (finding["level"] == WARNING or (finding["level"] == ERROR and finding["rule"] in self.REVIEWABLE_ERRORS)):
                finding["level"] = "已人工確認"


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"找不到資料夾 {root}")
        return 2
    findings = Checker(root).run()
    blocking = [f for f in findings if f["level"] in (ERROR, DECLARE)]
    if "--json" in argv:
        print(json.dumps({"blocking": len(blocking), "findings": findings}, ensure_ascii=False, indent=2))
        return 1 if blocking else 0
    print(f"===== 部署標準 v1.2／資料庫標準 v1.0 自我檢查（靜態）：{root.name} =====")
    for level in (ERROR, DECLARE, WARNING, "已核准例外", "已人工確認"):
        items = [f for f in findings if f["level"] == level]
        if not items:
            continue
        print(f"\n── {level}（{len(items)}）")
        for f in items:
            print(f"{f['rule']}  {f['message']}")
            if f.get("where"):
                print(f"    位置：{f['where']}")
            print(f"    修正：{f['fix']}")
    print()
    if blocking:
        print(f"還有 {len(blocking)} 項必須處理。")
    else:
        print("靜態檢查沒有必須處理的項目。")
        print("仍需實測：以 URL_PREFIX=/<系統名稱> 啟動後 /health、/version 正常；執行後程式目錄沒有多出檔案；")
        print("正式模式搭配 AUTH_MODE=mock 會拒絕啟動。最後請使用者在 Windows 上用部署助手做完整檢查。")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
