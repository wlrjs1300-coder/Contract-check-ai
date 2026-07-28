from __future__ import annotations
from backend.tests.support import encrypted_user

import os
import json
import base64

os.environ.setdefault("JWT_SECRET", "x" * 64)
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("DATA_ENCRYPTION_ACTIVE_KEY_ID", "synthetic-key-v1")
os.environ.setdefault(
    "EMAIL_LOOKUP_HMAC_KEY",
    base64.b64encode(bytes(range(64, 96))).decode("ascii"),
)
os.environ.setdefault(
    "DATA_ENCRYPTION_KEYS_JSON",
    json.dumps(
        [
            {
                "key_id": "synthetic-key-v1",
                "key": base64.b64encode(bytes(range(32))).decode("ascii"),
                "status": "active",
            },
            {
                "key_id": "synthetic-key-v0",
                "key": base64.b64encode(bytes(range(32, 64))).decode("ascii"),
                "status": "decrypt_only",
            },
        ]
    ),
)
os.environ.setdefault("RATE_LIMIT_LOGIN", "1000")
os.environ.setdefault("RATE_LIMIT_REGISTER", "1000")
os.environ.setdefault("RATE_LIMIT_UPLOAD", "1000")
os.environ.setdefault("RATE_LIMIT_EXTRACTION", "1000")
os.environ.setdefault("RATE_LIMIT_ANALYSIS_JOB", "1000")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")
os.environ.setdefault("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))
os.environ.setdefault("MAX_EXTRACTED_CHARACTERS", "2000000")
os.environ.setdefault("MAX_DOCUMENT_PAGES", "100")

import pytest
from fastapi import Depends
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.tests.support import TEST_USER_ID
from backend.app.core.auth import get_current_user, hash_password
from backend.app.db.database import (
    Base,
    enable_sqlite_foreign_keys,
    get_db,
)
from backend.app.db.models import User
from backend.app.main import app

TEST_DATABASE_URL = "sqlite://"
TEST_USER_EMAIL = "integration-user@example.invalid"
TEST_USER_PASSWORD = "test-password-1234"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
event.listen(test_engine, "connect", enable_sqlite_foreign_keys)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


def override_get_db():
    db: Session = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_test_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.id == TEST_USER_ID))
    if user is None:
        user = encrypted_user(
            id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            password_hash=hash_password(TEST_USER_PASSWORD),
            is_active=True,
            auth_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def override_get_current_user(
    db: Session = Depends(override_get_db),
) -> User:
    _ensure_test_user(db)
    user = db.scalar(select(User).where(User.id == TEST_USER_ID))
    if user is None:
        raise RuntimeError("Synthetic test user is unavailable.")
    return user


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture(autouse=True)
def reset_test_database():
    from backend.app.core.rate_limit import rate_limiter

    rate_limiter.reset()
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()
    try:
        _ensure_test_user(db)
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db: Session = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sqlite_test_engine():
    return test_engine


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)
