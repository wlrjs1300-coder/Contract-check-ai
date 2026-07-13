"""Evaluate masked-contract usefulness checks against frozen expectations.

Automatic checks can pass, but this PR-4 spike still requires manual review for
party-role meaning, required-context meaning, major meaning loss, and
token-induced ambiguity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from compare_masked_contract import SPIKE_ROOT, compare_case


EXPECTED_PATH = SPIKE_ROOT / "data" / "fixtures" / "masking-usefulness-expected.sample.json"
FORBIDDEN_EXPECTED_FIELDS = {"text", "raw_text", "value", "source_value", "matched_text"}
SUPPORTED_CONTEXT_MODES = {
    "exact_presence",
    "normalized_presence",
    "pattern_presence_plus_manual_review",
}


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")


def read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name}: UTF-8 BOM is not allowed")
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("expected JSON must be an object")
    return data


def _walk_for_forbidden_fields(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_EXPECTED_FIELDS:
                findings.append(f"{path}.{key}")
            findings.extend(_walk_for_forbidden_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_walk_for_forbidden_fields(child, f"{path}[{index}]"))
    return findings


def validate_expected(expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    authorship = expected.get("authorship", {})
    if expected.get("schema_version") != "0.2":
        errors.append("schema_version must be 0.2")
    if authorship.get("method") != "independent-human-authored-before-implementation":
        errors.append("authorship.method mismatch")
    if authorship.get("implementation_consulted") is not False:
        errors.append("authorship.implementation_consulted must be false")
    if authorship.get("status") != "approved-frozen-before-implementation":
        errors.append("authorship.status mismatch")

    test_cases = expected.get("test_cases")
    if not isinstance(test_cases, list) or len(test_cases) != 4:
        errors.append("test_cases must contain exactly 4 cases")
        return errors

    seen_ids: set[str] = set()
    for case in test_cases:
        case_id = case.get("test_case_id", "<missing>")
        if case_id in seen_ids:
            errors.append(f"{case_id}: duplicate test_case_id")
        seen_ids.add(case_id)

        source_fixture = case.get("source_fixture")
        if not isinstance(source_fixture, str) or not (SPIKE_ROOT.parents[1] / source_fixture).exists():
            errors.append(f"{case_id}: source_fixture does not exist")

        if "clause_expectation" not in case:
            errors.append(f"{case_id}: missing clause_expectation")

        expected_case = case.get("expected", {})
        for field in (
            "clause_count_preserved",
            "clause_order_preserved",
            "clause_identity_preserved",
            "non_pii_text_preserved",
            "repeated_token_consistency",
            "required_context_preserved",
            "residual_detector_matches_expected",
            "major_meaning_loss_count_expected",
            "token_induced_ambiguity_count_expected",
        ):
            if field not in expected_case:
                errors.append(f"{case_id}: missing expected.{field}")

        contract_check = case.get("contract_type_check")
        if contract_check and contract_check.get("applicable") is False:
            if expected_case.get("contract_type_preserved") is not None:
                errors.append(f"{case_id}: edge contract_type_preserved must be null")

        for context in case.get("required_context", []):
            if "scope" not in context:
                errors.append(f"{case_id}: context {context.get('context_id')} missing scope")
            if "require_all_in_same_scope" not in context:
                errors.append(f"{case_id}: context {context.get('context_id')} missing require_all_in_same_scope")
            if context.get("verification_mode") not in SUPPORTED_CONTEXT_MODES:
                errors.append(f"{case_id}: context {context.get('context_id')} unsupported verification mode")

    forbidden = _walk_for_forbidden_fields(expected)
    if forbidden:
        errors.append(f"forbidden raw-value fields present: {', '.join(forbidden)}")
    return errors


def _automatic_checks(case: dict[str, Any], comparison: dict[str, Any]) -> list[dict[str, Any]]:
    expected = case["expected"]
    checks = [
        {
            "name": "clause_count_preserved",
            "passed": comparison["clause_count_preserved"] is expected["clause_count_preserved"],
        },
        {
            "name": "clause_order_preserved",
            "passed": comparison["clause_order_preserved"] is expected["clause_order_preserved"],
        },
        {
            "name": "clause_identity_preserved",
            "passed": comparison["clause_identity_preserved"] is expected["clause_identity_preserved"],
        },
        {
            "name": "non_pii_text_preserved",
            "passed": comparison["non_pii_text_preserved"] is expected["non_pii_text_preserved"],
        },
        {
            "name": "repeated_token_consistency",
            "passed": comparison["repeated_token_consistency"] is expected["repeated_token_consistency"],
        },
        {
            "name": "residual_detector_matches",
            "passed": comparison["residual_detector_matches"] == expected["residual_detector_matches_expected"],
        },
    ]

    if expected.get("contract_type_preserved") is not None:
        checks.append(
            {
                "name": "contract_type_preserved",
                "passed": comparison["contract_type_preserved"] is expected["contract_type_preserved"],
            }
        )
    else:
        checks.append({"name": "contract_type_preserved", "passed": True, "status": "N/A"})

    context_results = comparison["required_context_results"]
    checks.append(
        {
            "name": "required_context_pattern_presence",
            "passed": all(item["automatic_status"] == "PASS" for item in context_results),
        }
    )
    party_results = comparison["party_role_prescreen"]
    checks.append(
        {
            "name": "party_role_pattern_presence",
            "passed": all(item["automatic_status"] == "PASS" for item in party_results),
        }
    )
    return checks


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    comparison = compare_case(case)
    checks = _automatic_checks(case, comparison)
    failed_checks = [item["name"] for item in checks if not item["passed"]]

    manual_fields = case.get("manual_review", {}).get("fields", [])
    pending_manual_fields = [
        field
        for field in manual_fields
        if field
        in {
            "party_roles_preserved",
            "required_context_preserved",
            "major_meaning_loss_count",
            "token_induced_ambiguity_count",
        }
    ]
    if any(item["manual_review_required"] for item in comparison["required_context_results"]):
        if "required_context_preserved" not in pending_manual_fields:
            pending_manual_fields.append("required_context_preserved")
    if any(item["manual_review_required"] for item in comparison["party_role_prescreen"]):
        if "party_roles_preserved" not in pending_manual_fields:
            pending_manual_fields.append("party_roles_preserved")

    if failed_checks:
        automatic_status = "FAIL"
        overall_status = "FAIL"
    else:
        automatic_status = "PASS"
        overall_status = "PENDING_REVIEW" if pending_manual_fields else "PASS"

    return {
        "test_case_id": case["test_case_id"],
        "automatic_status": automatic_status,
        "manual_review_status": "PENDING" if pending_manual_fields else "NOT_REQUIRED",
        "overall_status": overall_status,
        "failed_checks": failed_checks,
        "pending_manual_fields": sorted(set(pending_manual_fields)),
        "automatic_checks": checks,
        "contract_type_status": comparison["contract_type_status"],
        "required_context_results": comparison["required_context_results"],
        "party_role_prescreen": comparison["party_role_prescreen"],
        "residual_detector_matches": comparison["residual_detector_matches"],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    automatic_checks = [check for result in results for check in result["automatic_checks"]]
    automatic_failed = [check for check in automatic_checks if not check["passed"]]
    pending_cases = [result for result in results if result["overall_status"] == "PENDING_REVIEW"]
    failed_cases = [result for result in results if result["overall_status"] == "FAIL"]
    overall = "FAIL" if failed_cases else "PENDING_REVIEW" if pending_cases else "PASS"
    return {
        "overall_status": overall,
        "test_case_count": len(results),
        "automatic_checks_passed": len(automatic_checks) - len(automatic_failed),
        "automatic_checks_total": len(automatic_checks),
        "automatic_failures": len(automatic_failed),
        "manual_review_pending_cases": len(pending_cases),
        "residual_detector_matches": sum(result["residual_detector_matches"] for result in results),
        "results": results,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print(f"PR-4 masking usefulness evaluation: {summary['overall_status']}")
    print(f"test_cases: {summary['test_case_count']}")
    print(f"automatic_checks: {summary['automatic_checks_passed']}/{summary['automatic_checks_total']}")
    print(f"automatic_failures: {summary['automatic_failures']}")
    print(f"manual_review_pending_cases: {summary['manual_review_pending_cases']}")
    print(f"residual_detector_matches: {summary['residual_detector_matches']}")
    print("major_meaning_loss: PENDING")
    print("token_induced_ambiguity: PENDING")
    print()
    for result in summary["results"]:
        failed = ", ".join(result["failed_checks"]) if result["failed_checks"] else "none"
        pending = ", ".join(result["pending_manual_fields"]) if result["pending_manual_fields"] else "none"
        print(f"{result['test_case_id']}:")
        print(f"  automatic_status: {result['automatic_status']}")
        print(f"  manual_review_status: {result['manual_review_status']}")
        print(f"  overall_status: {result['overall_status']}")
        print(f"  contract_type_status: {result['contract_type_status']}")
        print(f"  failed_checks: {failed}")
        print(f"  pending_checks: {pending}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PR-4 masking usefulness expectations.")
    parser.add_argument("--expected", default=str(EXPECTED_PATH), help="Frozen masking usefulness expected JSON")
    parser.add_argument("--output", help="Optional sanitized summary JSON output path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print optional JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        args = parse_args(argv or sys.argv[1:])
        expected = read_json(Path(args.expected))
        errors = validate_expected(expected)
        if errors:
            raise ValueError("; ".join(errors))
        results = [evaluate_case(case) for case in expected["test_cases"]]
        summary = summarize(results)
        print_summary(summary)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            indent = 2 if args.pretty else None
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        return 1 if summary["overall_status"] == "FAIL" else 0
    except Exception as exc:
        print(f"masking usefulness evaluation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
