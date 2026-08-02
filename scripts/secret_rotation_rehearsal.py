from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from collections.abc import Iterator, Mapping

from jwt import DecodeError, decode as jwt_decode, encode as jwt_encode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.crypto import build_canonical_aad, decrypt, encrypt
from backend.app.core.email_lookup import build_email_lookup_hash, get_email_lookup_key
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.core.operations_config import (
    OperationsConfigurationError,
    validate_runtime_configuration,
)


def _encoded_key(start: int) -> str:
    return base64.b64encode(bytes((start + offset) % 256 for offset in range(32))).decode(
        "ascii"
    )


def _keyring(active: str, *, include_old: bool) -> str:
    keys: list[dict[str, str]] = []
    if include_old:
        keys.append(
            {
                "key_id": "synthetic-old",
                "key": _encoded_key(1),
                "status": "decrypt_only",
            }
        )
    keys.append(
        {
            "key_id": active,
            "key": _encoded_key(65),
            "status": "active",
        }
    )
    return json.dumps(keys, separators=(",", ":"))


def _base_environment() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "JWT_SECRET": "synthetic-jwt-current-with-unique-characters-123456789",
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
        "DATA_ENCRYPTION_KEYS_JSON": _keyring(
            "synthetic-current",
            include_old=False,
        ),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "synthetic-current",
        "EMAIL_LOOKUP_HMAC_KEY": _encoded_key(129),
        "CORS_ALLOWED_ORIGINS": "https://synthetic.example.invalid",
        "DATABASE_URL": "mysql+pymysql://synthetic:synthetic@db.invalid/synthetic",
        "DEBUG": "false",
        "UVICORN_RELOAD": "false",
        "ANALYSIS_PROVIDER": "unavailable",
        "MAX_UPLOAD_BYTES": "1048576",
        "MAX_EXTRACTED_CHARACTERS": "100000",
        "MAX_DOCUMENT_PAGES": "100",
        "RATE_LIMIT_LOGIN": "10",
        "RATE_LIMIT_REGISTER": "10",
        "RATE_LIMIT_UPLOAD": "10",
        "RATE_LIMIT_EXTRACTION": "10",
        "RATE_LIMIT_ANALYSIS_JOB": "10",
        "RATE_LIMIT_WINDOW_SECONDS": "60",
        "TRUST_PROXY_HEADERS": "false",
        "TRUSTED_PROXY_CIDRS": "",
        "REQUIRE_HTTPS": "true",
        "ALLOWED_HOSTS": "synthetic.example.invalid",
    }


@contextmanager
def _temporary_environment(values: Mapping[str, str]) -> Iterator[None]:
    original = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _required_and_weak_checks() -> None:
    values = _base_environment()
    missing = dict(values)
    missing.pop("JWT_SECRET")
    with _temporary_environment(missing):
        old = os.environ.pop("JWT_SECRET", None)
        try:
            try:
                validate_runtime_configuration()
            except Exception:
                pass
            else:
                raise AssertionError
        finally:
            if old is not None:
                os.environ["JWT_SECRET"] = old

    weak = dict(values)
    weak["JWT_SECRET"] = "placeholder-placeholder-placeholder-00"
    with _temporary_environment(weak):
        try:
            validate_runtime_configuration()
        except OperationsConfigurationError:
            return
    raise AssertionError


def _jwt_rotation_check() -> None:
    now = datetime.now(UTC)
    claims = {
        "sub": "00000000-0000-4000-8000-000000000001",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": "contract-check-api",
        "aud": "contract-check-client",
    }
    old_secret = "synthetic-jwt-old-with-unique-characters-123456789"
    new_secret = "synthetic-jwt-new-with-unique-characters-987654321"
    old_token = jwt_encode(claims, old_secret, algorithm="HS256")
    try:
        jwt_decode(
            old_token,
            new_secret,
            algorithms=["HS256"],
            audience="contract-check-client",
            issuer="contract-check-api",
        )
    except DecodeError:
        pass
    else:
        raise AssertionError

    new_token = jwt_encode(claims, new_secret, algorithm="HS256")
    jwt_decode(
        new_token,
        new_secret,
        algorithms=["HS256"],
        audience="contract-check-client",
        issuer="contract-check-api",
    )


def _encryption_rotation_check() -> None:
    aad = build_canonical_aad(
        resource_type="synthetic",
        record_id="rotation-rehearsal",
        field_name="value",
        owner_id="synthetic-owner",
        schema_version="rehearsal-v1",
    )
    initial_env = {
        "DATA_ENCRYPTION_KEYS_JSON": json.dumps(
            [
                {
                    "key_id": "synthetic-old",
                    "key": _encoded_key(1),
                    "status": "active",
                }
            ]
        ),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "synthetic-old",
    }
    with _temporary_environment(initial_env):
        old_envelope = encrypt(b"synthetic-only", aad=aad, keyring=get_encryption_keyring())

    rotated_env = {
        "DATA_ENCRYPTION_KEYS_JSON": _keyring("synthetic-new", include_old=True),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "synthetic-new",
    }
    with _temporary_environment(rotated_env):
        rotated = get_encryption_keyring()
        if decrypt(old_envelope, aad=aad, keyring=rotated) != b"synthetic-only":
            raise AssertionError
        if encrypt(b"synthetic-only", aad=aad, keyring=rotated).key_id != "synthetic-new":
            raise AssertionError

    missing_old_env = {
        "DATA_ENCRYPTION_KEYS_JSON": _keyring("synthetic-new", include_old=False),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "synthetic-new",
    }
    with _temporary_environment(missing_old_env):
        try:
            decrypt(old_envelope, aad=aad, keyring=get_encryption_keyring())
        except Exception:
            return
    raise AssertionError


def _email_lookup_rotation_check() -> None:
    email = "synthetic-user@example.invalid"
    with _temporary_environment({"EMAIL_LOOKUP_HMAC_KEY": _encoded_key(129)}):
        old_hash = build_email_lookup_hash(email, lookup_key=get_email_lookup_key())
    with _temporary_environment({"EMAIL_LOOKUP_HMAC_KEY": _encoded_key(161)}):
        new_hash = build_email_lookup_hash(email, lookup_key=get_email_lookup_key())
    if old_hash == new_hash:
        raise AssertionError


def run_rehearsal() -> tuple[dict[str, str], ...]:
    checks = (
        ("required_secret_validation", _required_and_weak_checks),
        ("jwt_rotation", _jwt_rotation_check),
        ("encryption_keyring_rotation", _encryption_rotation_check),
        ("email_lookup_rotation", _email_lookup_rotation_check),
    )
    results: list[dict[str, str]] = []
    for stage, check in checks:
        try:
            check()
        except Exception:
            results.append(
                {"stage": stage, "status": "FAIL", "safe_error_code": "REHEARSAL_FAILED"}
            )
        else:
            results.append({"stage": stage, "status": "PASS", "safe_error_code": "NONE"})
    return tuple(results)


def main() -> int:
    results = run_rehearsal()
    print(json.dumps({"results": results}, separators=(",", ":"), sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
