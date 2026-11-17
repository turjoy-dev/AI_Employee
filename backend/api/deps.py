"""FastAPI authentication dependencies and OAuth2 bearer token verification."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.database.connection import get_db
from backend.database.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Decode the Bearer JWT token and return the active User from the database."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require_exp": True},
        )
        subject: str | None = payload.get("sub")
        if not subject:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user: User | None = (
        db.execute(select(User).where(User.email == subject)).scalars().first()
    )
    if user is None:
        try:
            user = db.get(User, UUID(str(subject)))
        except ValueError:
            user = None

    if user is None or not user.is_active:
        raise credentials_exception

    return user
