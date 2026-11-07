import jwt

from app.core.config import get_settings

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"


def _register(client, email="org@example.org", password="strong-pass-1"):
    return client.post(REGISTER, json={"email": email, "password": password})


def test_register_success(client):
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "org@example.org"
    assert body["role"] == "org_user"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_case_insensitive(client):
    _register(client, email="dup@example.org")
    response = _register(client, email="DUP@Example.org")

    assert response.status_code == 409


def test_register_short_password(client):
    assert _register(client, password="short").status_code == 422


def test_register_invalid_email(client):
    assert _register(client, email="not-an-email").status_code == 422


def test_login_success_returns_valid_token(client):
    user_id = _register(client).json()["id"]

    response = client.post(LOGIN, json={"email": "org@example.org", "password": "strong-pass-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60

    settings = get_settings()
    claims = jwt.decode(
        body["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert claims["sub"] == user_id
    assert claims["role"] == "org_user"
    assert claims["type"] == "access"


def test_login_wrong_password(client):
    _register(client)

    response = client.post(LOGIN, json={"email": "org@example.org", "password": "wrong-pass-1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_same_message(client):
    response = client.post(LOGIN, json={"email": "nobody@example.org", "password": "whatever-1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
