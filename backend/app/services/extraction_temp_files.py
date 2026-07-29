from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile


TEMP_ROOT_ENV = "EXTRACTION_TEMP_ROOT"
TEMP_ROOT_NAME = "contract-check-ai-extractions"
UPLOAD_CHUNK_SIZE = 1024 * 1024
REQUEST_DIRECTORY_PREFIX = "request-"
REQUEST_DIRECTORY_MARKER_NAME = "request-directory.json"
REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION = 1
REQUEST_DIRECTORY_CLOCK_SKEW_SECONDS = 120
MAX_REQUEST_DIRECTORY_MARKER_SIZE_BYTES = 8 * 1024


class UploadSizeLimitExceededError(Exception):
    pass


class OriginalCleanupError(Exception):
    pass


class UnsafeCleanupTargetError(OriginalCleanupError):
    """삭제 시 비안전한 대상 경로/변경 이슈."""


class CleanupOperationError(OriginalCleanupError):
    """임시 I/O 삭제 동작 실패."""


@dataclass(frozen=True)
class RequestDirectory:
    path: Path
    device: int
    inode: int
    request_id: str | None = None
    created_at: str | None = None
    lease_updated_at: str | None = None
    schema_version: int | None = None
    process_id: int | None = None


@dataclass(frozen=True)
class RequestMarker:
    schema_version: int
    request_id: str
    created_at_utc: str
    lease_updated_at_utc: str
    process_id: int
    cleanup_state: str = "active"


_ALLOWED_MARKER_KEYS = {
    "schema_version",
    "request_id",
    "created_at_utc",
    "lease_updated_at_utc",
    "process_id",
    "cleanup_state",
}
_ALLOWED_CLEANUP_STATES = {"active", "orphan"}


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _to_aware_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware.")
        return value.astimezone(UTC)

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed.astimezone(UTC)


def _validate_request_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid request id.")
    parsed = UUID(value)
    if parsed.version != 4:
        raise ValueError("Invalid request id version.")
    return str(parsed)


def _validate_process_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("Invalid process id.")
    return value


def _parse_request_marker(marker_text: str) -> RequestMarker:
    raw = json.loads(marker_text)
    if not isinstance(raw, dict):
        raise ValueError("Invalid request marker payload.")

    if set(raw.keys()) - _ALLOWED_MARKER_KEYS:
        raise ValueError("Invalid marker fields.")

    schema_version = raw.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or schema_version != REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION
        or "request_id" not in raw
        or "created_at_utc" not in raw
        or "lease_updated_at_utc" not in raw
        or "process_id" not in raw
        or "cleanup_state" not in raw
    ):
        raise ValueError("Invalid request marker payload.")

    request_id = _validate_request_id(raw.get("request_id"))
    created_at_utc = raw.get("created_at_utc")
    lease_updated_at_utc = raw.get("lease_updated_at_utc")
    process_id = _validate_process_id(raw.get("process_id"))
    cleanup_state = raw.get("cleanup_state", "active")

    if (
        isinstance(schema_version, bool)
        or not isinstance(created_at_utc, str)
        or not isinstance(lease_updated_at_utc, str)
        or cleanup_state not in _ALLOWED_CLEANUP_STATES
    ):
        raise ValueError("Invalid request marker payload.")

    created_at = _to_aware_utc(created_at_utc)
    lease_updated = _to_aware_utc(lease_updated_at_utc)
    if created_at > lease_updated:
        raise ValueError("Marker has invalid timestamp order.")
    if lease_updated > _now_utc() + timedelta(
        seconds=REQUEST_DIRECTORY_CLOCK_SKEW_SECONDS
    ):
        raise ValueError("Marker timestamp is in the future.")

    return RequestMarker(
        schema_version=int(schema_version),
        request_id=request_id,
        created_at_utc=created_at.isoformat(),
        lease_updated_at_utc=lease_updated.isoformat(),
        process_id=process_id,
        cleanup_state=cleanup_state,
    )


def _format_request_marker(
    request_id: str,
    created_at: datetime,
    lease_updated_at: datetime,
    *,
    process_id: int,
    cleanup_state: str = "active",
) -> RequestMarker:
    return RequestMarker(
        schema_version=REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION,
        request_id=request_id,
        created_at_utc=_to_aware_utc(created_at).isoformat(),
        lease_updated_at_utc=_to_aware_utc(lease_updated_at).isoformat(),
        process_id=process_id,
        cleanup_state=cleanup_state,
    )


def _marker_path(request_directory: RequestDirectory) -> Path:
    return request_directory.path / REQUEST_DIRECTORY_MARKER_NAME


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise OriginalCleanupError from exc

    if stat.S_ISLNK(metadata.st_mode) or path.is_symlink():
        return True

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _validate_existing_path_components(path: Path) -> None:
    current = _lexical_absolute(path)
    visited: set[Path] = set()

    while True:
        if current in visited:
            raise RuntimeError("Temporary storage root is invalid.")
        visited.add(current)

        if current.exists():
            if _is_link_or_reparse(current):
                raise RuntimeError("The extraction temp root is unsafe.")

            try:
                metadata = os.lstat(current)
            except OSError as exc:
                raise RuntimeError("The extraction temp root is unsafe.") from exc
            if not stat.S_ISDIR(metadata.st_mode):
                raise RuntimeError("Temporary storage root is invalid.")

        parent = current.parent
        if parent == current:
            break
        current = parent


def _request_identity(path: Path) -> tuple[int, int]:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise OriginalCleanupError from exc
    return metadata.st_dev, metadata.st_ino


def _is_request_directory_child(path: Path, root: Path) -> bool:
    if path == root:
        return False
    try:
        metadata = os.lstat(path)
    except OSError:
        return False
    if _is_link_or_reparse(path):
        return False
    return path.parent == root and stat.S_ISDIR(metadata.st_mode)


def _write_request_directory_marker(
    request_directory: RequestDirectory,
    marker: RequestMarker,
) -> None:
    marker_path = _marker_path(request_directory)
    root = get_temp_root()

    if not _is_request_directory_child(request_directory.path, root):
        raise UnsafeCleanupTargetError

    pre_metadata = _request_identity(request_directory.path)
    if pre_metadata != (request_directory.device, request_directory.inode):
        raise UnsafeCleanupTargetError

    if marker_path.name != REQUEST_DIRECTORY_MARKER_NAME:
        raise UnsafeCleanupTargetError
    if _is_link_or_reparse(request_directory.path):
        raise UnsafeCleanupTargetError

    payload = {
        "schema_version": marker.schema_version,
        "request_id": marker.request_id,
        "created_at_utc": marker.created_at_utc,
        "lease_updated_at_utc": marker.lease_updated_at_utc,
        "process_id": marker.process_id,
        "cleanup_state": marker.cleanup_state,
    }
    staging = marker_path.with_name(
        f".{marker_path.name}.{uuid4().hex}.pending"
    )
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )

    try:
        with os.fdopen(
            os.open(
                staging,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            ),
            "wb",
            closefd=True,
        ) as output:
            output.write(encoded)
            output.write(b"\n")
            output.flush()
            os.fsync(output.fileno())
        if _request_identity(request_directory.path) != pre_metadata:
            raise UnsafeCleanupTargetError
        staging.replace(marker_path)
    finally:
        if staging.exists():
            try:
                staging.unlink()
            except OSError:
                pass


def read_request_directory_marker(
    request_directory: RequestDirectory,
) -> RequestMarker | None:
    marker_path = _marker_path(request_directory)
    if marker_path.parent != request_directory.path:
        return None
    if marker_path.name != REQUEST_DIRECTORY_MARKER_NAME:
        return None

    try:
        metadata = os.lstat(marker_path)
    except OSError:
        return None

    if _is_link_or_reparse(marker_path):
        return None
    if not stat.S_ISREG(metadata.st_mode):
        return None
    if metadata.st_size <= 0 or metadata.st_size > MAX_REQUEST_DIRECTORY_MARKER_SIZE_BYTES:
        return None

    try:
        marker_text = marker_path.read_text(encoding="utf-8")
        return _parse_request_marker(marker_text)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _is_path_within_repo(root: Path) -> bool:
    repository_root = Path(__file__).resolve().parents[3]
    return root == repository_root or repository_root in root.parents


def get_temp_root() -> Path:
    configured_root = os.getenv(TEMP_ROOT_ENV)
    raw_root = Path(
        configured_root
        if configured_root
        else Path(tempfile.gettempdir()) / TEMP_ROOT_NAME
    )

    try:
        lexical_root = _lexical_absolute(raw_root)
        _validate_existing_path_components(lexical_root)
        if not lexical_root.exists():
            lexical_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            _validate_existing_path_components(lexical_root)
        elif not lexical_root.is_dir():
            raise RuntimeError("Temporary storage root is invalid.")

        root = lexical_root.resolve()
        if root == Path.home():
            raise RuntimeError("The extraction temp root is unsafe.")
        if _is_path_within_repo(root):
            raise RuntimeError("The extraction root must be outside the repository.")
    except OriginalCleanupError as exc:
        raise RuntimeError("The extraction temp root is unsafe.") from exc
    except OSError as exc:
        raise RuntimeError("Temporary storage root is invalid.") from exc

    return root


def _validate_request_directory_identity(
    request_directory: RequestDirectory,
    *,
    root: Path | None = None,
) -> None:
    temp_root = root or get_temp_root()

    if _is_link_or_reparse(temp_root):
        raise UnsafeCleanupTargetError

    target = request_directory.path
    if _lexical_absolute(target) == temp_root:
        raise UnsafeCleanupTargetError
    if target.parent != temp_root:
        raise UnsafeCleanupTargetError
    if _is_link_or_reparse(target):
        raise UnsafeCleanupTargetError

    try:
        current_identity = _request_identity(target)
    except OriginalCleanupError as exc:
        raise UnsafeCleanupTargetError from exc
    if current_identity != (request_directory.device, request_directory.inode):
        raise UnsafeCleanupTargetError

    try:
        metadata = os.lstat(target)
    except OSError as exc:
        raise UnsafeCleanupTargetError from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise UnsafeCleanupTargetError
    if _is_link_or_reparse(target):
        raise UnsafeCleanupTargetError


def create_request_directory() -> RequestDirectory:
    request_directory: RequestDirectory | None = None

    try:
        root = get_temp_root()
        request_path = Path(tempfile.mkdtemp(prefix=REQUEST_DIRECTORY_PREFIX, dir=root))
        request_path.chmod(0o700)
        device, inode = _request_identity(request_path)
        now = _now_utc()
        request_id = str(uuid4())
        process_id = os.getpid()
        request_directory = RequestDirectory(
            request_path,
            device,
            inode,
            request_id=request_id,
            created_at=now.isoformat(),
            lease_updated_at=now.isoformat(),
            schema_version=REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION,
            process_id=process_id,
        )
        marker = _format_request_marker(
            request_id,
            now,
            now,
            process_id=process_id,
        )
        _write_request_directory_marker(request_directory, marker)
        return request_directory
    except (OSError, RuntimeError, OriginalCleanupError) as exc:
        if request_directory is not None:
            try:
                cleanup_request_directory(request_directory)
            except OriginalCleanupError as cleanup_exc:
                raise cleanup_exc
        raise RuntimeError("Temporary storage is unavailable.") from exc


def create_server_file_path(
    request_directory: RequestDirectory,
    *,
    suffix: str = ".pdf",
) -> Path:
    if not suffix.startswith(".") or not suffix[1:].isalnum():
        raise ValueError("The server file suffix is invalid.")
    return request_directory.path / f"{uuid4()}{suffix.lower()}"


async def write_upload_to_temp(
    upload: UploadFile,
    target: Path,
    *,
    max_size_bytes: int,
) -> int:
    size_bytes = 0

    with target.open("xb") as output:
        while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
            size_bytes += len(chunk)
            if size_bytes > max_size_bytes:
                raise UploadSizeLimitExceededError
            output.write(chunk)

    return size_bytes


def refresh_request_directory_lease(
    request_directory: RequestDirectory,
    *,
    now: datetime | None = None,
) -> RequestDirectory:
    _validate_request_directory_identity(request_directory)
    marker = read_request_directory_marker(request_directory)
    if marker is None:
        raise OriginalCleanupError

    now_utc = _to_aware_utc(now if now is not None else _now_utc())
    if request_directory.request_id is not None and marker.request_id != request_directory.request_id:
        raise OriginalCleanupError
    if request_directory.process_id is not None and marker.process_id != request_directory.process_id:
        raise OriginalCleanupError

    created_at = _to_aware_utc(marker.created_at_utc)
    if now_utc < created_at:
        raise OriginalCleanupError

    if request_directory.device is not None and request_directory.inode is not None:
        current_metadata = _request_identity(request_directory.path)
        if (request_directory.device, request_directory.inode) != current_metadata:
            raise UnsafeCleanupTargetError

    new_marker = _format_request_marker(
        marker.request_id,
        created_at,
        now_utc,
        process_id=request_directory.process_id or marker.process_id,
    )
    _write_request_directory_marker(request_directory, new_marker)

    return RequestDirectory(
        path=request_directory.path,
        device=request_directory.device,
        inode=request_directory.inode,
        request_id=marker.request_id,
        created_at=created_at.isoformat(),
        lease_updated_at=now_utc.isoformat(),
        schema_version=REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION,
        process_id=request_directory.process_id or marker.process_id,
    )


def cleanup_request_directory(
    request_directory: RequestDirectory,
) -> None:
    _validate_request_directory_identity(request_directory)

    marker = read_request_directory_marker(request_directory)
    if marker is not None and request_directory.request_id is not None:
        if marker.request_id != request_directory.request_id:
            raise UnsafeCleanupTargetError

    try:
        shutil.rmtree(request_directory.path)
    except OSError as exc:
        raise CleanupOperationError from exc

    if request_directory.path.exists():
        raise CleanupOperationError
