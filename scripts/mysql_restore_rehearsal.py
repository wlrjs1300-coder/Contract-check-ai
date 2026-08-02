from __future__ import annotations

import json
import sys

from mysql_backup_rehearsal import MySQLRehearsal, RehearsalError, _safe_result


def run_restore_rehearsal() -> tuple[dict[str, str], ...]:
    rehearsal = MySQLRehearsal()
    results: list[dict[str, str]] = []
    try:
        for stage, action in (
            ("isolated_environment", rehearsal.setup),
            ("source_database", lambda: rehearsal.start_database(restore=False)),
            ("alembic_upgrade", rehearsal.migrate_source),
            ("synthetic_seed", rehearsal.seed_source),
            ("backup_artifact", rehearsal.create_backup),
            ("isolated_restore_database", lambda: rehearsal.start_database(restore=True)),
            ("restore_artifact", rehearsal.restore_backup),
            ("restore_verification", rehearsal.verify_restore),
        ):
            try:
                action()
            except RehearsalError as exc:
                results.append(_safe_result(stage, "FAIL", exc.code))
                break
            results.append(_safe_result(stage, "PASS", "NONE"))
    finally:
        try:
            rehearsal.cleanup()
        except RehearsalError as exc:
            results.append(_safe_result("cleanup", "FAIL", exc.code))
        else:
            results.append(_safe_result("cleanup", "PASS", "NONE"))
    return tuple(results)


def main() -> int:
    results = run_restore_rehearsal()
    print(json.dumps({"results": results}, separators=(",", ":"), sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
