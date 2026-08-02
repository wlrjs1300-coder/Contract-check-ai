from __future__ import annotations

import os


ALLOWED_APP_ENVS = frozenset(
    {"test", "development", "pilot", "production", "prod"}
)
STRICT_APP_ENVS = frozenset({"pilot", "production", "prod"})


def get_app_env() -> str:
    return os.getenv("APP_ENV", "test").strip().lower() or "test"


def is_strict_environment() -> bool:
    return get_app_env() in STRICT_APP_ENVS
