"""Authentication router providing OAuth2 JWT login and initial admin registration."""

from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.config import get_settings
from backend.core.security import create_access_token, get_password_hash, limiter, verify_password
from backend.database.connection import get_db
from backend.database.models import User
from backend.schemas.auth import TokenResponse, UserRegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

DBSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register initial business administrator account",
)
@limiter.limit("20/minute")
def register_user(
    request: Request,
    payload: UserRegisterRequest,
    db: DBSession,
    authorization: Annotated[Optional[str], Header()] = None,
) -> User:
    """Create a new administrator account.

    Open registration is only allowed for the very first admin setup (`user_count == 0`).
    Once an admin exists, further registrations require an active admin Bearer JWT token.
    """
    existing_count = db.execute(select(func.count()).select_from(User)).scalar_one()
    if existing_count > 0:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Initial admin setup is already complete. Registration is disabled.",
            )
        raw_token = authorization.split(" ", 1)[1].strip()
        caller = get_current_user(token=raw_token, db=db)
        if caller.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can register additional users.",
            )

    duplicate = (
        db.execute(select(User).where(User.email == payload.email.strip().lower()))
        .scalars()
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        email=payload.email.strip().lower(),
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT Bearer access token",
)
@limiter.limit("20/minute")
def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
) -> TokenResponse:
    """Verify OAuth2 username (email) and password and issue a signed JWT token."""
    normalized_email = form_data.username.strip().lower()
    user = (
        db.execute(select(User).where(User.email == normalized_email))
        .scalars()
        .first()
    )
    if (
        user is None
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return TokenResponse(access_token=access_token, token_type="bearer")
