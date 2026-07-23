from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jwt import decode as jwt_decode
from jwt import encode as jwt_encode
from sqlalchemy import select

from backend.app.core.auth import get_current_user
from backend.app.core.auth import hash_password
from backend.app.core.config import AuthConfigurationError, get_jwt_config
from backend.app.core import config as auth_config
from backend.app.db.models import User
from backend.app.main import app


@contextmanager
def _use_real_auth():
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


def _assert_unauthorized(response) -> None:
    assert response.status_code == 401
    assert response.json()["detail"] == "Unable to authenticate request."
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def _assert_invalid_credentials(response) -> None:
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials."
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def _jwt_claims(overrides: dict[str, object] | None = None) -> dict[str, object]:
    config = get_jwt_config()
    now = int(datetime.now(UTC).timestamp())
    claims: dict[str, object] = {
        "sub": "00000000-0000-4000-8000-000000000001",
        "iat": now,
        "exp": now + config.access_token_expire_minutes * 60,
        "jti": "00000000-0000-4000-8000-000000000002",
        "iss": config.issuer,
        "aud": config.audience,
        "ver": 1,
    }
    if overrides:
        claims.update(overrides)
    return claims


def _encode_token(payload: dict[str, object]) -> str:
    config = get_jwt_config()
    return jwt_encode(payload, config.secret, algorithm=config.algorithm)


def _auth_me_with_token(token: str):
    with TestClient(app) as client:
        with _use_real_auth():
            return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def _register_user(email: str, password: str, client: TestClient):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login_user(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_jwt_config_validation_and_app_state_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not hasattr(app.state, "jwt_config")
    assert not hasattr(app.state, "jwt_secret")
    assert not hasattr(app.state, "secret")

    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(AuthConfigurationError):
        get_jwt_config()

    monkeypatch.setenv("JWT_SECRET", "   ")
    with pytest.raises(AuthConfigurationError):
        get_jwt_config()

    monkeypatch.setenv("JWT_SECRET", "x" * 31)
    with pytest.raises(AuthConfigurationError):
        get_jwt_config()

    def _null_secret(name: str, default: str | None = None) -> str:
        if name == "JWT_SECRET":
            return f"{'x' * 32}\x00"
        if name == "JWT_ACCESS_TOKEN_EXPIRE_MINUTES":
            return "15"
        return "" if default is None else default

    with monkeypatch.context() as null_patch:
        null_patch.setattr(auth_config.os, "getenv", _null_secret)
        with pytest.raises(AuthConfigurationError):
            get_jwt_config()

    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    for ttl in ["4", "61", "0", "-1", "invalid"]:
        monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", ttl)
        with pytest.raises(AuthConfigurationError):
            get_jwt_config()

    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    config = get_jwt_config()
    assert config.access_token_expire_minutes == 15


def test_register_email_normalization_and_password_boundaries(db_session) -> None:
    with TestClient(app) as client:
        first = _register_user("  User@Test-User.EXAMPLE.invalid  ", "Password12345!", client)
        assert first.status_code == 200
        assert first.json()["email"] == "user@test-user.example.invalid"

        duplicate = _register_user("\tUSER@Test-User.EXAMPLE.invalid\t", "Password12345!", client)
        assert duplicate.status_code == 409

        assert _register_user(
            "short@example.invalid",
            "12345678901",
            client,
        ).status_code == 400
        assert _register_user(
            "long@example.invalid",
            "1" * 129,
            client,
        ).status_code == 400
        assert _register_user(
            "nullbyte@example.invalid",
            "Bad\x00Pass123!",
            client,
        ).status_code == 400

        spaced = _register_user(
            "space@example.invalid",
            "  Password12345!  ",
            client,
        )
        assert spaced.status_code == 200
        assert spaced.json().get("password") is None
        assert spaced.json().get("password_hash") is None

    user = db_session.scalar(select(User).where(User.email == "space@example.invalid"))
    assert user is not None
    assert user.password_hash != "  Password12345!  "
    assert user.password_hash.startswith("$argon2")


@pytest.mark.parametrize("email", ["bad@@example.invalid", " ", "@bad.invalid", "bad@"])
def test_register_invalid_email(email: str) -> None:
    with TestClient(app) as client:
        response = _register_user(email, "Password12345!", client)
        assert response.status_code == 400


def test_login_failures_return_401(db_session) -> None:
    with TestClient(app) as client:
        missing_email = _login_user(client, "nobody@example.invalid", "WrongPassword111")
        _assert_invalid_credentials(missing_email)

    with TestClient(app) as client:
        registered = _register_user("active-user@example.invalid", "Password12345!", client)
        assert registered.status_code == 200
        wrong_pw = _login_user(client, "active-user@example.invalid", "WrongPassword111")
        _assert_invalid_credentials(wrong_pw)

    inactive = db_session.scalar(select(User).where(User.email == "inactive-user@example.invalid"))
    if inactive is None:
        inactive = User(
            id=str(uuid4()),
            email="inactive-user@example.invalid",
            password_hash=hash_password("Password12345!"),
            is_active=False,
        )
        db_session.add(inactive)
    else:
        inactive.password_hash = hash_password("Password12345!")
        inactive.is_active = False
    db_session.commit()

    with TestClient(app) as client:
        inactive_login = _login_user(client, "inactive-user@example.invalid", "Password12345!")
        _assert_invalid_credentials(inactive_login)


@pytest.mark.parametrize(
    ("missing",),
    [("sub",), ("jti",), ("iat",), ("exp",), ("iss",), ("aud",), ("ver",)],
)
def test_auth_me_required_claims_rejected(missing: str) -> None:
    claims = _jwt_claims()
    claims.pop(missing)
    _assert_unauthorized(_auth_me_with_token(_encode_token(claims)))


def test_auth_me_authorization_failures() -> None:
    with TestClient(app) as client:
        with _use_real_auth():
            _assert_unauthorized(client.get("/auth/me"))
            _assert_unauthorized(client.get("/auth/me", headers={"Authorization": "Token abc"}))
            _assert_unauthorized(client.get("/auth/me", headers={"Authorization": "Bearer "}))
            _assert_unauthorized(client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}))

    cfg = get_jwt_config()
    wrong_sig = jwt_encode(_jwt_claims(), "y" * 64, algorithm=cfg.algorithm)
    _assert_unauthorized(_auth_me_with_token(wrong_sig))

    now = int(datetime.now(UTC).timestamp())
    _assert_unauthorized(_auth_me_with_token(_encode_token(_jwt_claims({"exp": now - 1, "iat": now - 4000}))))
    _assert_unauthorized(_auth_me_with_token(_encode_token(_jwt_claims({"iat": now + 7200, "exp": now + 9000}))))
    _assert_unauthorized(_auth_me_with_token(_encode_token(_jwt_claims({"iss": "other"}))))
    _assert_unauthorized(_auth_me_with_token(_encode_token(_jwt_claims({"aud": "other"}))))


def test_auth_me_nonexistent_inactive_and_version_failures(db_session) -> None:
    _assert_unauthorized(_auth_me_with_token(_jwt_claims({"sub": "00000000-0000-4000-8000-00000000aaaa"})))
    _assert_unauthorized(_auth_me_with_token(_jwt_claims({"ver": 9999})))

    inactive = db_session.scalar(select(User).where(User.email == "inactive-me@example.invalid"))
    if inactive is None:
        inactive = User(
            id="00000000-0000-4000-8000-000000000099",
            email="inactive-me@example.invalid",
            password_hash=hash_password("Password12345!"),
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()
    _assert_unauthorized(_auth_me_with_token(_jwt_claims({"sub": inactive.id})))


@pytest.mark.parametrize(
    ("override"),
    [
        {"sub": True},
        {"sub": 1},
        {"sub": "AAAAAAAA-0000-4000-8000-000000000001"},
        {"sub": "{00000000-0000-4000-8000-000000000001}"},
        {"jti": 1},
        {"jti": True},
        {"jti": "BBBBBBBB-0000-4000-8000-000000000002"},
        {"iat": True},
        {"iat": "1"},
        {"iat": 1.0},
        {"exp": True},
        {"exp": "1"},
        {"exp": 1.0},
        {"ver": True},
        {"ver": False},
        {"ver": "1"},
        {"ver": 1.0},
        {"ver": 0},
        {"ver": -1},
        {"exp": 100, "iat": 100},
        {"exp": 50, "iat": 100},
    ],
)
def test_auth_me_strict_claim_attack_override(override: dict[str, object]) -> None:
    _assert_unauthorized(_auth_me_with_token(_encode_token(_jwt_claims(override))))


def test_jwt_login_and_me_contract() -> None:
    with TestClient(app) as client:
        register = _register_user("login-ok@example.invalid", "Password12345!", client)
        assert register.status_code == 200

        login = _login_user(client, "login-ok@example.invalid", "Password12345!")
        assert login.status_code == 200

    token_json = login.json()
    assert token_json["token_type"] == "bearer"

    config = get_jwt_config()
    assert token_json["expires_in"] == config.access_token_expire_minutes * 60
    token = token_json["access_token"]

    payload: dict[str, object] = jwt_decode(
        token,
        config.secret,
        algorithms=["HS256"],
        audience=config.audience,
        issuer=config.issuer,
    )
    assert {"sub", "iat", "exp", "jti", "iss", "aud", "ver"}.issubset(payload.keys())
    assert "email" not in payload
    assert "password" not in payload
    assert "password_hash" not in payload
    assert "owner_id" not in payload
    assert "resource_id" not in payload

    me = _auth_me_with_token(token)
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["email"] == "login-ok@example.invalid"
    assert "password" not in me_body
    assert "password_hash" not in me_body
