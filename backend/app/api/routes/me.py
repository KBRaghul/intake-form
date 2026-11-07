from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import User
from app.schemas.auth import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    return user
