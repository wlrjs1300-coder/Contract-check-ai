from __future__ import annotations

from pathlib import Path
import subprocess
import sys


_FORBIDDEN_SUFFIXES = (
    ".sql",
    ".dump",
    ".bak",
    ".backup",
    ".sql.gz",
    ".dump.gz",
)


def _candidate_files(repository: Path) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for command in (
        ["git", "ls-files", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ):
        completed = subprocess.run(
            command,
            cwd=repository,
            check=True,
            capture_output=True,
        )
        candidates.update(
            Path(item.decode("utf-8"))
            for item in completed.stdout.split(b"\0")
            if item
        )
    return tuple(sorted(candidates))


def validate_repository(repository: Path) -> frozenset[str]:
    findings: set[str] = set()
    for path in _candidate_files(repository):
        lowered = path.name.lower()
        if any(lowered.endswith(suffix) for suffix in _FORBIDDEN_SUFFIXES):
            findings.add("TRACKED_BACKUP_ARTIFACT")
    return frozenset(findings)


def main() -> int:
    try:
        findings = validate_repository(Path(__file__).resolve().parents[1])
    except Exception:
        print("FAIL BACKUP_ARTIFACT_SCAN_ERROR")
        return 2
    if findings:
        for code in sorted(findings):
            print(f"FAIL {code}")
        return 1
    print("PASS BACKUP_ARTIFACT_BOUNDARY_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
