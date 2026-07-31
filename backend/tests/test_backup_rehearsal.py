from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.mysql_backup_rehearsal import (
    MySQLRehearsal,
    RehearsalError,
    _safe_result,
)
from scripts.validate_backup_artifacts import validate_repository


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_safe_rehearsal_result_contains_no_payload_or_path() -> None:
    result = _safe_result("backup_artifact", "FAIL", "BACKUP_COMMAND_FAILED")
    assert result == {
        "stage": "backup_artifact",
        "status": "FAIL",
        "safe_error_code": "BACKUP_COMMAND_FAILED",
    }
    rendered = json.dumps(result)
    for forbidden in (
        "DATABASE_URL",
        "MYSQL_PASSWORD",
        "mysql+pymysql",
        "synthetic-backup-user",
        "synthetic-contract",
    ):
        assert forbidden not in rendered


def test_rehearsal_error_exposes_safe_code_only() -> None:
    error = RehearsalError("RESTORE_COMMAND_FAILED")
    assert error.code == "RESTORE_COMMAND_FAILED"
    assert str(error) == "Synthetic backup/restore rehearsal failed."


def test_cleanup_failure_is_not_reported_as_success(monkeypatch) -> None:
    rehearsal = MySQLRehearsal()
    rehearsal.created_containers.append("synthetic-rehearsal-container")
    monkeypatch.setattr(
        "scripts.mysql_backup_rehearsal.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )
    with pytest.raises(RehearsalError) as exc_info:
        rehearsal.cleanup()
    assert exc_info.value.code == "CLEANUP_FAILED"


def test_backup_artifact_validator_passes_repository() -> None:
    assert validate_repository(REPOSITORY_ROOT) == frozenset()
    completed = subprocess.run(
        [sys.executable, "scripts/validate_backup_artifacts.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "PASS BACKUP_ARTIFACT_BOUNDARY_VALID"
    assert completed.stderr == ""


def test_backup_artifact_validator_detects_tracked_dump(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    artifact = tmp_path / "synthetic.dump"
    artifact.write_bytes(b"synthetic")
    subprocess.run(["git", "add", "-f", "synthetic.dump"], cwd=tmp_path, check=True)
    assert validate_repository(tmp_path) == {"TRACKED_BACKUP_ARTIFACT"}


def test_compose_keeps_root_credential_in_database_service_only() -> None:
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert compose.count("\n      MYSQL_ROOT_PASSWORD:") == 1
    database_section = compose.split("\n  contract-db:", 1)[1].split(
        "\n  migrate:", 1
    )[0]
    assert "MYSQL_ROOT_PASSWORD:" in database_section


def test_compose_blocks_api_and_worker_until_migration_succeeds() -> None:
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
    api_section = compose.split("\n  api:", 1)[1].split("\n  worker:", 1)[0]
    worker_section = compose.split("\n  worker:", 1)[1].split("\nvolumes:", 1)[0]
    assert "condition: service_completed_successfully" in api_section
    assert "condition: service_completed_successfully" in worker_section


def test_runbook_forbids_automatic_downgrade_rollback() -> None:
    runbook = (
        REPOSITORY_ROOT / "docs/deployment/mysql-backup-restore-runbook.md"
    ).read_text(encoding="utf-8")
    assert "Alembic downgrade를 자동 rollback으로 사용하지 않는다" in runbook
    assert "migration 실패 시 API·worker 시작을 차단" in runbook
