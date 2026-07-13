"""Evaluate PR-5 output safety checker against frozen corrective expectations."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SPIKE_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[4]
EXPECTED_PATH = SPIKE_ROOT / "data" / "fixtures" / "output-safety-expected.v0.2.sample.json"
CHECKER_PATH = SCRIPT_PATH.with_name("check_output_safety.py")


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name}: UTF-8 BOM is not allowed")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name}: must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: JSON root must be an object")
    return data


def expected_text_paths(fixture: dict[str, Any]) -> list[str]:
    result = fixture.get("result")
    if not isinstance(result, dict):
        raise ValueError("fixture result must be an object")
    items = result.get("items")
    if not isinstance(items, list):
        raise ValueError("fixture result.items must be an array")
    paths = ["result.summary"]
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("fixture result.items entries must be objects")
        paths.extend(
            [
                f"result.items[{index}].source_quote",
                f"result.items[{index}].analysis",
                f"result.items[{index}].reason",
                f"result.items[{index}].recommended_action",
            ]
        )
    paths.append("result.disclaimer")
    return paths


def field_value(fixture: dict[str, Any], field_path: str) -> str:
    current: Any = fixture
    for part in field_path.split("."):
        if "[" in part:
            name, index_text = part.split("[", 1)
            current = current[name][int(index_text.rstrip("]"))]
        else:
            current = current[part]
    if not isinstance(current, str):
        raise ValueError(f"{field_path}: field value must be a string")
    return current


def validate_expected(expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if expected.get("schema_version") != "0.2":
        errors.append("schema_version must be 0.2")
    authorship = expected.get("authorship", {})
    if authorship.get("method") != "independent-human-authored-before-implementation":
        errors.append("authorship.method mismatch")
    if authorship.get("implementation_consulted") is not False:
        errors.append("authorship.implementation_consulted must be false")
    if authorship.get("status") != "approved-frozen-before-implementation":
        errors.append("authorship.status mismatch")
    if expected.get("corrective_basis") != "independent-review-field-coverage-gap":
        errors.append("corrective_basis mismatch")
    completeness = expected.get("completeness_policy", {})
    if completeness.get("expected_total_fixture_text_fields") != 48:
        errors.append("expected_total_fixture_text_fields must be 48")
    test_cases = expected.get("test_cases")
    if not isinstance(test_cases, list) or len(test_cases) != 4:
        errors.append("test_cases must contain 4 cases")
        return errors

    seen_case_ids: set[str] = set()
    seen_sources: set[str] = set()
    total_expected_paths = 0
    for case in test_cases:
        case_id = case.get("test_case_id")
        if not isinstance(case_id, str):
            errors.append("test_case_id must be a string")
            continue
        if case_id in seen_case_ids:
            errors.append(f"{case_id}: duplicate test_case_id")
        seen_case_ids.add(case_id)

        source_fixture = case.get("source_fixture")
        if not isinstance(source_fixture, str):
            errors.append(f"{case_id}: source_fixture must be a string")
            continue
        if source_fixture in seen_sources:
            errors.append(f"{case_id}: duplicate source_fixture")
        seen_sources.add(source_fixture)
        fixture_path = REPO_ROOT / source_fixture
        if not fixture_path.exists():
            errors.append(f"{case_id}: source_fixture does not exist")
            continue
        fixture = read_json(fixture_path)
        actual_paths = expected_text_paths(fixture)
        field_expectations = case.get("field_expectations")
        if not isinstance(field_expectations, list):
            errors.append(f"{case_id}: field_expectations must be an array")
            continue
        expected_paths = [item.get("field_path") for item in field_expectations if isinstance(item, dict)]
        total_expected_paths += len(expected_paths)
        if len(expected_paths) != len(set(expected_paths)):
            errors.append(f"{case_id}: duplicate field_path")
        missing = sorted(set(actual_paths) - set(expected_paths))
        extra = sorted(set(expected_paths) - set(actual_paths))
        if missing:
            errors.append(f"{case_id}: missing field paths: {', '.join(missing)}")
        if extra:
            errors.append(f"{case_id}: extra field paths: {', '.join(extra)}")
        counts = {"ALLOW": 0, "BLOCK": 0, "REVIEW": 0}
        for item in field_expectations:
            if not isinstance(item, dict):
                errors.append(f"{case_id}: field expectation must be an object")
                continue
            field_path = item.get("field_path")
            classification = item.get("expected_classification")
            if field_path in actual_paths:
                field_value(fixture, field_path)
            if classification not in counts:
                errors.append(f"{case_id}: invalid classification")
                continue
            counts[classification] += 1
            expected_role = str(field_path).split(".")[-1]
            if item.get("text_role") != expected_role:
                errors.append(f"{case_id}: text_role mismatch at {field_path}")
        if counts["ALLOW"] != case.get("expected_allowed_count"):
            errors.append(f"{case_id}: expected_allowed_count mismatch")
        if counts["BLOCK"] != case.get("expected_violation_count"):
            errors.append(f"{case_id}: expected_violation_count mismatch")
        if counts["REVIEW"] != case.get("expected_review_count"):
            errors.append(f"{case_id}: expected_review_count mismatch")
        if sum(counts.values()) != case.get("expected_total_evaluated_field_count"):
            errors.append(f"{case_id}: expected_total_evaluated_field_count mismatch")
        overall = "BLOCK" if counts["BLOCK"] else "REVIEW" if counts["REVIEW"] else "ALLOW"
        manual = counts["REVIEW"] > 0
        if case.get("expected_overall_status") != overall:
            errors.append(f"{case_id}: expected_overall_status mismatch")
        if case.get("expected_manual_review_required") is not manual:
            errors.append(f"{case_id}: expected_manual_review_required mismatch")
    if total_expected_paths != 48:
        errors.append("total expected field path count must be 48")
    return errors


def run_checker(fixture_path: Path) -> tuple[dict[str, Any], str]:
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), "--input", str(fixture_path)],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"checker failed for {fixture_path.name}: {completed.stderr.strip()}")
    try:
        output = json.loads(completed.stdout, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"checker stdout invalid JSON for {fixture_path.name}: {exc.msg}") from exc
    if not isinstance(output, dict):
        raise ValueError(f"checker stdout root must be object for {fixture_path.name}")
    return output, completed.stdout


def compare_case(case: dict[str, Any]) -> dict[str, Any]:
    fixture_path = REPO_ROOT / case["source_fixture"]
    fixture = read_json(fixture_path)
    expected_paths = [item["field_path"] for item in case["field_expectations"]]
    expected_by_path = {item["field_path"]: item for item in case["field_expectations"]}
    actual, raw_stdout = run_checker(fixture_path)
    actual_results = actual.get("field_results")
    if not isinstance(actual_results, list):
        raise ValueError(f"{case['test_case_id']}: field_results must be an array")
    actual_paths = [item.get("field_path") for item in actual_results if isinstance(item, dict)]
    actual_by_path = {item.get("field_path"): item for item in actual_results if isinstance(item, dict)}
    missing_paths = sorted(set(expected_paths) - set(actual_paths))
    extra_paths = sorted(set(actual_paths) - set(expected_paths))
    duplicate_paths = len(actual_paths) - len(set(actual_paths))

    classification_mismatches = []
    category_mismatches = []
    action_mismatches = []
    for field_path in expected_paths:
        expected = expected_by_path[field_path]
        actual_result = actual_by_path.get(field_path)
        if not actual_result:
            continue
        if actual_result.get("classification") != expected["expected_classification"]:
            classification_mismatches.append(field_path)
        if set(actual_result.get("categories", [])) != set(expected["expected_categories"]):
            category_mismatches.append(field_path)
        if actual_result.get("action") != expected["expected_action"]:
            action_mismatches.append(field_path)

    overall_mismatch = actual.get("overall_status") != case["expected_overall_status"]
    manual_mismatch = actual.get("manual_review_required") is not case["expected_manual_review_required"]
    count_mismatches = []
    count_pairs = [
        ("allowed_count", "expected_allowed_count"),
        ("violation_count", "expected_violation_count"),
        ("review_count", "expected_review_count"),
        ("evaluated_field_count", "expected_total_evaluated_field_count"),
    ]
    for actual_key, expected_key in count_pairs:
        if actual.get(actual_key) != case[expected_key]:
            count_mismatches.append(actual_key)

    raw_text_exposure = 0
    for field_path in expected_paths:
        value = field_value(fixture, field_path)
        if value and value in raw_stdout:
            raw_text_exposure += 1

    return {
        "test_case_id": case["test_case_id"],
        "passed": not (
            missing_paths
            or extra_paths
            or duplicate_paths
            or classification_mismatches
            or category_mismatches
            or action_mismatches
            or overall_mismatch
            or manual_mismatch
            or count_mismatches
            or raw_text_exposure
        ),
        "field_count": actual.get("evaluated_field_count", 0),
        "allow": actual.get("allowed_count", 0),
        "block": actual.get("violation_count", 0),
        "review": actual.get("review_count", 0),
        "missing_paths": missing_paths,
        "extra_paths": extra_paths,
        "duplicate_paths": duplicate_paths,
        "classification_mismatches": classification_mismatches,
        "category_mismatches": category_mismatches,
        "action_mismatches": action_mismatches,
        "overall_mismatch": overall_mismatch,
        "manual_mismatch": manual_mismatch,
        "count_mismatches": count_mismatches,
        "raw_text_exposure": raw_text_exposure,
    }


def summarize(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall": "PASS" if all(item["passed"] for item in case_results) else "FAIL",
        "test_cases_passed": sum(1 for item in case_results if item["passed"]),
        "test_cases_total": len(case_results),
        "fields": sum(item["field_count"] for item in case_results),
        "allow": sum(item["allow"] for item in case_results),
        "block": sum(item["block"] for item in case_results),
        "review": sum(item["review"] for item in case_results),
        "missing_paths": sum(len(item["missing_paths"]) for item in case_results),
        "extra_paths": sum(len(item["extra_paths"]) for item in case_results),
        "duplicate_paths": sum(item["duplicate_paths"] for item in case_results),
        "classification_mismatches": sum(len(item["classification_mismatches"]) for item in case_results),
        "category_mismatches": sum(len(item["category_mismatches"]) for item in case_results),
        "action_mismatches": sum(len(item["action_mismatches"]) for item in case_results),
        "overall_mismatches": sum(1 for item in case_results if item["overall_mismatch"]),
        "manual_mismatches": sum(1 for item in case_results if item["manual_mismatch"]),
        "count_mismatches": sum(len(item["count_mismatches"]) for item in case_results),
        "raw_text_exposure": sum(item["raw_text_exposure"] for item in case_results),
        "case_results": case_results,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print(f"Output safety evaluation: {summary['overall']}")
    print(f"test_cases: {summary['test_cases_passed']}/{summary['test_cases_total']}")
    print(f"fields: {summary['fields']}/48")
    print(f"allow: {summary['allow']}")
    print(f"block: {summary['block']}")
    print(f"review: {summary['review']}")
    print(f"missing_paths: {summary['missing_paths']}")
    print(f"extra_paths: {summary['extra_paths']}")
    print(f"duplicate_paths: {summary['duplicate_paths']}")
    print(f"classification_mismatches: {summary['classification_mismatches']}")
    print(f"category_mismatches: {summary['category_mismatches']}")
    print(f"action_mismatches: {summary['action_mismatches']}")
    print(f"overall_mismatches: {summary['overall_mismatches']}")
    print(f"raw_text_exposure: {summary['raw_text_exposure']}")
    for case in summary["case_results"]:
        print(f"{case['test_case_id']}: {'PASS' if case['passed'] else 'FAIL'}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PR-5 output safety checker.")
    parser.add_argument("--expected", default=str(EXPECTED_PATH), help="Frozen output safety expected JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        args = parse_args(argv or sys.argv[1:])
        expected = read_json(Path(args.expected))
        errors = validate_expected(expected)
        if errors:
            raise ValueError("; ".join(errors))
        case_results = [compare_case(case) for case in expected["test_cases"]]
        summary = summarize(case_results)
        print_summary(summary)
        return 0 if summary["overall"] == "PASS" else 1
    except Exception as exc:
        print(f"output safety evaluation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
