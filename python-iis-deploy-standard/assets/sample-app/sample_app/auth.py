"""登入：AD 帳密（LDAPS）與 Windows SSO 兩個入口，共用同一套 Session 與平台授權。"""
import secrets
import ssl
import sys

from flask import Blueprint, abort, jsonify, request, session

from . import config

bp = Blueprint("auth", __name__)

MOCK_USERS = {"admin": "admin", "viewer": "viewer"}  # 只在 AUTH_MODE=mock 使用，密碼固定為 password


def _platform_role(account):
    """AD 驗證成功不等於開通：平台另外記錄已開通的帳號與角色。"""
    users = MOCK_USERS if config.AUTH_MODE == "mock" else config.PLATFORM_USERS
    return users.get(account.lower())


def _sign_in(account):
    role = _platform_role(account)
    if role is None:
        return jsonify(error="此帳號尚未開通平台權限"), 403
    session.clear()  # 登入後更新 Session
    session["account"] = account.lower()
    session["role"] = role
    session["csrf"] = secrets.token_urlsafe(32)
    session.pop("sso_paused", None)
    return jsonify(authenticated=True, account=account.lower(), role=role, csrf_token=session["csrf"])


def verify_ad(account, secret):
    """以 AD 驗證帳密（SIMPLE bind）。

    部門預設不強制驗證 AD 伺服器的憑證；AD_SERVER 使用 ldaps:// 且設定了 AD_CA_FILE 時才驗證，
    環境準備好之後不必改程式就能開啟。
    """
    from ldap3 import Connection, Server, Tls

    use_ssl = config.AD_SERVER.lower().startswith("ldaps://")
    tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=config.AD_CA_FILE) if (use_ssl and config.AD_CA_FILE) else None
    server = Server(config.AD_SERVER, use_ssl=use_ssl, tls=tls, connect_timeout=8)
    with Connection(server, user="%s\\%s" % (config.AD_DOMAIN, account), password=secret) as conn:
        return bool(conn.bound)


def windows_account(handle):
    """由 HttpPlatformHandler 轉交的 Windows 權杖 Handle 取得帳號；用完一定要 CloseHandle。"""
    import ctypes
    from ctypes import wintypes

    advapi32, kernel32 = ctypes.windll.advapi32, ctypes.windll.kernel32
    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(wintypes.HANDLE(handle), 1, None, 0, ctypes.byref(size))  # TokenUser
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(wintypes.HANDLE(handle), 1, buffer, size, ctypes.byref(size)):
            return None
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents
        name, domain = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
        name_size, domain_size, use = wintypes.DWORD(256), wintypes.DWORD(256), wintypes.DWORD(0)
        if not advapi32.LookupAccountSidW(None, sid, name, ctypes.byref(name_size), domain, ctypes.byref(domain_size), ctypes.byref(use)):
            return None
        return name.value
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))


def require_csrf():
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not session.get("csrf") or not token or not secrets.compare_digest(token, session["csrf"]):
        abort(403, description="CSRF Token 不正確")


@bp.get("/api/auth/me")
def me():
    if "account" not in session:
        return jsonify(authenticated=False), 401
    return jsonify(authenticated=True, account=session["account"], role=session["role"], csrf_token=session["csrf"])


@bp.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or request.form
    account, secret = (data.get("account") or "").strip(), data.get("password") or ""
    if config.AUTH_MODE == "mock":
        valid = account.lower() in MOCK_USERS and secret == "password"
    elif config.AUTH_MODE == "ad":
        valid = bool(account and secret) and verify_ad(account, secret)
    else:
        valid = False
    if not valid:
        return jsonify(error="帳號或密碼錯誤"), 401
    return _sign_in(account)


@bp.get("/auth/sso")
def sso():
    if not config.AUTH_SSO_ENABLED or config.AUTH_MODE != "ad":
        return jsonify(authenticated=False, error="未啟用 Windows 登入"), 404
    if session.get("sso_paused"):
        return jsonify(authenticated=False, error="已登出，請以帳密登入或重新選擇 Windows 登入"), 401
    raw = request.headers.get("X-IIS-WindowsAuthToken", "")
    try:
        handle = int(raw, 16)
    except ValueError:
        return jsonify(authenticated=False, error="沒有收到 Windows 權杖"), 401
    account = windows_account(handle) if sys.platform == "win32" else None
    if not account:
        return jsonify(authenticated=False, error="無法由 Windows 權杖取得身分"), 401
    return _sign_in(account)


@bp.post("/api/auth/logout")
def logout():
    require_csrf()
    session.clear()
    session["sso_paused"] = True  # 登出後暫停自動 SSO
    return jsonify(authenticated=False)
