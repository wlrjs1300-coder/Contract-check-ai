from __future__ import annotations

from dataclasses import dataclass
import os


class AuthConfigurationError(RuntimeError):
    """Raised when JWT configuration is invalid."""


@dataclass(frozen=True)
class JwtConfig:
    secret: str
    access_token_expire_minutes: int
    algorithm: str = "HS256"
    issuer: str = "contract-check-api"
    audience: str = "contract-check-client"


def _read_access_token_expire_minutes() -> int:
    value = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15").strip()
    if not value:
        raise AuthConfigurationError("Invalid JWT access token expiry.")
    if not value.isdigit():
        raise AuthConfigurationError("Invalid JWT access token expiry.")

    parsed = int(value)
    if parsed < 5 or parsed > 60:
        raise AuthConfigurationError("Invalid JWT access token expiry.")
    return parsed


def get_jwt_config() -> JwtConfig:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise AuthConfigurationError("Invalid JWT secret.")
    if len(secret.encode("utf-8")) < 32:
        raise AuthConfigurationError("Invalid JWT secret.")
    if "\x00" in secret:
        raise AuthConfigurationError("Invalid JWT secret.")

    issuer = "contract-check-api"
    audience = "contract-check-client"
    return JwtConfig(
        secret=secret,
        access_token_expire_minutes=_read_access_token_expire_minutes(),
        algorithm="HS256",
        issuer=issuer,
        audience=audience,
    )
