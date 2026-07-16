import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from redis import RedisError
import hashlib

from database import get_db
from db_model import DbUsers, UserRole
from redis_client import redis_client

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "development-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password."""
    return pwd.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored hash."""
    return pwd.verify(plain_password, hashed_password)


def verify_token(token: str, expected_type: str) -> dict:
    """Decode and validate a JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not payload or payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Invalid token type")

    if expected_type == "refresh":
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        key = f"blacklist:{token_hash}"
        try:
            blacklisted_token = redis_client.get(key)
            if blacklisted_token:
                raise HTTPException(status_code=401, detail="Blacklisted token")
        except RedisError:
            pass

    return payload


def create_access_token(user_id: int) -> str:
    """Build an access token for a user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Build a refresh token for a user."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> DbUsers:
    """Load the active user from the access-token cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Access token missing")

    payload = verify_token(token, "access")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.query(DbUsers).filter(DbUsers.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid User ID")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return user


def admin_required(current_user: DbUsers = Depends(get_current_user)) -> DbUsers:
    """Ensure that the current user is an administrator."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
