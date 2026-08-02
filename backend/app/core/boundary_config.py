from __future__ import annotations

import os
from dataclasses import dataclass

from backend.app.core.runtime_environment import is_strict_environment

class BoundaryConfigurationError(RuntimeError):
    """Raised when request-boundary limits are missing or unsafe."""


@dataclass(frozen=True)
class BoundaryConfig:
    max_upload_bytes: int
    max_extracted_characters: int
    max_document_pages: int
    rate_limit_login: int
    rate_limit_register: int
    rate_limit_upload: int
    rate_limit_extraction: int
    rate_limit_analysis_job: int
    rate_limit_window_seconds: int


_DEFAULTS = {
    "MAX_UPLOAD_BYTES": 20 * 1024 * 1024,
    "MAX_EXTRACTED_CHARACTERS": 2_000_000,
    "MAX_DOCUMENT_PAGES": 100,
    "RATE_LIMIT_LOGIN": 10,
    "RATE_LIMIT_REGISTER": 5,
    "RATE_LIMIT_UPLOAD": 10,
    "RATE_LIMIT_EXTRACTION": 20,
    "RATE_LIMIT_ANALYSIS_JOB": 10,
    "RATE_LIMIT_WINDOW_SECONDS": 60,
}
_MAXIMUMS = {
    "MAX_UPLOAD_BYTES": 20 * 1024 * 1024,
    "MAX_EXTRACTED_CHARACTERS": 2_000_000,
    "MAX_DOCUMENT_PAGES": 100,
    "RATE_LIMIT_LOGIN": 10_000,
    "RATE_LIMIT_REGISTER": 10_000,
    "RATE_LIMIT_UPLOAD": 10_000,
    "RATE_LIMIT_EXTRACTION": 10_000,
    "RATE_LIMIT_ANALYSIS_JOB": 10_000,
    "RATE_LIMIT_WINDOW_SECONDS": 3600,
}


def _read_positive_int(name: str, *, production: bool) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if production:
            raise BoundaryConfigurationError("Invalid boundary configuration.")
        return _DEFAULTS[name]
    try:
        value = int(raw)
    except ValueError:
        raise BoundaryConfigurationError("Invalid boundary configuration.") from None
    if value <= 0 or value > _MAXIMUMS[name]:
        raise BoundaryConfigurationError("Invalid boundary configuration.")
    return value


def get_boundary_config() -> BoundaryConfig:
    production = is_strict_environment()
    values = {
        name.lower(): _read_positive_int(name, production=production)
        for name in _DEFAULTS
    }
    return BoundaryConfig(**values)
