from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from backend.app.core.backup_contract import (
    BACKUP_INVENTORY,
    BackupContractError,
    inventory_metadata,
    validate_artifact_path,
)


def test_backup_inventory_contains_metadata_only() -> None:
    metadata = inventory_metadata()
    assert set(metadata) == {
        "included_categories",
        "excluded_categories",
        "required_verifications",
    }
    rendered = repr(metadata).lower()
    for forbidden in ("row_content", "secret_value", "credential_value", "database_url"):
        assert forbidden not in rendered
    assert "encrypted_application_rows" in BACKUP_INVENTORY.included_categories
    assert {
        "temporary_extraction_sources",
        "logs",
        "secret_material",
        "environment_values",
        "database_credentials",
    } <= set(BACKUP_INVENTORY.excluded_categories)


def test_artifact_must_be_outside_repository_and_inside_temporary_root(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "isolated"
    outside.mkdir()
    artifact = outside / "synthetic.sql"

    validate_artifact_path(
        repository=repository,
        temporary_root=outside,
        artifact=artifact,
        require_file=False,
    )

    with pytest.raises(BackupContractError, match="Invalid backup artifact boundary"):
        validate_artifact_path(
            repository=repository,
            temporary_root=repository / "backup",
            artifact=repository / "backup" / "synthetic.sql",
            require_file=False,
        )

    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=outside,
            artifact=outside / ".." / "escaped.sql",
            require_file=False,
        )
    assert exc_info.value.code == "ARTIFACT_PATH_ESCAPE"


def test_artifact_file_size_and_suffix_are_enforced(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    artifact = isolated / "synthetic.dump"

    artifact.write_bytes(b"")
    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=isolated,
            artifact=artifact,
            require_file=True,
        )
    assert exc_info.value.code == "ARTIFACT_EMPTY"

    artifact.write_bytes(b"synthetic")
    validate_artifact_path(
        repository=repository,
        temporary_root=isolated,
        artifact=artifact,
        require_file=True,
        max_bytes=32,
    )
    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=isolated,
            artifact=artifact,
            require_file=True,
            max_bytes=4,
        )
    assert exc_info.value.code == "ARTIFACT_TOO_LARGE"


def test_symlink_artifact_is_rejected_when_supported(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    target = isolated / "target.sql"
    target.write_bytes(b"synthetic")
    artifact = isolated / "linked.sql"
    try:
        artifact.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is not available.")

    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=isolated,
            artifact=artifact,
            require_file=True,
        )
    assert exc_info.value.code == "ARTIFACT_LINK_REJECTED"


@pytest.mark.parametrize("target_outside_root", [False, True])
def test_artifact_with_symlink_parent_is_rejected_when_supported(
    tmp_path: Path,
    target_outside_root: bool,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    target = (
        tmp_path / "outside-parent"
        if target_outside_root
        else isolated / "real-parent"
    )
    target.mkdir()
    linked_parent = isolated / "linked-parent"
    try:
        linked_parent.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is not available.")

    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=isolated,
            artifact=linked_parent / "nested" / "synthetic.sql",
            require_file=False,
        )
    assert exc_info.value.code == "ARTIFACT_LINK_REJECTED"


def test_nested_artifact_without_linked_parents_is_allowed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = tmp_path / "isolated"
    nested = isolated / "first" / "second"
    nested.mkdir(parents=True)

    validate_artifact_path(
        repository=repository,
        temporary_root=isolated,
        artifact=nested / "synthetic.sql",
        require_file=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test.")
def test_artifact_with_junction_parent_is_rejected_when_supported(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    target = tmp_path / "junction-target"
    target.mkdir()
    junction = isolated / "junction-parent"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("Windows junction creation is not available.")

    with pytest.raises(BackupContractError) as exc_info:
        validate_artifact_path(
            repository=repository,
            temporary_root=isolated,
            artifact=junction / "synthetic.sql",
            require_file=False,
        )
    assert exc_info.value.code == "ARTIFACT_LINK_REJECTED"
