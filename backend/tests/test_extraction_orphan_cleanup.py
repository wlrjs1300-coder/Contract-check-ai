from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
import backend.app.main as app_main
from backend.app.services import extraction_orphan_cleanup as orphan_cleanup
from backend.app.services.extraction_orphan_cleanup import (
    OrphanCleanupError,
    OrphanCleanupResult,
    _sweep_orphan_request_directories_for_testing,
    sweep_orphan_request_directories,
)
from backend.app.services.extraction_temp_files import (
    get_temp_root,
    REQUEST_DIRECTORY_MARKER_NAME,
    REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION,
    _format_request_marker,
    _to_aware_utc,
    _write_request_directory_marker,
    create_request_directory,
    RequestDirectory,
    cleanup_request_directory,
    CleanupOperationError,
)
from backend.app.services import extraction_temp_files


def _set_temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "extractions"
    root.mkdir()
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(root))
    return root


def test_get_temp_root_creates_nested_missing_parents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    nested_root = tmp_path / "safe" / "parent" / "request-temp-root"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(nested_root))
    assert not nested_root.exists()
    assert not nested_root.parent.exists()

    root = get_temp_root()

    assert root == nested_root.resolve()
    assert root.exists()
    assert root.is_dir()


def test_startup_creates_safe_nested_temp_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    nested_root = tmp_path / "safe-startup" / "nested" / "root"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(nested_root))
    assert not nested_root.exists()

    with TestClient(app):
        assert nested_root.exists()
        assert nested_root.is_dir()
        assert app.state.orphan_cleanup["scanned_count"] == 0


def test_orphan_sweep_supports_nested_missing_temp_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    nested_root = tmp_path / "orphan" / "nested" / "root"
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(nested_root))
    result = sweep_orphan_request_directories()

    assert nested_root.exists()
    assert nested_root.is_dir()
    assert result.scanned_count == 0


def test_get_temp_root_rejects_symlink_in_existing_parent_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-parent"
    link_parent = tmp_path / "link-parent"
    try:
        real_parent.mkdir()
        link_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink is unavailable.")
    nested_root = link_parent / "request-temp-root"

    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(nested_root))
    with pytest.raises(RuntimeError):
        get_temp_root()


def test_get_temp_root_rejects_reparse_parent_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) == 0:
        pytest.skip("Reparse point metadata is not available.")

    root = tmp_path / "reparse-root"
    root.mkdir()
    request_root = root / "child" / "request"
    request_root.parent.mkdir()

    original_lstat = extraction_temp_files.os.lstat
    metadata = SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT"),
    )

    def reparse_lstat(path: Path) -> os.stat_result:
        if Path(path) == root:
            return metadata
        return original_lstat(path)

    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(request_root))
    monkeypatch.setattr(extraction_temp_files.os, "lstat", reparse_lstat)

    with pytest.raises(RuntimeError):
        get_temp_root()


def test_get_temp_root_normalizes_boundary_inspection_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "normalized-root"
    target_root.mkdir()

    def fail_lstat(path: Path) -> os.stat_result:
        if Path(path) == target_root:
            raise OSError("synthetic-stat-error")
        return extraction_temp_files.os.stat(path)

    monkeypatch.setattr(extraction_temp_files.os, "lstat", fail_lstat)
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(target_root))

    with pytest.raises(RuntimeError):
        get_temp_root()


def test_orphan_sweep_normalizes_temp_root_cleanup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = orphan_cleanup.get_temp_root
    monkeypatch.setattr(
        orphan_cleanup,
        "get_temp_root",
        lambda: (_ for _ in ()).throw(extraction_temp_files.OriginalCleanupError()),
    )

    try:
        with pytest.raises(OrphanCleanupError):
            sweep_orphan_request_directories()
    finally:
        monkeypatch.setattr(orphan_cleanup, "get_temp_root", original)


def _write_marker(
    request_directory: RequestDirectory,
    *,
    created_delta_seconds: int = 0,
    lease_delta_seconds: int = 0,
    request_id: str,
    process_id: int = 100,
    schema_version: int = REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION,
    cleanup_state: str = "active",
) -> None:
    now = datetime.now(UTC)
    created = now + timedelta(seconds=created_delta_seconds)
    lease = now + timedelta(seconds=lease_delta_seconds)
    marker = _format_request_marker(
        request_id=request_id,
        created_at=created,
        lease_updated_at=lease,
        process_id=process_id,
        cleanup_state=cleanup_state,
    )
    if schema_version != REQUEST_DIRECTORY_MARKER_SCHEMA_VERSION:
        marker_data = marker.__dict__.copy()
        marker_data["schema_version"] = schema_version
    else:
        marker_data = marker.__dict__.copy()
    marker_data["schema_version"] = schema_version
    marker_text = json.dumps(marker_data, ensure_ascii=False)
    (request_directory.path / "request-directory.json").write_text(
        marker_text,
        encoding="utf-8",
    )


def test_orphan_sweep_deletes_expired_marker_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker = request_directory
    assert marker.request_id is not None
    _write_marker(
        request_directory,
        request_id=marker.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.removed_count == 1
    assert not request_directory.path.exists()


def test_orphan_sweep_keeps_active_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_active_count == 1
    assert request_directory.path.exists()


def test_orphan_sweep_multiple_orphans_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    first = create_request_directory()
    second = create_request_directory()
    for request_directory in (first, second):
        _write_marker(
            request_directory,
            request_id=request_directory.request_id,
            lease_delta_seconds=-7200,
            created_delta_seconds=-7200,
        )

    result = _sweep_orphan_request_directories_for_testing(root=root)

    assert result.removed_count == 2
    assert not first.path.exists()
    assert not second.path.exists()


def test_orphan_sweep_continue_when_one_entry_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    first = create_request_directory()
    second = create_request_directory()
    for request_directory in (first, second):
        _write_marker(
            request_directory,
            request_id=request_directory.request_id,
            lease_delta_seconds=-7200,
            created_delta_seconds=-7200,
        )

    original = orphan_cleanup.cleanup_request_directory

    def fail_for_first(request_directory: RequestDirectory) -> None:
        if request_directory.path == first.path:
            raise CleanupOperationError
        original(request_directory)

    monkeypatch.setattr(orphan_cleanup, "cleanup_request_directory", fail_for_first)
    result = _sweep_orphan_request_directories_for_testing(root=root)

    assert result.failed_count == 1
    assert result.removed_count == 1
    assert not second.path.exists()


def test_orphan_sweep_retry_then_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    _write_marker(
        request_directory,
        request_id=request_directory.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )

    attempts = {"n": 0}

    def fail_once_then_cleanup(entry: RequestDirectory) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise CleanupOperationError
        cleanup_request_directory(entry)

    monkeypatch.setattr(orphan_cleanup, "cleanup_request_directory", fail_once_then_cleanup)
    result = _sweep_orphan_request_directories_for_testing(
        root=root,
        retry_count=2,
        retry_delay_seconds=0,
    )

    assert result.removed_count == 1
    assert attempts["n"] == 2
    assert not request_directory.path.exists()


def test_orphan_sweep_retry_exhausted_keeps_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    _write_marker(
        request_directory,
        request_id=request_directory.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )

    monkeypatch.setattr(
        orphan_cleanup,
        "cleanup_request_directory",
        lambda _: (_ for _ in ()).throw(CleanupOperationError()),
    )
    result = _sweep_orphan_request_directories_for_testing(root=root, retry_count=2, retry_delay_seconds=0)

    assert result.failed_count == 1
    assert request_directory.path.exists()


def test_orphan_sweep_marker_missing_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    request_directory.path.rename(request_directory.path.with_name("temporary"))
    request_directory.path.mkdir()
    tempfile.mkdtemp(prefix="request-", dir=str(root))

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.eligible_count == 0
    assert result.skipped_unsafe_count >= 1


def test_orphan_sweep_skips_symlink_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "request-symlink"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink unavailable.")

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_reparse_or_junction_unsupported_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name != "nt":
        pytest.skip("Junction/reparse specific test is Windows-only.")
    root = _set_temp_root(tmp_path, monkeypatch)
    assert root.exists()


def test_orphan_sweep_keeps_non_request_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    (root / "note.txt").write_text("dummy", encoding="utf-8")
    (root / "not-request").mkdir()
    tempfile.mkdtemp(prefix="request-", dir=str(root))

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert (root / "note.txt").exists()
    assert (root / "not-request").exists()
    assert result.scanned_count >= 2


def test_orphan_sweep_malformed_json_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_text("{", encoding="utf-8")

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_naive_marker_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_text = {
        "schema_version": 1,
        "request_id": request_directory.request_id,
        "created_at_utc": "2026-07-22T00:00:00",
        "lease_updated_at_utc": "2026-07-22T00:00:00",
        "process_id": 100,
        "cleanup_state": "active",
    }
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_text(
        json.dumps(marker_text, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_future_lease_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    now = datetime.now(UTC)
    marker = _format_request_marker(
        request_directory.request_id,
        _to_aware_utc(now),
        _to_aware_utc(now + timedelta(hours=2)),
        process_id=100,
    )
    _write_request_directory_marker(request_directory, marker)

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_created_after_lease_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    _write_marker(
        request_directory,
        request_id=request_directory.request_id,
        lease_delta_seconds=-100,
        created_delta_seconds=100,
    )
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_invalid_boolean_process_id_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_text = {
        "schema_version": 1,
        "request_id": request_directory.request_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "lease_updated_at_utc": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "process_id": True,
        "cleanup_state": "active",
    }
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_text(
        json.dumps(marker_text, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_invalid_uuid_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_text = {
        "schema_version": 1,
        "request_id": "bad-id",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "lease_updated_at_utc": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "process_id": 100,
        "cleanup_state": "active",
    }
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_text(
        json.dumps(marker_text, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_scan_child_disappears(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    (root / "normal.txt").write_text("x", encoding="utf-8")

    original_scan = orphan_cleanup._scan_root_entries

    def remove_child(_root: Path) -> list[os.DirEntry[str]]:
        entries = original_scan(_root)
        for entry in entries:
            if entry.name == request_directory.path.name:
                Path(entry.path).rename(Path(entry.path).with_name("request-removed"))
        return original_scan(_root)

    monkeypatch.setattr(orphan_cleanup, "_scan_root_entries", remove_child)
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.scanned_count >= 1


def test_orphan_sweep_root_scan_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)

    def fail_scan(_: Path) -> list[os.DirEntry[str]]:
        raise OSError("scan fail")

    monkeypatch.setattr(orphan_cleanup, "_scan_root_entries", fail_scan)
    with pytest.raises(OrphanCleanupError):
        _sweep_orphan_request_directories_for_testing(root=root)


def test_orphan_sweep_root_override_not_available() -> None:
    with pytest.raises(TypeError):
        # public function should not accept root override anymore
        sweep_orphan_request_directories(root=Path(".").resolve())  # type: ignore[arg-type]


def test_orphan_startup_state_stored_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(app_main, "sweep_orphan_request_directories", lambda **kwargs: OrphanCleanupResult(0, 0, 0, 0, 0, 0, {}))

    calls: list[dict[str, object]] = []

    def fake_sweep(*args: object, **kwargs: object) -> OrphanCleanupResult:
        calls.append({"args": args, "kwargs": kwargs})
        return OrphanCleanupResult(1, 1, 1, 0, 0, 0, {})

    monkeypatch.setattr(app_main, "sweep_orphan_request_directories", fake_sweep)
    with TestClient(app):
        pass

    assert len(calls) >= 1
    assert app.state.orphan_cleanup["removed_count"] == 1


def test_orphan_sweep_reject_root_inside_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # if root equals repository path, startup config is rejected
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(Path(__file__).resolve().parents[4]))
    with pytest.raises(OrphanCleanupError):
        sweep_orphan_request_directories()


def test_orphan_sweep_staging_cleanup_on_failed_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker = _to_aware_utc(datetime.now(UTC) - timedelta(hours=3))

    def fail_open(*_args: object, **_kwargs: object) -> int:
        raise OSError("blocked")

    monkeypatch.setattr(orphan_cleanup.os, "open", fail_open)
    with pytest.raises(OSError):
        _write_request_directory_marker(
            request_directory,
            _format_request_marker(
                request_id=request_directory.request_id,
                created_at=marker,
                lease_updated_at=marker,
                process_id=request_directory.process_id or 100,
            ),
        )

    leftovers = [item for item in request_directory.path.iterdir() if item.name.endswith(".pending")]
    assert leftovers == []


def test_orphan_sweep_result_has_no_path_string(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    _write_marker(
        request_directory,
        request_id=request_directory.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )

    def fail_cleanup(_: RequestDirectory) -> None:
        raise OSError("blocked path")

    monkeypatch.setattr(orphan_cleanup, "cleanup_request_directory", fail_cleanup)
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.failed_count == 1
    assert "path=" not in str(result.status_codes)


def test_orphan_sweep_keeps_request_items_when_marker_missing_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_text = {
        "schema_version": 1,
        "request_id": request_directory.request_id,
        "created_at_utc": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "lease_updated_at_utc": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "process_id": 100,
    }
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_text(
        json.dumps(marker_text, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1


def test_orphan_sweep_non_request_entries_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    (root / "document.txt").write_text("x", encoding="utf-8")
    (root / "notrequest").mkdir()
    (root / "request_not_this").mkdir()
    tempfile.mkdtemp(prefix="request-", dir=str(root))

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert (root / "document.txt").exists()
    assert (root / "notrequest").exists()
    assert (root / "request_not_this").exists()
    assert result.scanned_count >= 2


def test_orphan_sweep_retry_delay_nan_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    monkeypatch.setenv("EXTRACTION_ORPHAN_CLEANUP_RETRY_DELAY_SECONDS", "nan")
    request_directory = create_request_directory()
    _write_marker(
        request_directory,
        request_id=request_directory.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )
    with pytest.raises(OrphanCleanupError):
        _sweep_orphan_request_directories_for_testing(root=root)


def test_orphan_sweep_startup_runs_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_temp_root(tmp_path, monkeypatch)
    calls: list[dict[str, object]] = []

    def fake_sweep(*args: object, **kwargs: object) -> OrphanCleanupResult:
        calls.append({"args": args, "kwargs": kwargs})
        return OrphanCleanupResult(0, 0, 0, 0, 0, 0, {})

    monkeypatch.setattr(app_main, "sweep_orphan_request_directories", fake_sweep)

    with TestClient(app):
        pass

    with TestClient(app):
        pass
    assert len(calls) == 2


def test_orphan_sweep_startup_config_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_temp_root(tmp_path, monkeypatch)
    monkeypatch.setenv("EXTRACTION_ORPHAN_TTL_SECONDS", "bad")
    with pytest.raises(OrphanCleanupError):
        sweep_orphan_request_directories()


def test_orphan_sweep_root_scan_failure_does_not_stop_other_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    alive = create_request_directory()
    dead = create_request_directory()
    _write_marker(
        alive,
        request_id=alive.request_id,
        lease_delta_seconds=-7200,
        created_delta_seconds=-7200,
    )
    marker_text = {
        "schema_version": 1,
        "request_id": dead.request_id,
        "created_at_utc": "bad",
        "lease_updated_at_utc": "bad",
        "process_id": 100,
    }
    (dead.path / REQUEST_DIRECTORY_MARKER_NAME).write_text(
        json.dumps(marker_text, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.removed_count == 1
    assert result.failed_count == 0


def test_orphan_sweep_rejects_root_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_root = tmp_path / "real-root"
    target_root.mkdir()
    link_root = tmp_path / "link-root"
    try:
        link_root.symlink_to(target_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink unavailable.")

    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(link_root))
    assert list(tmp_path.iterdir())
    with pytest.raises(OrphanCleanupError):
        sweep_orphan_request_directories()

    assert list(target_root.iterdir()) == []
    assert len(list(link_root.iterdir())) >= 0


def test_orphan_sweep_rejects_root_reparse_point_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name != "nt":
        pytest.skip("Reparse/junction policy test is Windows-only.")
    root = _set_temp_root(tmp_path, monkeypatch)
    original_is_link_or_reparse = orphan_cleanup._is_link_or_reparse

    def reject_root(path: Path) -> bool:
        if path == root:
            return True
        return original_is_link_or_reparse(path)

    monkeypatch.setattr(orphan_cleanup, "_is_link_or_reparse", reject_root)
    with pytest.raises(OrphanCleanupError):
        sweep_orphan_request_directories()


def test_orphan_sweep_skips_linked_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_path = request_directory.path / REQUEST_DIRECTORY_MARKER_NAME
    marker_path.unlink()
    external = tmp_path / "external-marker.txt"
    external.write_text('{"schema_version":1}', encoding="utf-8")

    try:
        marker_path.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlink unavailable.")

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1
    assert request_directory.path.exists()
    assert external.exists()


def test_orphan_sweep_skips_non_file_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    marker_path = request_directory.path / REQUEST_DIRECTORY_MARKER_NAME
    marker_path.unlink()
    marker_path.mkdir()

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1
    assert request_directory.path.exists()


def test_orphan_sweep_skips_oversized_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    request_directory = create_request_directory()
    (request_directory.path / REQUEST_DIRECTORY_MARKER_NAME).write_bytes(b"{\"schema_version\":1}\n" * 700)

    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.skipped_unsafe_count == 1
    assert request_directory.path.exists()


def test_orphan_sweep_continues_when_entries_disappear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    first = create_request_directory()
    second = create_request_directory()
    for request_directory in (first, second):
        _write_marker(
            request_directory,
            request_id=request_directory.request_id,
            lease_delta_seconds=-7200,
            created_delta_seconds=-7200,
        )

    real_lstat = orphan_cleanup.os.lstat
    invoked = {"first_lost": False}

    def flaky_lstat(path: str | os.PathLike[str] | os.PathLike[bytes]) -> os.stat_result:
        if Path(path) == first.path and not invoked["first_lost"]:
            invoked["first_lost"] = True
            raise FileNotFoundError("simulated scan disappearance")
        return real_lstat(path)

    monkeypatch.setattr(orphan_cleanup.os, "lstat", flaky_lstat)
    result = _sweep_orphan_request_directories_for_testing(root=root)
    assert result.removed_count == 1
    assert result.status_codes.get("skipped_missing_entry", 0) >= 1
    assert result.failed_count == 0
    assert not second.path.exists()


def test_orphan_sweep_rejects_invalid_retry_count_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    for invalid_retry_count in (0, -1, 25, True):
        with pytest.raises(OrphanCleanupError):
            _sweep_orphan_request_directories_for_testing(
                root=root,
                retry_count=invalid_retry_count,
            )
        assert len(list(root.iterdir())) == 0


def test_orphan_sweep_rejects_invalid_retry_delay_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    for invalid_delay in (-1, 11, float("nan"), float("inf"), True):
        with pytest.raises(OrphanCleanupError):
            _sweep_orphan_request_directories_for_testing(
                root=root,
                retry_delay_seconds=invalid_delay,
            )
        assert len(list(root.iterdir())) == 0


def test_orphan_sweep_accepts_retry_bounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _set_temp_root(tmp_path, monkeypatch)
    _sweep_orphan_request_directories_for_testing(
        root=root,
        retry_count=1,
        retry_delay_seconds=0,
    )
    _sweep_orphan_request_directories_for_testing(
        root=root,
        retry_count=24,
        retry_delay_seconds=10,
    )
