"""Evaluate deterministic PII masking against frozen expected fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SPIKE_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[4]
EXPECTED_PATH = SPIKE_ROOT / "data" / "fixtures" / "pii-masking-expected.sample.json"
DETECTOR_PATH = SCRIPT_PATH.with_name("detect_and_mask.py")

FORBIDDEN_ENTITY_FIELDS = {"text", "raw_text", "value", "source_value", "matched_text"}


def _load_detector_module():
    spec = importlib.util.spec_from_file_location("detect_and_mask", DETECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load detector module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["detect_and_mask"] = module
    spec.loader.exec_module(module)
    return module


DETECTOR = _load_detector_module()


def _read_utf8(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name}: UTF-8 BOM is not allowed")
    return data.decode("utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_hash(text: str, start: int, end: int) -> str:
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:12]


def _intervals(records: list[dict[str, Any]]) -> list[tuple[int, int, int]]:
    return [(item["start_offset"], item["end_offset"], item["ordinal"]) for item in records]


def _overlap_count(left: list[tuple[int, int, int]], right: list[tuple[int, int, int]]) -> int:
    count = 0
    same_list = left is right
    for left_index, left_item in enumerate(left):
        start_at = left_index + 1 if same_list else 0
        for right_item in right[start_at:]:
            if max(left_item[0], right_item[0]) < min(left_item[1], right_item[1]):
                count += 1
    return count


def _safe_record_differences(
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
    fields: tuple[str, ...],
) -> list[str]:
    if actual is None:
        return ["missing_actual"]
    differences: list[str] = []
    for field in fields:
        if expected.get(field) != actual.get(field):
            differences.append(field)
    return differences


def _actual_by_ordinal(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {item["ordinal"]: item for item in records}


def _contains_forbidden_fields(records: list[dict[str, Any]]) -> bool:
    return any(FORBIDDEN_ENTITY_FIELDS.intersection(item.keys()) for item in records)


def _subprocess_result(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(DETECTOR_PATH), "--input", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"detector CLI failed for {path.name} with exit code {completed.returncode}")
    return json.loads(completed.stdout.decode("utf-8"))


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    source_path = REPO_ROOT / case["source_file"]
    source_text = DETECTOR.normalize_text(_read_utf8(source_path))
    actual = DETECTOR.detect_and_mask(source_text)
    cli_actual = _subprocess_result(source_path)

    failures: list[str] = []
    expected_entities = case["expected_entities"]
    expected_exclusions = case["expected_false_positive_exclusions"]
    actual_entities = actual["entities"]

    if cli_actual != actual:
        failures.append("cli_stdout_result")

    if _sha256_text(source_text) != case["source_text_sha256"]:
        failures.append("source_text_sha256")

    if len(actual_entities) != len(expected_entities):
        failures.append("entity_count")

    if actual["masked_text_sha256"] != case["expected_masked_text_sha256"]:
        failures.append("masked_text_sha256")

    if actual["document_warnings"] != case["expected_document_warnings"]:
        failures.append("document_warnings")

    actual_records = _actual_by_ordinal(actual_entities)
    comparison_fields = (
        "ordinal",
        "entity_type",
        "start_offset",
        "end_offset",
        "source_line_start",
        "source_line_end",
    )
    for expected in expected_entities:
        actual_record = actual_records.get(expected["ordinal"])
        differences = _safe_record_differences(expected, actual_record, comparison_fields)
        if actual_record is not None:
            if actual_record.get("mask_token") != expected.get("expected_mask_token"):
                differences.append("mask_token")
            if actual_record.get("source_hash") != expected.get("expected_entity_source_hash"):
                differences.append("source_hash")
            if actual_record.get("warnings") != expected.get("expected_warnings"):
                differences.append("warnings")
            calculated_hash = _source_hash(source_text, expected["start_offset"], expected["end_offset"])
            if calculated_hash != expected["expected_entity_source_hash"]:
                differences.append("expected_source_hash")
        if differences:
            failures.append(f"entity:{expected['ordinal']}:{','.join(differences)}")

    if _contains_forbidden_fields(actual_entities):
        failures.append("raw_value_field")

    entity_intervals = _intervals(actual_entities)
    exclusion_intervals = _intervals(expected_exclusions)
    entity_overlap = _overlap_count(entity_intervals, entity_intervals)
    exclusion_overlap = _overlap_count(entity_intervals, exclusion_intervals)
    if entity_overlap:
        failures.append("entity_overlap")
    if exclusion_overlap:
        failures.append("exclusion_overlap")

    replaced_expected_spans = all(
        expected["expected_mask_token"] in actual["masked_text"] for expected in expected_entities
    )
    if not replaced_expected_spans:
        failures.append("expected_span_replacement")

    residual = DETECTOR.detect_entities(actual["masked_text"])
    residual_count = len(residual)
    if residual_count:
        failures.append("residual_entities")

    return {
        "test_case_id": case["test_case_id"],
        "passed": not failures,
        "failures": failures,
        "source_sha": "PASS" if _sha256_text(source_text) == case["source_text_sha256"] else "FAIL",
        "entity_count": len(actual_entities),
        "expected_entity_count": len(expected_entities),
        "exclusion_overlap_count": exclusion_overlap,
        "masked_sha": "PASS"
        if actual["masked_text_sha256"] == case["expected_masked_text_sha256"]
        else "FAIL",
        "residual_detection_count": residual_count,
    }


def _load_expected() -> dict[str, Any]:
    return json.loads(_read_utf8(EXPECTED_PATH))


def main() -> int:
    try:
        expected = _load_expected()
        cases = expected["test_cases"]
        results = [_evaluate_case(case) for case in cases]
    except Exception as exc:
        print(f"PII masking evaluation error: {exc}", file=sys.stderr)
        return 2

    passed_count = sum(1 for item in results if item["passed"])
    entity_count = sum(item["entity_count"] for item in results)
    expected_entity_count = sum(item["expected_entity_count"] for item in results)
    exclusion_count = sum(len(case["expected_false_positive_exclusions"]) for case in cases)
    residual_count = sum(item["residual_detection_count"] for item in results)

    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{item['test_case_id']}: {status}")
        print(f"  source_sha: {item['source_sha']}")
        print(f"  entity_count: {item['entity_count']}/{item['expected_entity_count']}")
        print(f"  exclusion_overlap_count: {item['exclusion_overlap_count']}")
        print(f"  masked_sha: {item['masked_sha']}")
        print(f"  residual_detection_count: {item['residual_detection_count']}")
        if item["failures"]:
            print(f"  failure_fields: {', '.join(item['failures'])}")

    print()
    print(f"PII masking evaluation: {'PASS' if passed_count == len(results) else 'FAIL'}")
    print(f"test_cases: {passed_count}/{len(results)}")
    print(f"entities: {entity_count}/{expected_entity_count}")
    print(f"exclusions: {exclusion_count}/{exclusion_count}")
    print(f"residual_entities: {residual_count}")

    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
