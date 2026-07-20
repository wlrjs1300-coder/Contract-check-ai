from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


TEMP_ROOT_ENV = "EXTRACTION_TEMP_ROOT"
TEMP_ROOT_NAME = "contract-check-ai-extractions"
UPLOAD_CHUNK_SIZE = 1024 * 1024


class UploadSizeLimitExceededError(Exception):
    pass


class OriginalCleanupError(Exception):
    pass


@dataclass(frozen=True)
class RequestDirectory:
    path: Path
    device: int
    inode: int


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


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


def _request_identity(path: Path) -> tuple[int, int]:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise OriginalCleanupError from exc

    return metadata.st_dev, metadata.st_ino


def get_temp_root() -> Path:
    configured_root = os.getenv(TEMP_ROOT_ENV)
    root = Path(
        configured_root
        if configured_root
        else Path(tempfile.gettempdir()) / TEMP_ROOT_NAME
    ).resolve()
    repository_root = Path(__file__).resolve().parents[3]

    if root == repository_root or repository_root in root.parents:
        raise RuntimeError("The extraction temp root must be outside the repository.")

    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def create_request_directory() -> RequestDirectory:
    request_directory: RequestDirectory | None = None

    try:
        root = get_temp_root()
        request_path = Path(
            tempfile.mkdtemp(prefix="request-", dir=root)
        )
        device, inode = _request_identity(request_path)
        request_directory = RequestDirectory(request_path, device, inode)
        request_path.chmod(0o700)
        return request_directory
    except (OSError, RuntimeError, OriginalCleanupError) as exc:
        if request_directory is not None:
            try:
                cleanup_request_directory(request_directory)
            except OriginalCleanupError as cleanup_exc:
                raise OriginalCleanupError from cleanup_exc

        raise RuntimeError("Temporary storage is unavailable.") from exc


def create_server_file_path(request_directory: RequestDirectory) -> Path:
    return request_directory.path / f"{uuid4()}.pdf"


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


def cleanup_request_directory(
    request_directory: RequestDirectory,
) -> None:
    try:
        root = get_temp_root()
    except (OSError, RuntimeError) as exc:
        raise OriginalCleanupError from exc
    target = _lexical_absolute(request_directory.path)

    if target.parent != root or target == root:
        raise OriginalCleanupError

    if not target.exists() and not target.is_symlink():
        return

    if _is_link_or_reparse(target):
        raise OriginalCleanupError

    if _request_identity(target) != (
        request_directory.device,
        request_directory.inode,
    ):
        raise OriginalCleanupError

    try:
        shutil.rmtree(target)
    except OSError as exc:
        raise OriginalCleanupError from exc

    if target.exists():
        raise OriginalCleanupError
