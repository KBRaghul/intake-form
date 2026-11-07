import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models import User, UserRole


def test_user_defaults(db_session):
    user = User(email="a@example.org", password_hash=hash_password("pw-123456"))
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.ORG_USER
    assert user.is_active is True
    assert user.created_at is not None


def test_email_must_be_unique(db_session):
    db_session.add(User(email="dup@example.org", password_hash="x"))
    db_session.flush()

    db_session.add(User(email="dup@example.org", password_hash="y"))
    with pytest.raises(IntegrityError):
        db_session.flush()
