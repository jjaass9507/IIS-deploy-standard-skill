"""設定：位置由環境變數 APP_CONFIG_FILE 提供（正式環境為 shared\\config\\.env）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# 開發機沒有設定 APP_CONFIG_FILE 時，才讀專案資料夾的 .env
load_dotenv(os.environ.get("APP_CONFIG_FILE") or ROOT / ".env", encoding="utf-8-sig")


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _dir(name, default):
    """寫入位置一律來自環境變數；開發機未設定時用專案外的暫存位置。"""
    path = Path(os.environ.get(name) or default)
    path.mkdir(parents=True, exist_ok=True)
    return path


_DEV_HOME = Path(os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp") / "sample-app-dev"

APPLICATION = "sample-app"
APP_VERSION = os.environ.get("APP_VERSION", "dev")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
URL_PREFIX = "/" + os.environ.get("URL_PREFIX", "").strip("/") if os.environ.get("URL_PREFIX", "").strip("/") else ""
SECRET_KEY = os.environ.get("SECRET_KEY", "")
AUTH_MODE = os.environ.get("AUTH_MODE", "mock").strip().lower()
AUTH_SSO_ENABLED = _bool("AUTH_SSO_ENABLED")
SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE")
AD_SERVER = os.environ.get("AD_SERVER", "")
AD_DOMAIN = os.environ.get("AD_DOMAIN", "")
AD_CA_FILE = os.environ.get("AD_CA_FILE", "")
PLATFORM_USERS = dict(
    item.split("=", 1) for item in os.environ.get("PLATFORM_USERS", "").split(",") if "=" in item
)


def log_dir():
    return _dir("APP_LOG_DIR", _DEV_HOME / "logs")


def data_dir():
    return _dir("APP_DATA_DIR", _DEV_HOME / "data")


def check_production():
    """正式環境的防呆：不符合就拒絕啟動。"""
    if APP_ENV != "production":
        return
    problems = []
    if AUTH_MODE != "ad":
        problems.append("AUTH_MODE 必須是 ad（目前 %s）" % AUTH_MODE)
    if len(SECRET_KEY) < 32:
        problems.append("SECRET_KEY 至少 32 個字元")
    if not AD_SERVER:
        problems.append("AD_SERVER 未設定")
    if problems:
        raise SystemExit("正式環境設定不正確：" + "；".join(problems))
