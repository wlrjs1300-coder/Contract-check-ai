from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


_FORBIDDEN_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "service-account.json",
}
_FORBIDDEN_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
)
_TOKEN_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?ix)
    \b(
        JWT_SECRET|EMAIL_LOOKUP_HMAC_KEY|DATA_ENCRYPTION_KEYS_JSON|
        MYSQL_PASSWORD|MYSQL_ROOT_PASSWORD|PROVIDER_API_KEY
    )\b
    \s*(?:=|:)\s*
    ["']?([^"'#,\r\n}]+)
    """
)
_SAFE_ASSIGNMENT_MARKERS = (
    "${",
    "os.getenv",
    "os.environ",
    "synthetic",
    "example",
    "placeholder",
    "validation-only",
)


def _is_fixture_path(path: Path) -> bool:
    normalized = path.as_posix().lower()
    return normalized.startswith("backend/tests/") or "/fixtures/" in normalized


def scan_content(path: Path, content: str) -> frozenset[str]:
    findings: set[str] = set()
    if _PRIVATE_KEY_PATTERN.search(content):
        findings.add("PRIVATE_KEY_MATERIAL")
    if _TOKEN_PATTERN.search(content) and not _is_fixture_path(path):
        findings.add("TOKEN_MATERIAL")

    if not _is_fixture_path(path) and path.name != ".env.example":
        for match in _SECRET_ASSIGNMENT_PATTERN.finditer(content):
            candidate = match.group(2).strip()
            lowered = candidate.lower()
            if candidate and not any(marker in lowered for marker in _SAFE_ASSIGNMENT_MARKERS):
                findings.add("SECRET_LITERAL")
    return frozenset(findings)


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
    for relative_path in _candidate_files(repository):
        lowered_name = relative_path.name.lower()
        if (
            lowered_name in _FORBIDDEN_FILE_NAMES
            or relative_path.suffix.lower() in _FORBIDDEN_SUFFIXES
        ):
            findings.add("FORBIDDEN_CREDENTIAL_FILE")
            continue

        absolute_path = repository / relative_path
        try:
            content = absolute_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.update(scan_content(relative_path, content))
    return frozenset(findings)


def main() -> int:
    try:
        findings = validate_repository(Path(__file__).resolve().parents[1])
    except Exception:
        print("FAIL SECRET_BOUNDARY_SCAN_ERROR")
        return 2
    if findings:
        for safe_code in sorted(findings):
            print(f"FAIL {safe_code}")
        return 1
    print("PASS SECRET_BOUNDARIES_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
