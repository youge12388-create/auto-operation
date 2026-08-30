from __future__ import annotations

import base64
import hashlib

from argon2 import PasswordHasher
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .settings import get_settings

password_hasher = PasswordHasher()
SESSION_COOKIE = "content_ops_session"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret, salt="content-ops-session")


def make_session(user_id: str, session_version: int) -> str:
    return _serializer().dumps({"user_id": user_id, "session_version": session_version})


def read_session(value: str) -> tuple[str, int] | None:
    try:
        payload = _serializer().loads(value, max_age=60 * 60 * 24)
        user_id = str(payload["user_id"])
        # Cookies created before session revocation was introduced have no
        # version. They remain valid only while the user's version is still 1.
        session_version = int(payload.get("session_version", 1))
    except (BadSignature, KeyError, TypeError, ValueError):
        return None
    return user_id, session_version


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().app_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        raise ValueError("stored secret cannot be decrypted") from None


def current_user_from_session(session_cookie: str | None, db: Session) -> User:
    session = read_session(session_cookie) if session_cookie else None
    user = db.get(User, session[0]) if session else None
    if not user or not user.is_active or not session or user.session_version != session[1]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    return user


def get_current_user(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    return current_user_from_session(session_cookie, db)


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return dependency
