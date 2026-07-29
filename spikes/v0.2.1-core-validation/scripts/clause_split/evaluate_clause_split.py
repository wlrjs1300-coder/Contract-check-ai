"""Evaluate clause splitting CLI output against frozen expected fixture data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REFERENCE_ID_RE = re.compile(r"^(.+):clause:(\d+):(\d+)-(\d+)$")
SCRIPT_DIR = Path(__file__).resolve().parent
SPLIT_SCRIPT_PATH = SCRIPT_DIR / "split_clauses.py"


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")


def normalize_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not valid UTF-8: {exc.reason}") from exc


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_source_hash(text: str) -> str:
    return sha256_text(text)[:12]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(normalize_bytes(path.read_bytes()))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("expected JSON must be an object")
    return value


def read_text(path: Path) -> str:
    return normalize_bytes(path.read_bytes())


def compare_sequence(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    fields: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    missing = []
    extra = []
    mismatches = []

    if len(actual) < len(expected):
        missing.extend(expected[len(actual) :])
    if len(actual) > len(expected):
        extra.extend(actual[len(expected) :])

    for index, (expected_item, actual_item) in enumerate(zip(expected, actual), start=1):
        for expected_field, actual_field in fields:
            if expected_item.get(expected_field) != actual_item.get(actual_field):
                mismatches.append(
                    {
                        "index": index,
                        "field": actual_field,
                        "expected": expected_item.get(expected_field),
                        "actual": actual_item.get(actual_field),
                    }
                )
    return missing, extra, mismatches


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def decode_cli_stdout(stdout: bytes) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if stdout.startswith(b"\xef\xbb\xbf"):
        errors.append("stdout contains UTF-8 BOM")
    if b"\r\n" in stdout:
        errors.append("stdout contains CRLF")
    try:
        decoded = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return None, errors + [f"stdout is not valid UTF-8: {exc.reason}"]
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as exc:
        return None, errors + [f"stdout is not valid JSON: {exc.msg}"]
    if not isinstance(parsed, dict):
        return None, errors + ["stdout JSON must be an object"]
    return parsed, errors


def safe_stderr(stderr: bytes) -> str:
    if not stderr:
        return ""
    return stderr.decode("utf-8", errors="replace").strip()


def run_split_cli(source_path: Path, test_case_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SPLIT_SCRIPT_PATH),
            "--input",
            str(source_path),
            "--test-case-id",
            test_case_id,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"split_clauses.py exited with code {completed.returncode}")
        stderr = safe_stderr(completed.stderr)
        if stderr:
            errors.append(f"stderr: {stderr}")
    actual, stdout_errors = decode_cli_stdout(completed.stdout)
    errors.extend(stdout_errors)
    return actual, errors


def validate_reference_ids(actual: dict[str, Any]) -> list[dict[str, Any]]:
    invalid = []
    for clause in actual["clauses"]:
        reference_id = clause["reference_id"]
        match = REFERENCE_ID_RE.match(reference_id)
        if not match:
            invalid.append({"reference_id": reference_id, "reason": "format"})
            continue
        case_id, ordinal, start, end = match.groups()
        if case_id != actual["test_case_id"]:
            invalid.append({"reference_id": reference_id, "reason": "test_case_id"})
        if int(ordinal) != clause["ordinal"]:
            invalid.append({"reference_id": reference_id, "reason": "ordinal"})
        if int(start) != clause["start_offset"] or int(end) != clause["end_offset"]:
            invalid.append({"reference_id": reference_id, "reason": "offset"})
    return invalid


def validate_source_hashes(actual: dict[str, Any], text: str) -> list[dict[str, Any]]:
    invalid = []
    for clause in actual["clauses"]:
        source = text[clause["start_offset"] : clause["end_offset"]]
        expected_hash = short_source_hash(source)
        if clause["source_hash"] != expected_hash:
            invalid.append(
                {
                    "reference_id": clause["reference_id"],
                    "expected": expected_hash,
                    "actual": clause["source_hash"],
                }
            )
    return invalid


def all_sections(actual: dict[str, Any]) -> list[dict[str, Any]]:
    sections = []
    for clause in actual["clauses"]:
        sections.append({"kind": "clause", **clause})
    for section in actual["non_clause_sections"]:
        sections.append({"kind": "non_clause", **section})
    for section in actual["unclassified_sections"]:
        sections.append({"kind": "unclassified", **section})
    return sorted(sections, key=lambda item: (item["start_offset"], item["end_offset"]))


def overlapping_sections(actual: dict[str, Any]) -> list[dict[str, Any]]:
    overlaps = []
    sections = all_sections(actual)
    previous = None
    for section in sections:
        if previous and section["start_offset"] < previous["end_offset"]:
            overlaps.append({"previous": previous, "current": section})
        previous = section
    return overlaps


def uncovered_non_whitespace_count(actual: dict[str, Any], text: str) -> int:
    covered = [False] * len(text)
    for section in all_sections(actual):
        for index in range(section["start_offset"], section["end_offset"]):
            if 0 <= index < len(covered):
                covered[index] = True
    return sum(1 for index, char in enumerate(text) if char.strip() and not covered[index])


def warning_counts(actual: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for clause in actual["clauses"]:
        for warning in clause["warnings"]:
            counts[warning] = counts.get(warning, 0) + 1
    for section in actual["non_clause_sections"]:
        for warning in section["warnings"]:
            counts[warning] = counts.get(warning, 0) + 1
    for section in actual["unclassified_sections"]:
        for warning in section["warnings"]:
            counts[warning] = counts.get(warning, 0) + 1
    for warning in actual["document_warnings"]:
        counts[warning] = counts.get(warning, 0) + 1
    return dict(sorted(counts.items()))


def failed_cli_result(case: dict[str, Any], text: str, notes: list[str]) -> dict[str, Any]:
    return {
        "test_case_id": case["test_case_id"],
        "passed": False,
        "expected_clause_count": len(case["expected_clauses"]),
        "actual_clause_count": 0,
        "missing_clauses": case["expected_clauses"],
        "extra_clauses": [],
        "mismatched_fields": [],
        "missing_non_clause_sections": case["expected_non_clause_sections"],
        "extra_non_clause_sections": [],
        "missing_unclassified_sections": case["expected_unclassified_sections"],
        "extra_unclassified_sections": [],
        "source_text_sha256_matches": sha256_text(text) == case["source_text_sha256"],
        "document_warnings_match": False,
        "duplicate_reference_ids": [],
        "invalid_reference_ids": [],
        "invalid_source_hashes": [],
        "overlapping_sections": [],
        "uncovered_non_whitespace_characters": sum(1 for char in text if char.strip()),
        "warning_counts": {},
        "manual_review_required": True,
        "notes": notes,
    }


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(case["source_file"])
    text = read_text(source_path)
    actual, cli_errors = run_split_cli(source_path, case["test_case_id"])
    if cli_errors or actual is None:
        return failed_cli_result(case, text, cli_errors)

    clause_fields = [
        ("ordinal", "ordinal"),
        ("marker", "marker"),
        ("clause_type", "clause_type"),
        ("title", "title"),
        ("raw_heading", "raw_heading"),
        ("body", "body"),
        ("start_offset", "start_offset"),
        ("end_offset", "end_offset"),
        ("source_line_start", "source_line_start"),
        ("source_line_end", "source_line_end"),
        ("expected_warnings", "warnings"),
    ]
    section_fields = [
        ("type", "type"),
        ("text", "text"),
        ("start_offset", "start_offset"),
        ("end_offset", "end_offset"),
        ("source_line_start", "source_line_start"),
        ("source_line_end", "source_line_end"),
        ("expected_warnings", "warnings"),
    ]

    missing_clauses, extra_clauses, clause_mismatches = compare_sequence(
        case["expected_clauses"], actual["clauses"], clause_fields
    )
    missing_non, extra_non, non_mismatches = compare_sequence(
        case["expected_non_clause_sections"], actual["non_clause_sections"], section_fields
    )
    missing_unclassified, extra_unclassified, unclassified_mismatches = compare_sequence(
        case["expected_unclassified_sections"], actual["unclassified_sections"], section_fields
    )

    mismatched_fields = clause_mismatches + [
        {"section": "non_clause_sections", **item} for item in non_mismatches
    ] + [{"section": "unclassified_sections", **item} for item in unclassified_mismatches]

    source_hash_matches = sha256_text(text) == case["source_text_sha256"]
    document_warning_matches = actual["document_warnings"] == case["expected_document_warnings"]
    duplicate_reference_ids = duplicate_values([clause["reference_id"] for clause in actual["clauses"]])
    invalid_reference_ids = validate_reference_ids(actual)
    invalid_source_hashes = validate_source_hashes(actual, text)
    overlaps = overlapping_sections(actual)
    uncovered = uncovered_non_whitespace_count(actual, text)

    notes = []
    if not source_hash_matches:
        notes.append("fixture source_text_sha256 mismatch")
    if not document_warning_matches:
        notes.append("document_warnings mismatch")
    if invalid_reference_ids:
        notes.append("invalid reference_id")
    if invalid_source_hashes:
        notes.append("invalid source_hash")
    if overlaps:
        notes.append("overlapping sections")
    if uncovered:
        notes.append("uncovered non-whitespace characters")

    passed = not any(
        [
            missing_clauses,
            extra_clauses,
            missing_non,
            extra_non,
            missing_unclassified,
            extra_unclassified,
            mismatched_fields,
            not source_hash_matches,
            not document_warning_matches,
            duplicate_reference_ids,
            invalid_reference_ids,
            invalid_source_hashes,
            overlaps,
            uncovered,
        ]
    )

    return {
        "test_case_id": case["test_case_id"],
        "passed": passed,
        "expected_clause_count": len(case["expected_clauses"]),
        "actual_clause_count": len(actual["clauses"]),
        "missing_clauses": missing_clauses,
        "extra_clauses": extra_clauses,
        "mismatched_fields": mismatched_fields,
        "missing_non_clause_sections": missing_non,
        "extra_non_clause_sections": extra_non,
        "missing_unclassified_sections": missing_unclassified,
        "extra_unclassified_sections": extra_unclassified,
        "source_text_sha256_matches": source_hash_matches,
        "document_warnings_match": document_warning_matches,
        "duplicate_reference_ids": duplicate_reference_ids,
        "invalid_reference_ids": invalid_reference_ids,
        "invalid_source_hashes": invalid_source_hashes,
        "overlapping_sections": overlaps,
        "uncovered_non_whitespace_characters": uncovered,
        "warning_counts": warning_counts(actual),
        "manual_review_required": not passed,
        "notes": notes,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": all(result["passed"] for result in results),
        "test_case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "results": results,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate clause splitting output against frozen expected data.")
    parser.add_argument("--expected", required=True, help="Frozen expected JSON path")
    parser.add_argument("--output", help="Optional summary JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        args = parse_args(argv or sys.argv[1:])
        expected = read_json(Path(args.expected))
        test_cases = expected.get("test_cases")
        if not isinstance(test_cases, list):
            raise ValueError("expected JSON must contain a 'test_cases' array")
        results = [evaluate_case(case) for case in test_cases]
        summary = summarize(results)
        output = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(output, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(output)
        return 0 if summary["passed"] else 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
