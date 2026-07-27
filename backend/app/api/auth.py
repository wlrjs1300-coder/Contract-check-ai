from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.auth import (
    authenticate_user,
    hash_password,
    issue_jwt_for_user,
    normalize_and_validate_email,
    get_current_user,
    resolve_user_email,
)
from backend.app.core.email_lookup import build_email_lookup_hash
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
)
from backend.app.services.scalar_metadata_encryption import encrypt_user_email
from backend.app.schemas.auth import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthMeResponse,
    AuthRegisterRequest,
    AuthRegisterResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthRegisterResponse)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthRegisterResponse:
    email = normalize_and_validate_email(payload.email)
    try:
        password_hash = hash_password(payload.password)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid password.",
        )

    lookup_hash = build_email_lookup_hash(email)
    if (
        db.scalar(select(User).where(User.email_lookup_hash == lookup_hash))
        is not None
        or db.scalar(select(User).where(User.email == email)) is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="A user with that email already exists.",
        )

    user_id = str(uuid4())
    try:
        email_encrypted = encrypt_user_email(
            email,
            user_id=user_id,
            keyring=get_encryption_keyring(),
        )
    except ScalarEncryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to prepare account data.",
        ) from exc
    user = User(
        id=user_id,
        email=email,
        email_encrypted=email_encrypted,
        email_lookup_hash=lookup_hash,
        password_hash=password_hash,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A user with that email already exists.",
        )
    db.refresh(user)

    return AuthRegisterResponse(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at.replace(microsecond=0).isoformat() + "Z",
    )


@router.post("/login", response_model=AuthLoginResponse)
def login(
    payload: AuthLoginRequest,
    db: Session = Depends(get_db),
) -> AuthLoginResponse:
    email = normalize_and_validate_email(payload.email)
    try:
        user = authenticate_user(
            db,
            email=email,
            password=payload.password,
        )
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored encrypted data is unavailable.",
        ) from exc
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = issue_jwt_for_user(
        user=user,
    )
    return AuthLoginResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user)) -> AuthMeResponse:
    try:
        email = resolve_user_email(current_user).value
    except ScalarDecryptionError as exc:
        raise HTTPException(
            status_code=500,
            detail="Stored encrypted data is unavailable.",
        ) from exc
    if not isinstance(email, str):
        raise HTTPException(
            status_code=500,
            detail="Stored encrypted data is unavailable.",
        )
    return AuthMeResponse(
        user_id=current_user.id,
        email=email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.replace(microsecond=0).isoformat() + "Z",
    )
