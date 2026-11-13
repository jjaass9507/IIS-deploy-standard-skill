"""範例系統：符合《Python 程式與平台部署標準 v1.2》的最小網站。"""
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template_string, session, url_for

from . import config


class PrefixMiddleware:
    """掛在 IIS 子應用程式（/sample-app）下：把 URL_PREFIX 交給 WSGI 的 SCRIPT_NAME。"""

    def __init__(self, app, prefix):
        self.app, self.prefix = app, prefix

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            return self.app(environ, start_response)
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]


PAGE = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>範例系統</title>
<h1>範例系統 {{ version }}</h1>
<p>{% if account %}已登入：{{ account }}（{{ role }}）{% else %}尚未登入{% endif %}</p>
<p><a href="{{ url_for('home') }}">首頁</a>　<a href="{{ url_for('version') }}">版本</a></p></html>"""


def create_app():
    config.check_production()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY or "dev-only-" + "x" * 32,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        SESSION_COOKIE_PATH=config.URL_PREFIX or "/",
        PERMANENT_SESSION_LIFETIME=8 * 3600,
    )

    handler = RotatingFileHandler(config.log_dir() / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("start version=%s env=%s auth=%s prefix=%s", config.APP_VERSION, config.APP_ENV, config.AUTH_MODE, config.URL_PREFIX or "/")

    from .auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/version")
    def version():
        return jsonify(application=config.APPLICATION, version=config.APP_VERSION)

    @app.get("/")
    def home():
        session.setdefault("visited", True)  # 建立 Session，讓 Cookie 設定可被檢查
        return render_template_string(PAGE, version=config.APP_VERSION, account=session.get("account"), role=session.get("role"))

    if config.URL_PREFIX:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, config.URL_PREFIX)
    return app
