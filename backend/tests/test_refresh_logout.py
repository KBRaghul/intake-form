from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import RefreshToken

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
REFRESH = "/api/auth/refresh"
LOGOUT = "/api/auth/logout"
CREDS = {"email": "org@example.org", "password": "strong-pass-1"}


def _register_and_login(client):
    client.post(REGISTER, json=CREDS)
    return client.post(LOGIN, json=CREDS)


def test_login_sets_httponly_refresh_cookie(client):
    response = _register_and_login(client)

    cookie_header = response.headers["set-cookie"]
    assert "refresh_token=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/api/auth" in cookie_header
    assert "samesite=lax" in cookie_header.lower()


def test_refresh_returns_new_access_token_and_rotates(client):
    login = _register_and_login(client)
    old_refresh = login.cookies["refresh_token"]

    response = client.post(REFRESH)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies["refresh_token"] != old_refresh


def test_refresh_without_cookie(client):
    assert client.post(REFRESH).status_code == 401


def test_reused_refresh_token_revokes_all_sessions(client):
    login = _register_and_login(client)
    old_refresh = login.cookies["refresh_token"]

    rotated = client.post(REFRESH)
    new_refresh = rotated.cookies["refresh_token"]

    # Attacker replays the old token
    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh)
    assert client.post(REFRESH).status_code == 401

    # The legitimate user's newer token is now revoked too
    client.cookies.clear()
    client.cookies.set("refresh_token", new_refresh)
    assert client.post(REFRESH).status_code == 401


def test_expired_refresh_token(client, db_session):
    _register_and_login(client)

    token = db_session.scalar(select(RefreshToken))
    token.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()

    assert client.post(REFRESH).status_code == 401


def test_logout_revokes_token_and_clears_cookie(client):
    login = _register_and_login(client)
    refresh_value = login.cookies["refresh_token"]

    response = client.post(LOGOUT)
    assert response.status_code == 204

    # Even if someone kept a copy, it no longer works
    client.cookies.clear()
    client.cookies.set("refresh_token", refresh_value)
    assert client.post(REFRESH).status_code == 401


def test_logout_without_cookie_is_fine(client):
    assert client.post(LOGOUT).status_code == 204
