from __future__ import annotations

from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status
from jwt import DecodeError, ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError
from jwt import decode as jwt_decode
from jwt import encode as jwt_encode
from jwt.exceptions import ImmatureSignatureError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_jwt_config
from backend.app.db.database import get_db
from backend.app.db.models import User


_PASSWORD_HASHER = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH: Final[str] = _PASSWORD_HASHER.hash("synthetic-dummy-password-only")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to authenticate request.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def normalize_email(email: str) -> str:
    trimmed = (email or "").strip()
    normalized = trimmed.casefold()
    if not normalized:
        return ""
    return normalized


def _validate_email_syntax(email: str) -> None:
    if "\x00" in email:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    if email != email.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    if " " in email:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    if email.count("@") != 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    if len(email) > 254:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )


def normalize_and_validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Invalid email format.",
        )
    _validate_email_syntax(normalized)
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Invalid password.")
    if "\x00" in password:
        raise ValueError("Invalid password.")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password, password_hash)
    except Exception:
        return False


def issue_jwt_for_user(user: User) -> tuple[str, int]:
    config = get_jwt_config()
    issued_at = int(datetime.now(UTC).timestamp())
    expires_at = issued_at + config.access_token_expire_minutes * 60

    payload = {
        "sub": str(user.id),
        "iat": issued_at,
        "exp": expires_at,
        "jti": str(uuid4()),
        "iss": config.issuer,
        "aud": config.audience,
        "ver": int(user.auth_version),
    }
    token = jwt_encode(payload, config.secret, algorithm=config.algorithm)
    return token, config.access_token_expire_minutes * 60


def _ensure_canonical_uuid(candidate: str, *, field: str) -> UUID:
    parsed = UUID(candidate)
    if str(parsed) != candidate:
        raise ValueError(f"Invalid {field} UUID.")
    return parsed


def _decode_bearer_token(token: str) -> dict[str, object]:
    config = get_jwt_config()
    try:
        payload = jwt_decode(
            token,
            config.secret,
            algorithms=[config.algorithm],
            audience=config.audience,
            issuer=config.issuer,
            options={
                "require": ["sub", "iat", "exp", "jti", "iss", "aud", "ver"],
            },
        )
    except (DecodeError, ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError, ImmatureSignatureError, TypeError, ValueError):
        raise _unauthorized() from None
    except Exception:
        raise _unauthorized() from None

    try:
        sub_value = payload["sub"]
        jti_value = payload["jti"]
        iat = payload["iat"]
        exp = payload["exp"]
        ver_value = payload["ver"]

        if type(sub_value) is not str:
            raise ValueError
        if type(jti_value) is not str:
            raise ValueError
        if type(iat) is not int or type(exp) is not int:
            raise ValueError

        if type(ver_value) is not int or ver_value <= 0:
            raise ValueError

        now = datetime.now(UTC).timestamp()
        if iat - 60 > now:
            raise ValueError
        if exp + 60 < now:
            raise ValueError
        if exp <= iat:
            raise ValueError

        subject = _ensure_canonical_uuid(sub_value, field="sub")
        jti = _ensure_canonical_uuid(jti_value, field="jti")
        ver = ver_value
    except Exception:
        raise _unauthorized() from None

    return {
        "sub": str(subject),
        "jti": str(jti),
        "ver": ver,
    }


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized()

    claims = _decode_bearer_token(token)
    user_id = claims["sub"]

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _unauthorized()
    if not user.is_active:
        raise _unauthorized()
    if user.auth_version != claims["ver"]:
        raise _unauthorized()
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        _ = verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None
    return user
