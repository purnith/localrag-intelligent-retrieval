from datetime import datetime, timedelta, timezone
from typing import Annotated

import asyncpg
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.config import get_settings
from app.database import get_pool
from app.schemas import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])
settings = get_settings()
password_hash = PasswordHash.recommended()
SESSION_COOKIE = "localrag_session"


def create_session_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.jwt_expiration_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


async def get_current_user(
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserResponse:
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        payload = jwt.decode(session, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from error

    row = await get_pool().fetchrow(
        "SELECT id, display_name, email FROM users WHERE id = $1 AND email IS NOT NULL",
        user_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return UserResponse(**dict(row))


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, response: Response) -> UserResponse:
    display_name = request.display_name.strip()
    if not display_name:
        raise HTTPException(422, "Display name cannot be empty")
    email = request.email.lower()
    hashed_password = password_hash.hash(request.password)
    try:
        row = await get_pool().fetchrow(
            """
            INSERT INTO users(display_name, email, password_hash)
            VALUES($1, $2, $3) RETURNING id, display_name, email
            """,
            display_name,
            email,
            hashed_password,
        )
    except asyncpg.UniqueViolationError as error:
        raise HTTPException(409, "An account with this email already exists") from error

    user = UserResponse(**dict(row))
    set_session_cookie(response, create_session_token(user.id))
    return user


@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest, response: Response) -> UserResponse:
    row = await get_pool().fetchrow(
        """
        SELECT id, display_name, email, password_hash
        FROM users WHERE LOWER(email) = LOWER($1)
        """,
        str(request.email),
    )
    if row is None or not row["password_hash"] or not password_hash.verify(
        request.password, row["password_hash"]
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    user = UserResponse(
        id=row["id"], display_name=row["display_name"], email=row["email"]
    )
    set_session_cookie(response, create_session_token(user.id))
    return user


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
