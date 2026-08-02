from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets as synthetic_secrets
import sys
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.api.extractions import (
    SyntheticOcrAdapter,
    SyntheticPdfRenderer,
    get_ocr_adapter,
    get_pdf_renderer,
)
from backend.app.core.operations_config import validate_runtime_configuration
from backend.app.services.analysis_provider_factory import (
    AnalysisProviderConfigError,
    create_analysis_provider,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PILOT_COMPOSE = REPOSITORY_ROOT / "compose.pilot.yaml"


@contextmanager
def _environment(values: dict[str, str]) -> Iterator[None]:
    original = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _strict_pilot_environment() -> dict[str, str]:
    encryption_key = base64.b64encode(synthetic_secrets.token_bytes(32)).decode()
    return {
        "APP_ENV": "pilot",
        "JWT_SECRET": synthetic_secrets.token_urlsafe(48),
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "pilot-key-v1",
        "DATA_ENCRYPTION_KEYS_JSON": json.dumps(
            [
                {
                    "key_id": "pilot-key-v1",
                    "key": encryption_key,
                    "status": "active",
                }
            ]
        ),
        "EMAIL_LOOKUP_HMAC_KEY": base64.b64encode(
            synthetic_secrets.token_bytes(32)
        ).decode(),
        "CORS_ALLOWED_ORIGINS": "https://pilot.example.invalid",
        "DATABASE_URL": "mysql+pymysql://pilot@db.example.invalid/pilot",
        "DEBUG": "false",
        "UVICORN_RELOAD": "false",
        "ANALYSIS_PROVIDER": "synthetic",
        "MAX_UPLOAD_BYTES": str(20 * 1024 * 1024),
        "MAX_EXTRACTED_CHARACTERS": "2000000",
        "MAX_DOCUMENT_PAGES": "100",
        "RATE_LIMIT_LOGIN": "10",
        "RATE_LIMIT_REGISTER": "5",
        "RATE_LIMIT_UPLOAD": "10",
        "RATE_LIMIT_EXTRACTION": "20",
        "RATE_LIMIT_ANALYSIS_JOB": "10",
        "RATE_LIMIT_WINDOW_SECONDS": "60",
        "TRUST_PROXY_HEADERS": "false",
        "TRUSTED_PROXY_CIDRS": "",
        "REQUIRE_HTTPS": "true",
        "ALLOWED_HOSTS": "pilot.example.invalid",
    }


def validate_repository() -> None:
    compose_text = PILOT_COMPOSE.read_text(encoding="utf-8").lower()
    forbidden_compose = (
        "mysql-data",
        "3306:3306",
        "jwt_secret:",
        "email_lookup_hmac_key:",
        "data_encryption_keys_json:",
        "http://",
        "https://",
    )
    if any(value in compose_text for value in forbidden_compose):
        raise RuntimeError("PILOT_COMPOSE_BOUNDARY_INVALID")
    if "!override []" not in compose_text:
        raise RuntimeError("PILOT_DB_PORT_BOUNDARY_INVALID")
    if "pilot-data" not in compose_text or "pilot-network" not in compose_text:
        raise RuntimeError("PILOT_RESOURCE_BOUNDARY_INVALID")
    if "${pilot_network_subnet:?required}" not in compose_text:
        raise RuntimeError("PILOT_NETWORK_SUBNET_BOUNDARY_INVALID")

    pilot_env = _strict_pilot_environment()
    with _environment(pilot_env):
        validate_runtime_configuration()
        if create_analysis_provider().provider_name != "synthetic":
            raise RuntimeError("PILOT_PROVIDER_BOUNDARY_INVALID")
        try:
            create_analysis_provider(provider_name="fake")
        except AnalysisProviderConfigError:
            pass
        else:
            raise RuntimeError("PILOT_PROVIDER_BOUNDARY_INVALID")
        os.environ["OCR_ADAPTER"] = "synthetic"
        try:
            get_ocr_adapter()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("PILOT_OCR_BOUNDARY_INVALID")
        if isinstance(get_pdf_renderer(), SyntheticPdfRenderer):
            raise RuntimeError("PILOT_PDF_BOUNDARY_INVALID")

    with _environment({"APP_ENV": "production"}):
        for provider_name in ("synthetic", "fake"):
            try:
                create_analysis_provider(provider_name=provider_name)
            except AnalysisProviderConfigError:
                continue
            raise RuntimeError("PRODUCTION_PROVIDER_BOUNDARY_INVALID")

    if isinstance(SyntheticOcrAdapter, type) is False:
        raise RuntimeError("PILOT_OCR_BOUNDARY_INVALID")


def main() -> int:
    try:
        validate_repository()
    except Exception:
        print("FAIL SYNTHETIC_PILOT_BOUNDARY_INVALID")
        return 1
    print("PASS SYNTHETIC_PILOT_BOUNDARIES_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
