import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser
from app.core.config import get_settings
from app.main import app
from app.models import User, UserRole

ME = "/api/me"
ADMIN_ONLY = "/_test/admin-only"
CREDS = {"email": "org@example.org", "password": "strong-pass-1"}

_test_router = APIRouter()


@_test_router.get(ADMIN_ONLY)
def _admin_only(admin: AdminUser) -> dict:
    return {"ok": True}


app.include_router(_test_router)


def _login(client) -> str:
    client.post("/api/auth/register", json=CREDS)
    return client.post("/api/auth/login", json=CREDS).json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(db_session) -> User:
    return db_session.scalar(select(User).where(User.email == CREDS["email"]))


def _craft_token(sub: str, token_type="access", minutes=15, secret=None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "role": "org_user",
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret or settings.jwt_secret_key, settings.jwt_algorithm)


def test_me_with_valid_token(client):
    response = client.get(ME, headers=_auth(_login(client)))

    assert response.status_code == 200
    assert response.json()["email"] == CREDS["email"]


def test_me_without_token(client):
    response = client.get(ME)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_garbage_token(client):
    assert client.get(ME, headers=_auth("not-a-jwt")).status_code == 401


def test_expired_token(client, db_session):
    _login(client)
    token = _craft_token(str(_user(db_session).id), minutes=-1)

    assert client.get(ME, headers=_auth(token)).status_code == 401


def test_wrong_token_type(client, db_session):
    _login(client)
    token = _craft_token(str(_user(db_session).id), token_type="refresh")

    assert client.get(ME, headers=_auth(token)).status_code == 401


def test_token_signed_with_other_secret(client, db_session):
    _login(client)
    token = _craft_token(
        str(_user(db_session).id), secret="some-other-secret-that-is-long-enough-for-hs256"
    )

    assert client.get(ME, headers=_auth(token)).status_code == 401


def test_unknown_user_id(client):
    token = _craft_token(str(uuid.uuid4()))

    assert client.get(ME, headers=_auth(token)).status_code == 401


def test_deactivated_user_is_rejected_immediately(client, db_session):
    token = _login(client)
    _user(db_session).is_active = False
    db_session.flush()

    assert client.get(ME, headers=_auth(token)).status_code == 401


def test_org_user_cannot_reach_admin_route(client):
    response = client.get(ADMIN_ONLY, headers=_auth(_login(client)))

    assert response.status_code == 403


def test_admin_can_reach_admin_route(client, db_session):
    token = _login(client)
    _user(db_session).role = UserRole.ADMIN
    db_session.flush()

    assert client.get(ADMIN_ONLY, headers=_auth(token)).status_code == 200


def test_demoted_admin_loses_access_immediately(client, db_session):
    _login(client)
    user = _user(db_session)
    user.role = UserRole.ADMIN
    db_session.flush()
    token = client.post("/api/auth/login", json=CREDS).json()["access_token"]

    user.role = UserRole.ORG_USER
    db_session.flush()

    assert client.get(ADMIN_ONLY, headers=_auth(token)).status_code == 403
