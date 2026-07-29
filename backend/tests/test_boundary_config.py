from __future__ import annotations

import pytest

from backend.app.core.boundary_config import (
    BoundaryConfigurationError,
    get_boundary_config,
)


@pytest.mark.parametrize(
    "name",
    [
        "MAX_UPLOAD_BYTES",
        "MAX_EXTRACTED_CHARACTERS",
        "MAX_DOCUMENT_PAGES",
        "RATE_LIMIT_LOGIN",
        "RATE_LIMIT_REGISTER",
        "RATE_LIMIT_UPLOAD",
        "RATE_LIMIT_EXTRACTION",
        "RATE_LIMIT_ANALYSIS_JOB",
        "RATE_LIMIT_WINDOW_SECONDS",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_invalid_boundary_values_fail_closed(monkeypatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(BoundaryConfigurationError) as exc_info:
        get_boundary_config()
    assert value not in str(exc_info.value)


def test_safe_test_defaults_are_bounded(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    for name in (
        "MAX_UPLOAD_BYTES",
        "MAX_EXTRACTED_CHARACTERS",
        "MAX_DOCUMENT_PAGES",
        "RATE_LIMIT_LOGIN",
        "RATE_LIMIT_REGISTER",
        "RATE_LIMIT_UPLOAD",
        "RATE_LIMIT_EXTRACTION",
        "RATE_LIMIT_ANALYSIS_JOB",
        "RATE_LIMIT_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    config = get_boundary_config()
    assert config.max_upload_bytes == 20 * 1024 * 1024
    assert config.max_extracted_characters == 2_000_000
    assert config.max_document_pages == 100


def test_production_requires_explicit_boundary_values(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
    with pytest.raises(BoundaryConfigurationError):
        get_boundary_config()
