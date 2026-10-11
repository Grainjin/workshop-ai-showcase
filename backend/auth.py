"""Password hashing, JWT sessions, and role dependencies."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    JWT_PRIVATE_KEY,
    JWT_PUBLIC_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from backend.core.clock import parse_dt, utc_now
from backend.database import SessionLocal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
PASSWORD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")
EMAIL_PASSWORD_PROVIDER = "email_password"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_now() -> datetime:
    return utc_now()


def to_iso(value: datetime | str | None) -> str | None:
    parsed = parse_dt(value)
    return parsed.isoformat() if parsed is not None else None


def validate_password_policy(password: str) -> str:
    if not PASSWORD_POLICY.match(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters and include upper, lower, and digit",
        )
    return password


def prehash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(prehash_password(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if pwd_context.verify(prehash_password(plain_password), hashed_password):
            return True
    except ValueError:
        pass

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _signing_key():
    if ALGORITHM.startswith("RS"):
        return JWT_PRIVATE_KEY
    return JWT_PRIVATE_KEY or ""


def _verify_key():
    if ALGORITHM.startswith("RS"):
        return JWT_PUBLIC_KEY
    return JWT_PUBLIC_KEY


def create_jwt_token(data: dict, expires_delta: timedelta, token_type: str):
    to_encode = data.copy()
    expire = get_now() + expires_delta
    token_jti = str(uuid.uuid4())
    to_encode.update(
        {
            "exp": expire,
            "iat": get_now(),
            "jti": token_jti,
            "type": token_type,
        }
    )
    encoded_jwt = jwt.encode(to_encode, _signing_key(), algorithm=ALGORITHM)
    return encoded_jwt, token_jti, expire


def create_access_token(data: dict) -> str:
    token, _, _ = create_jwt_token(
        data,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )
    return token


def create_refresh_token(data: dict):
    return create_jwt_token(
        data,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
    )


def create_user_token_data(user: models.User, session_id: str | None = None) -> dict:
    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role,
    }
    if session_id:
        payload["sid"] = session_id
    return payload


def store_refresh_token(
    user: models.User,
    refresh_token: str,
    token_jti: str,
    expires_at: datetime,
    db: Session,
):
    token_record = models.RefreshToken(
        user_id=user.id,
        token_jti=token_jti,
        token_hash=hash_token(refresh_token),
        created_at=get_now(),
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(token_record)
    return token_record


def create_token_pair(user: models.User, db: Session):
    refresh_placeholder = create_user_token_data(user)
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
        refresh_placeholder
    )
    access_token = create_access_token(create_user_token_data(user, refresh_jti))
    store_refresh_token(user, refresh_token, refresh_jti, refresh_expires_at, db)
    return access_token, refresh_token


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _verify_key(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def ensure_user_can_login(user: models.User):
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is banned",
        )


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def find_user_by_email(db: Session, email: str) -> models.User | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return (
        db.query(models.User)
        .filter(func.lower(models.User.email) == normalized)
        .first()
    )


def get_password_identity(user: models.User, db: Session):
    return (
        db.query(models.AuthenticationIdentity)
        .filter(
            models.AuthenticationIdentity.user_id == user.id,
            models.AuthenticationIdentity.identity_provider == EMAIL_PASSWORD_PROVIDER,
        )
        .first()
    )


def create_password_identity(
    user: models.User,
    password: str,
    db: Session,
    *,
    verified: bool = False,
):
    now = get_now()
    identity = models.AuthenticationIdentity(
        user_id=user.id,
        identity_provider=EMAIL_PASSWORD_PROVIDER,
        provider_subject=normalize_email(user.email),
        password_hash=hash_password(password),
        created_at=now,
        verified_at=now if verified else None,
    )
    if verified:
        user.email_verified_at = now
    db.add(identity)
    return identity


def get_user_from_token(token: str, db: Session) -> models.User:
    payload = decode_token(token)
    token_type = payload.get("type")
    if token_type not in [None, "access"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required",
        )

    user_id = payload.get("user_id") or payload.get("sub")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        user = find_user_by_email(db, payload.get("sub"))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        user_id = user.id

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    session_id = payload.get("sid")
    if session_id:
        session = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.token_jti == session_id)
            .first()
        )
        if session is None or session.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
            )
        if parse_dt(session.expires_at) <= get_now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
            )

    ensure_user_can_login(user)
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    return get_user_from_token(token, db)


EMAIL_NOT_VERIFIED_DETAIL = "Verify your email address to continue"


def ensure_email_verified(user: models.User) -> models.User:
    """Customers and providers must confirm their email before using the app.

    Admins are created by seed or by hand and are exempt. Account endpoints
    (/me, /auth/*) stay open so an unverified user can verify or sign out.
    """
    if user.role != "admin" and user.email_verified_at is None:
        raise HTTPException(status_code=403, detail=EMAIL_NOT_VERIFIED_DETAIL)
    return user


def require_verified_user(current_user: models.User = Depends(get_current_user)):
    return ensure_email_verified(current_user)


def require_role(required_role: str, current_user: models.User):
    if current_user.role != required_role:
        raise HTTPException(
            status_code=403,
            detail=f"Only {required_role}s can access this resource",
        )
    return current_user


def require_customer(current_user: models.User = Depends(get_current_user)):
    return ensure_email_verified(require_role("customer", current_user))


def require_provider(current_user: models.User = Depends(get_current_user)):
    return ensure_email_verified(require_role("provider", current_user))


def require_admin(current_user: models.User = Depends(get_current_user)):
    return require_role("admin", current_user)


def validate_refresh_token(refresh_token: str, db: Session):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    token_jti = payload.get("jti")
    user_id = payload.get("user_id")
    if not token_jti or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_record = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_jti == token_jti,
            models.RefreshToken.token_hash == hash_token(refresh_token),
        )
        .first()
    )
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )
    if token_record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    if parse_dt(token_record.expires_at) <= get_now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    ensure_user_can_login(user)
    return user, token_record


def revoke_refresh_token(refresh_token: str, db: Session):
    user, token_record = validate_refresh_token(refresh_token, db)
    token_record.revoked_at = get_now()
    db.commit()
    return user


def revoke_user_refresh_tokens(user: models.User, db: Session) -> int:
    return (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .update(
            {models.RefreshToken.revoked_at: get_now()},
            synchronize_session=False,
        )
    )
