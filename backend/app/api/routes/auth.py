from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_refresh_token, verify_password
from app.db.session import get_db
from app.models import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth_tokens import (
    build_token_response,
    clear_refresh_cookie,
    issue_refresh_token,
    set_refresh_cookie,
)

router = APIRouter()

INVALID_CREDENTIALS = "Invalid email or password"
INVALID_REFRESH = "Invalid refresh token"
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = _normalize_email(payload.email)

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None

    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == _normalize_email(payload.email)))

    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    raw = issue_refresh_token(db, user)
    db.commit()
    set_refresh_cookie(response, raw)
    return build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_REFRESH)

    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    if stored is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_REFRESH)

    now = datetime.now(UTC)

    if stored.revoked_at is not None:
        # A revoked token was reused: assume theft and end every session for this user.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_REFRESH)

    if stored.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_REFRESH)

    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_REFRESH)

    stored.revoked_at = now  # rotate: the old token can never be used again
    raw = issue_refresh_token(db, user)
    db.commit()
    set_refresh_cookie(response, raw)
    return build_token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> None:
    if refresh_token:
        stored = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        )
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            db.commit()

    clear_refresh_cookie(response)
