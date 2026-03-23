"""Auth API — register, login, JWT tokens."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
import bcrypt

from app.models.session import get_db
from app.models.database import User
from app.schemas.models import UserCreate, UserOut, Token, LoginRequest
from app.config import settings

router = APIRouter()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "Email already registered")

    user = User(email=data.email, password_hash=_hash_password(data.password), full_name=data.full_name, phone=data.phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if not user or not _verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    return Token(access_token=_create_token(str(user.id)))
