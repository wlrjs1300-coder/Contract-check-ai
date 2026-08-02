from __future__ import annotations

from dataclasses import dataclass
import stat
from pathlib import Path


class BackupContractError(RuntimeError):
    """Raised when a backup artifact violates the repository boundary."""

    def __init__(self, code: str) -> None:
        super().__init__("Invalid backup artifact boundary.")
        self.code = code


@dataclass(frozen=True)
class BackupInventory:
    included_categories: tuple[str, ...]
    excluded_categories: tuple[str, ...]
    required_verifications: tuple[str, ...]


BACKUP_INVENTORY = BackupInventory(
    included_categories=(
        "application_schema",
        "alembic_revision",
        "encrypted_application_rows",
        "indexes_constraints_tables",
    ),
    excluded_categories=(
        "temporary_extraction_sources",
        "logs",
        "local_paths",
        "secret_material",
        "environment_values",
        "database_credentials",
    ),
    required_verifications=(
        "artifact_nonempty",
        "artifact_size_limit",
        "schema_parity",
        "alembic_head",
        "encrypted_envelope",
        "owner_relationship",
        "required_indexes_constraints",
        "readiness",
        "synthetic_query",
        "new_write",
    ),
)

BACKUP_ARTIFACT_SUFFIXES = frozenset(
    {".sql", ".dump", ".bak", ".backup", ".sql.gz", ".dump.gz"}
)
DEFAULT_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def inventory_metadata() -> dict[str, tuple[str, ...]]:
    return {
        "included_categories": BACKUP_INVENTORY.included_categories,
        "excluded_categories": BACKUP_INVENTORY.excluded_categories,
        "required_verifications": BACKUP_INVENTORY.required_verifications,
    }


def _resolved(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        raise BackupContractError("ARTIFACT_PATH_INVALID") from None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _has_linked_parent(
    *,
    temporary_root: Path,
    artifact: Path,
) -> bool:
    try:
        relative_parent = artifact.parent.relative_to(temporary_root)
    except ValueError:
        return False
    if ".." in relative_parent.parts:
        return False

    current = temporary_root
    if _is_link_or_reparse(current):
        return True
    for part in relative_parent.parts:
        current /= part
        if _is_link_or_reparse(current):
            return True
    return False


def validate_artifact_path(
    *,
    repository: Path,
    temporary_root: Path,
    artifact: Path,
    require_file: bool,
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> None:
    repository_resolved = _resolved(repository)
    temporary_root_resolved = _resolved(temporary_root)
    artifact_resolved = _resolved(artifact)

    if _has_linked_parent(
        temporary_root=temporary_root,
        artifact=artifact,
    ) or _is_link_or_reparse(artifact):
        raise BackupContractError("ARTIFACT_LINK_REJECTED")
    if _is_relative_to(temporary_root_resolved, repository_resolved):
        raise BackupContractError("ARTIFACT_ROOT_IN_REPOSITORY")
    if not _is_relative_to(artifact_resolved, temporary_root_resolved):
        raise BackupContractError("ARTIFACT_PATH_ESCAPE")
    if artifact.name in {"", ".", ".."}:
        raise BackupContractError("ARTIFACT_PATH_INVALID")
    if not any(
        artifact.name.lower().endswith(suffix)
        for suffix in BACKUP_ARTIFACT_SUFFIXES
    ):
        raise BackupContractError("ARTIFACT_SUFFIX_INVALID")

    if not require_file:
        return
    if not artifact.is_file():
        raise BackupContractError("ARTIFACT_MISSING")
    size = artifact.stat().st_size
    if size <= 0:
        raise BackupContractError("ARTIFACT_EMPTY")
    if size > max_bytes:
        raise BackupContractError("ARTIFACT_TOO_LARGE")
