from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

from backend.app.core.secret_lifecycle import (
    BACKEND_SECRET_NAMES,
    PUBLIC_FRONTEND_CONFIGURATION,
    SECRET_INVENTORY,
    SecretLifecycleState,
    inventory_metadata,
    secret_names_for_service,
)
from scripts.secret_rotation_rehearsal import run_rehearsal
from scripts.validate_secret_boundaries import scan_content


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_inventory_contains_metadata_only_and_distinct_lifecycle_models() -> None:
    metadata = inventory_metadata()
    names = {item["name"] for item in metadata}
    assert {
        "DATABASE_URL",
        "MYSQL_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
        "JWT_SECRET",
        "EMAIL_LOOKUP_HMAC_KEY",
        "DATA_ENCRYPTION_KEYS_JSON",
        "DATA_ENCRYPTION_ACTIVE_KEY_ID",
        "PROVIDER_API_KEY",
    } <= names
    assert all("value" not in item and "secret" not in item for item in metadata)

    definitions = {item.name: item for item in SECRET_INVENTORY}
    assert SecretLifecycleState.DECRYPT_ONLY in definitions[
        "DATA_ENCRYPTION_KEYS_JSON"
    ].lifecycle_states
    assert SecretLifecycleState.DECRYPT_ONLY not in definitions[
        "JWT_SECRET"
    ].lifecycle_states
    assert SecretLifecycleState.COMPATIBILITY in definitions[
        "EMAIL_LOOKUP_HMAC_KEY"
    ].lifecycle_states
    assert not definitions["PROVIDER_API_KEY"].currently_configured


def test_backend_secrets_are_separate_from_public_frontend_configuration() -> None:
    assert "VITE_API_BASE_URL" in PUBLIC_FRONTEND_CONFIGURATION
    assert BACKEND_SECRET_NAMES.isdisjoint(PUBLIC_FRONTEND_CONFIGURATION)
    assert all(not item.frontend_allowed for item in SECRET_INVENTORY)


def test_service_secret_scope_matches_compose() -> None:
    assert secret_names_for_service("api") == {
        "DATABASE_URL",
        "JWT_SECRET",
        "EMAIL_LOOKUP_HMAC_KEY",
        "DATA_ENCRYPTION_KEYS_JSON",
        "DATA_ENCRYPTION_ACTIVE_KEY_ID",
    }
    assert secret_names_for_service("worker") == {
        "DATABASE_URL",
        "DATA_ENCRYPTION_KEYS_JSON",
        "DATA_ENCRYPTION_ACTIVE_KEY_ID",
    }
    assert secret_names_for_service("migrate") == {"DATABASE_URL"}
    assert secret_names_for_service("contract-db") == {
        "MYSQL_PASSWORD",
        "MYSQL_ROOT_PASSWORD",
    }

    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
    sections = {}
    for service in ("contract-db", "migrate", "api", "worker"):
        match = re.search(
            rf"(?ms)^  {re.escape(service)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:|\Z)",
            compose,
        )
        assert match is not None
        sections[service] = match.group(1)
    for service, section in sections.items():
        for secret_name in secret_names_for_service(service):
            assert f"{secret_name}:" in section
    for secret_name in secret_names_for_service("api") - secret_names_for_service(
        "worker"
    ):
        assert f"{secret_name}:" not in sections["worker"]
    for secret_name in secret_names_for_service("api") - {"DATABASE_URL"}:
        assert f"{secret_name}:" not in sections["migrate"]


def test_synthetic_rehearsal_covers_rotation_impacts_without_secret_output() -> None:
    results = run_rehearsal()
    assert {item["stage"] for item in results} == {
        "required_secret_validation",
        "jwt_rotation",
        "encryption_keyring_rotation",
        "email_lookup_rotation",
    }
    assert all(item["status"] == "PASS" for item in results)
    rendered = json.dumps(results)
    for forbidden in (
        "mysql+pymysql://",
        "synthetic-jwt-current",
        "synthetic-jwt-old",
        "synthetic-jwt-new",
        "DATA_ENCRYPTION_KEYS_JSON",
        "EMAIL_LOOKUP_HMAC_KEY",
    ):
        assert forbidden not in rendered


def test_boundary_scanner_detects_prohibited_files_and_material() -> None:
    assert "PRIVATE_KEY_MATERIAL" in scan_content(
        Path("config/private.txt"),
        "-----BEGIN " + "PRIVATE KEY-----\nnot-real\n-----END PRIVATE KEY-----",
    )
    assert "TOKEN_MATERIAL" in scan_content(
        Path("src/config.py"),
        "provider_token = 'sk-" + ("a" * 24) + "'",
    )
    assert "SECRET_LITERAL" in scan_content(
        Path("src/config.py"),
        "JWT_SECRET = 'unapproved-literal-value-without-safe-marker'",
    )
    assert not scan_content(
        Path("backend/tests/fixtures/synthetic.py"),
        "JWT_SECRET = 'synthetic-test-value'",
    )


def test_env_example_contains_names_only() -> None:
    lines = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assignments = [line for line in lines if line and not line.startswith("#")]
    assert assignments
    assert all(line.endswith("=") and line.count("=") == 1 for line in assignments)


def test_boundary_validation_cli_passes_repository() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_secret_boundaries.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "PASS SECRET_BOUNDARIES_VALID"
    assert completed.stderr == ""
