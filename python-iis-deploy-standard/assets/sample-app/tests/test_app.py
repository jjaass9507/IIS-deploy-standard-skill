import importlib

import pytest


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "mock")
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    monkeypatch.setenv("URL_PREFIX", "/sample-app")
    monkeypatch.setenv("APP_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_CONFIG_FILE", str(tmp_path / "none.env"))
    from sample_app import config

    importlib.reload(config)
    import sample_app

    return sample_app.create_app().test_client()


def test_health_and_version(client):
    assert client.get("/sample-app/health").get_json() == {"status": "ok"}
    assert client.get("/sample-app/version").get_json() == {"application": "sample-app", "version": "9.9.9"}
    assert client.get("/health").status_code == 404  # 只在子路徑下


def test_login_logout_requires_csrf(client):
    assert client.get("/sample-app/api/auth/me").status_code == 401
    assert client.post("/sample-app/api/auth/login", json={"account": "admin", "password": "wrong"}).status_code == 401
    token = client.post("/sample-app/api/auth/login", json={"account": "admin", "password": "password"}).get_json()["csrf_token"]
    assert client.get("/sample-app/api/auth/me").get_json()["role"] == "admin"
    assert client.post("/sample-app/api/auth/logout").status_code == 403
    assert client.post("/sample-app/api/auth/logout", headers={"X-CSRF-Token": token}).status_code == 200
    assert client.get("/sample-app/api/auth/me").status_code == 401


def test_sso_disabled_by_default(client):
    assert client.get("/sample-app/auth/sso", headers={"X-IIS-WindowsAuthToken": "1A2B"}).status_code == 404


def test_production_rejects_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "mock")
    monkeypatch.setenv("APP_CONFIG_FILE", str(tmp_path / "none.env"))
    from sample_app import config

    importlib.reload(config)
    with pytest.raises(SystemExit):
        config.check_production()
