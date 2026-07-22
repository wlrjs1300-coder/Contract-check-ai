from __future__ import annotations

import math
import os
import stat
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, NamedTuple

from backend.app.services.extraction_temp_files import (
    REQUEST_DIRECTORY_PREFIX,
    CleanupOperationError,
    RequestDirectory,
    OriginalCleanupError,
    _is_link_or_reparse,
    _to_aware_utc,
    cleanup_request_directory,
    get_temp_root,
    read_request_directory_marker,
    UnsafeCleanupTargetError,
)


ORPHAN_TTL_SECONDS_ENV: Final = "EXTRACTION_ORPHAN_TTL_SECONDS"
ORPHAN_RETRY_COUNT_ENV: Final = "EXTRACTION_ORPHAN_CLEANUP_RETRY_COUNT"
ORPHAN_RETRY_DELAY_SECONDS_ENV: Final = (
    "EXTRACTION_ORPHAN_CLEANUP_RETRY_DELAY_SECONDS"
)

DEFAULT_ORPHAN_TTL_SECONDS: Final = 3600
DEFAULT_ORPHAN_RETRY_COUNT: Final = 3
DEFAULT_ORPHAN_RETRY_DELAY_SECONDS: Final = 1.0
ORPHAN_CLOCK_SKEW_SECONDS: Final = 120

_CONFIG_LIMITS = {
    ORPHAN_TTL_SECONDS_ENV: (60, 86400),
    ORPHAN_RETRY_COUNT_ENV: (1, 24),
    ORPHAN_RETRY_DELAY_SECONDS_ENV: (0.0, 10.0),
}


@dataclass(frozen=True)
class OrphanCleanupResult:
    scanned_count: int
    eligible_count: int
    removed_count: int
    skipped_active_count: int
    skipped_unsafe_count: int
    failed_count: int
    status_codes: dict[str, int] = field(default_factory=dict)


class OrphanCleanupError(Exception):
    pass


class OrphanAttempt(NamedTuple):
    category: str
    removed: bool = False
    deleted: bool = False


def _parse_positive_int(value: str | None, *, minimum: int, maximum: int) -> int:
    if value is None or str(value).strip() == "":
        raise ValueError

    parsed = int(value)
    if isinstance(parsed, bool) or parsed < minimum or parsed > maximum:
        raise ValueError
    return parsed


def _parse_positive_float(value: str | None, *, minimum: float, maximum: float) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError

    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError
    if parsed < minimum or parsed > maximum:
        raise ValueError
    return parsed


def _validate_retry_count(value: object) -> int:
    try:
        minimum, maximum = _CONFIG_LIMITS[ORPHAN_RETRY_COUNT_ENV]
    except KeyError as exc:
        raise OrphanCleanupError("Invalid retry configuration.") from exc
    if not isinstance(value, int) or isinstance(value, bool):
        raise OrphanCleanupError("Invalid retry configuration.")
    if value < minimum or value > maximum:
        raise OrphanCleanupError("Invalid retry configuration.")
    return value


def _validate_retry_delay(value: object) -> float:
    try:
        minimum, maximum = _CONFIG_LIMITS[ORPHAN_RETRY_DELAY_SECONDS_ENV]
    except KeyError as exc:
        raise OrphanCleanupError("Invalid retry configuration.") from exc
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise OrphanCleanupError("Invalid retry configuration.")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        raise OrphanCleanupError("Invalid retry configuration.")
    return parsed


def _read_orphan_config() -> tuple[int, int, float]:
    try:
        ttl = _parse_positive_int(
            os.getenv(ORPHAN_TTL_SECONDS_ENV, str(DEFAULT_ORPHAN_TTL_SECONDS)),
            minimum=_CONFIG_LIMITS[ORPHAN_TTL_SECONDS_ENV][0],
            maximum=_CONFIG_LIMITS[ORPHAN_TTL_SECONDS_ENV][1],
        )
        retry_count = _parse_positive_int(
            os.getenv(ORPHAN_RETRY_COUNT_ENV, str(DEFAULT_ORPHAN_RETRY_COUNT)),
            minimum=_CONFIG_LIMITS[ORPHAN_RETRY_COUNT_ENV][0],
            maximum=_CONFIG_LIMITS[ORPHAN_RETRY_COUNT_ENV][1],
        )
        retry_delay = _parse_positive_float(
            os.getenv(
                ORPHAN_RETRY_DELAY_SECONDS_ENV,
                str(DEFAULT_ORPHAN_RETRY_DELAY_SECONDS),
            ),
            minimum=_CONFIG_LIMITS[ORPHAN_RETRY_DELAY_SECONDS_ENV][0],
            maximum=_CONFIG_LIMITS[ORPHAN_RETRY_DELAY_SECONDS_ENV][1],
        )
    except (TypeError, ValueError) as exc:
        raise OrphanCleanupError("Invalid orphan cleanup configuration.") from exc

    return ttl, retry_count, retry_delay


def _to_aware_utc_strict(value: datetime) -> datetime:
    return _to_aware_utc(value)


def _marker_is_expired(marker: object, now: datetime, ttl_seconds: int) -> bool:
    marker_lease = getattr(marker, "lease_updated_at_utc", None)
    marker_created = getattr(marker, "created_at_utc", None)

    lease_time = _to_aware_utc(marker_lease)
    created_time = _to_aware_utc(marker_created)
    if created_time > lease_time:
        return False

    if lease_time > now + timedelta(seconds=ORPHAN_CLOCK_SKEW_SECONDS):
        return False

    return (now - lease_time) >= timedelta(seconds=ttl_seconds)


def _touch_status(status_codes: dict[str, int], code: str) -> None:
    status_codes[code] = status_codes.get(code, 0) + 1


def _is_request_directory_candidate(entry_name: str) -> bool:
    return (
        entry_name.startswith(REQUEST_DIRECTORY_PREFIX)
        and len(entry_name) > len(REQUEST_DIRECTORY_PREFIX)
    )


def _attempt_remove(
    request_directory: RequestDirectory,
    *,
    retry_count: int,
    delay: float,
) -> OrphanAttempt:
    for attempt in range(max(1, retry_count)):
        try:
            cleanup_request_directory(request_directory)
            return OrphanAttempt(category="removed", removed=True)
        except UnsafeCleanupTargetError:
            return OrphanAttempt(category="skipped_unsafe")
        except CleanupOperationError:
            if attempt < max(1, retry_count) - 1 and delay > 0:
                time.sleep(delay)
            continue
        except Exception:
            return OrphanAttempt(category="failed")
    return OrphanAttempt(category="failed")


def _validate_root_boundary(root: Path) -> None:
    try:
        if not root.exists() or not root.is_dir():
            raise OrphanCleanupError
        if _is_link_or_reparse(root):
            raise OrphanCleanupError
        temp_root = get_temp_root()
        if root.resolve() != temp_root:
            raise OrphanCleanupError
    except OSError as exc:
        raise OrphanCleanupError from exc


def _scan_root_entries(root: Path) -> list[os.DirEntry[str]]:
    try:
        return list(os.scandir(root))
    except OSError as exc:
        raise OrphanCleanupError from exc


def _sweep(
    *,
    root: Path,
    now: datetime | None = None,
    retry_count: int | None = None,
    retry_delay_seconds: float | None = None,
) -> OrphanCleanupResult:
    status_codes: dict[str, int] = defaultdict(int)
    ttl_seconds, cfg_retry_count, cfg_retry_delay = _read_orphan_config()
    now = _to_aware_utc_strict(now or datetime.now(UTC))
    try:
        retry_count = cfg_retry_count if retry_count is None else _validate_retry_count(retry_count)
        retry_delay_seconds = (
            cfg_retry_delay
            if retry_delay_seconds is None
            else _validate_retry_delay(retry_delay_seconds)
        )
    except OrphanCleanupError as exc:
        raise OrphanCleanupError("Invalid retry configuration.") from exc

    _validate_root_boundary(root)

    scanned_count = 0
    eligible_count = 0
    removed_count = 0
    skipped_active_count = 0
    skipped_unsafe_count = 0
    failed_count = 0

    try:
        entries = _scan_root_entries(root)
    except OSError as exc:
        raise OrphanCleanupError from exc

    for entry in entries:
        scanned_count += 1
        path = Path(entry.path)
        try:
            if _is_link_or_reparse(path):
                skipped_unsafe_count += 1
                _touch_status(status_codes, "skipped_symlink")
                continue

            if not _is_request_directory_candidate(entry.name):
                _touch_status(status_codes, "skipped_non_request_entry")
                continue

            try:
                entry_metadata = os.lstat(path)
            except OSError:
                skipped_unsafe_count += 1
                _touch_status(status_codes, "skipped_missing_entry")
                continue

            if not stat.S_ISDIR(entry_metadata.st_mode):
                skipped_unsafe_count += 1
                _touch_status(status_codes, "skipped_non_dir")
                continue

            request_directory = RequestDirectory(
                path=path,
                device=entry_metadata.st_dev,
                inode=entry_metadata.st_ino,
            )
            marker = read_request_directory_marker(request_directory)
            if marker is None:
                skipped_unsafe_count += 1
                _touch_status(status_codes, "skipped_invalid_marker")
                continue

            if (
                marker.request_id is None
                or marker.process_id is None
                or marker.created_at_utc is None
                or marker.lease_updated_at_utc is None
            ):
                skipped_unsafe_count += 1
                _touch_status(status_codes, "skipped_invalid_marker")
                continue

            if not _marker_is_expired(marker, now, ttl_seconds):
                skipped_active_count += 1
                _touch_status(status_codes, "skipped_active")
                continue

            request_directory = RequestDirectory(
                path=path,
                device=entry_metadata.st_dev,
                inode=entry_metadata.st_ino,
                request_id=marker.request_id,
                process_id=marker.process_id,
                created_at=marker.created_at_utc,
                lease_updated_at=marker.lease_updated_at_utc,
                schema_version=marker.schema_version,
            )
            eligible_count += 1
            _touch_status(status_codes, "eligible")

            result = _attempt_remove(
                request_directory,
                retry_count=retry_count,
                delay=retry_delay_seconds,
            )
            _touch_status(status_codes, result.category)
            if result.removed:
                removed_count += 1
            elif result.category == "failed":
                failed_count += 1
            else:
                skipped_unsafe_count += 1
        except (OSError, ValueError, RuntimeError, TypeError, OriginalCleanupError):
            skipped_unsafe_count += 1
            _touch_status(status_codes, "skipped_missing_entry")
            continue
        except Exception:
            failed_count += 1
            _touch_status(status_codes, "failed")
            continue

    return OrphanCleanupResult(
        scanned_count=scanned_count,
        eligible_count=eligible_count,
        removed_count=removed_count,
        skipped_active_count=skipped_active_count,
        skipped_unsafe_count=skipped_unsafe_count,
        failed_count=failed_count,
        status_codes=dict(status_codes),
    )


def sweep_orphan_request_directories(
    *,
    now: datetime | None = None,
    retry_count: int | None = None,
    retry_delay_seconds: float | None = None,
) -> OrphanCleanupResult:
    try:
        temp_root = get_temp_root()
    except (RuntimeError, OSError, OriginalCleanupError) as exc:
        raise OrphanCleanupError from exc
    return _sweep(
        root=temp_root,
        now=now,
        retry_count=retry_count,
        retry_delay_seconds=retry_delay_seconds,
    )


def _sweep_orphan_request_directories_for_testing(
    *,
    root: Path,
    now: datetime | None = None,
    retry_count: int | None = None,
    retry_delay_seconds: float | None = None,
) -> OrphanCleanupResult:
    return _sweep(
        root=root,
        now=now,
        retry_count=retry_count,
        retry_delay_seconds=retry_delay_seconds,
    )
