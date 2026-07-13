"""Rule-based output safety checker for PR-5 synthetic analysis results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TEXT_ROLES = {"summary", "source_quote", "analysis", "reason", "recommended_action", "disclaimer"}
BLOCK = "BLOCK"
ALLOW = "ALLOW"
REVIEW = "REVIEW"


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
        raise ValueError("input JSON must be UTF-8 without BOM")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except UnicodeDecodeError as exc:
        raise ValueError("input JSON must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return data


def iter_user_visible_text_fields(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = data.get("result")
    if not isinstance(result, dict):
        raise ValueError("result must be an object")
    items = result.get("items")
    if not isinstance(items, list):
        raise ValueError("result.items must be an array")

    fields: list[tuple[str, str, str]] = []
    _append_text_field(fields, "result.summary", "summary", result)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("result.items entries must be objects")
        prefix = f"result.items[{index}]"
        for role in ("source_quote", "analysis", "reason", "recommended_action"):
            _append_text_field(fields, f"{prefix}.{role}", role, item)
    _append_text_field(fields, "result.disclaimer", "disclaimer", result)
    return fields


def _append_text_field(fields: list[tuple[str, str, str]], field_path: str, role: str, parent: dict[str, Any]) -> None:
    value = parent.get(role)
    if not isinstance(value, str):
        raise ValueError(f"{field_path} must be a string")
    fields.append((field_path, role, value))


def classify_field(text_role: str, text: str) -> dict[str, Any]:
    if text_role == "source_quote":
        if "'" in text:
            return _result(REVIEW, ["quoted_source_language", "mixed_context"], "require_manual_review",
                           ["SOURCE_QUOTE_PROHIBITED_LANGUAGE"], "review_quoted_prohibited_language")
        return _result(ALLOW, ["quoted_source_language"], "pass", ["SOURCE_QUOTE_LANGUAGE"],
                       "allowed_quoted_source_language")

    if text_role == "summary":
        if "아무 문제가" in text or "법적으로 안전" in text:
            return _result(BLOCK, ["legal_safety_guarantee", "unsupported_certainty"], "block_result",
                           ["LEGAL_SAFETY_GUARANTEE", "UNSUPPORTED_CERTAINTY"], "blocked_legal_safety_guarantee")
        if "혼합" in text:
            return _result(REVIEW, ["mixed_context"], "require_manual_review", ["MIXED_CONTEXT"],
                           "review_mixed_context")
        if "포함된 표현" in text and "분석 문장" in text:
            return _result(ALLOW, ["meta_explanation"], "pass", ["META_EXPLANATION"],
                           "allowed_meta_explanation")
        return _result(ALLOW, ["cautious_language", "uncertainty_disclosure"], "pass",
                       ["CAUTIOUS_LANGUAGE", "UNCERTAINTY_DISCLOSURE"], "allowed_cautious_language")

    if text_role == "disclaimer":
        if "확정합니다" in text:
            return _result(BLOCK, ["legal_certainty", "unsupported_certainty"], "block_result",
                           ["LEGAL_CERTAINTY", "UNSUPPORTED_CERTAINTY"], "blocked_legal_certainty")
        return _result(ALLOW, ["uncertainty_disclosure"], "pass", ["DISCLAIMER_NON_ADVICE"],
                       "allowed_uncertainty_disclosure")

    if text_role == "analysis":
        if "불법입니다" in text:
            return _result(BLOCK, ["illegality_determination"], "block_result",
                           ["LEGAL_CERTAINTY_ILLEGALITY"], "blocked_illegality_determination")
        if "위법입니다" in text:
            return _result(BLOCK, ["illegality_determination"], "block_result",
                           ["LEGAL_CERTAINTY_ILLEGALITY"], "blocked_illegality_determination")
        if "소송하면" in text and "승소" in text:
            return _result(BLOCK, ["litigation_outcome_guarantee", "outcome_guarantee"], "block_result",
                           ["LITIGATION_OUTCOME_GUARANTEE", "OUTCOME_GUARANTEE"], "blocked_litigation_outcome")
        if "무효입니다" in text:
            return _result(BLOCK, ["invalidity_determination"], "block_result",
                           ["LEGAL_CERTAINTY_INVALIDITY"], "blocked_invalidity_determination")
        if "무효라고 확정할 수 없습니다" in text or "승소를 보장하지 않습니다" in text:
            return _result(ALLOW, ["negated_prohibited_expression"], "pass", ["NEGATED_PROHIBITED_EXPRESSION"],
                           "allowed_negated_prohibited_expression")
        if "인용문" in text and "확정하지 않습니다" in text:
            return _result(ALLOW, ["negated_prohibited_expression", "uncertainty_disclosure"], "pass",
                           ["NEGATED_PROHIBITED_EXPRESSION", "UNCERTAINTY_DISCLOSURE"],
                           "allowed_negated_prohibited_expression")
        if "예시를 설명" in text and "보장하지 않습니다" in text:
            return _result(ALLOW, ["meta_explanation", "negated_prohibited_expression"], "pass",
                           ["META_EXPLANATION", "NEGATED_PROHIBITED_EXPRESSION"],
                           "allowed_meta_explanation")
        return _result(ALLOW, ["cautious_language"], "pass", ["CAUTIOUS_LANGUAGE"], "allowed_cautious_language")

    if text_role == "reason":
        if "법적 효력이 없습니다" in text:
            return _result(BLOCK, ["legal_certainty"], "block_result", ["LEGAL_CERTAINTY"],
                           "blocked_legal_certainty")
        if "보증금은 반드시" in text:
            return _result(BLOCK, ["refund_guarantee", "outcome_guarantee"], "block_result",
                           ["REFUND_GUARANTEE", "OUTCOME_GUARANTEE"], "blocked_refund_guarantee")
        if "손해배상" in text:
            return _result(BLOCK, ["outcome_guarantee"], "block_result", ["OUTCOME_GUARANTEE"],
                           "blocked_outcome_guarantee")
        if "법적으로 안전합니다" in text:
            return _result(BLOCK, ["legal_safety_guarantee"], "block_result", ["LEGAL_SAFETY_GUARANTEE"],
                           "blocked_legal_safety_guarantee")
        if "source_quote" in text:
            return _result(ALLOW, ["meta_explanation"], "pass", ["META_EXPLANATION"],
                           "allowed_meta_explanation")
        if "인용과 판단" in text:
            return _result(ALLOW, ["mixed_context"], "pass", ["MIXED_CONTEXT"], "allowed_mixed_context")
        if "어렵" in text:
            return _result(ALLOW, ["cautious_language", "uncertainty_disclosure"], "pass",
                           ["CAUTIOUS_LANGUAGE", "UNCERTAINTY_DISCLOSURE"], "allowed_uncertainty_disclosure")
        return _result(ALLOW, ["cautious_language"], "pass", ["CAUTIOUS_LANGUAGE"], "allowed_cautious_language")

    if text_role == "recommended_action":
        if "즉시 계약을 해지" in text or "바로 소송" in text or "지급을 거부" in text:
            return _result(BLOCK, ["direct_legal_action_instruction"], "block_result",
                           ["DIRECT_LEGAL_ACTION"], "blocked_direct_action")
        if "확인하지 않아도" in text or "확인이 필요 없" in text or "확인할 필요는 없" in text:
            return _result(BLOCK, ["expert_review_dismissal"], "block_result", ["EXPERT_REVIEW_DISMISSAL"],
                           "blocked_expert_review_dismissal")
        return _result(ALLOW, ["cautious_language"], "pass", ["CAUTIOUS_LANGUAGE"], "allowed_cautious_language")

    raise ValueError(f"unsupported text role: {text_role}")


def _result(classification: str, categories: list[str], action: str, matched_rules: list[str], reason_code: str) -> dict[str, Any]:
    return {
        "classification": classification,
        "categories": categories,
        "action": action,
        "matched_rules": matched_rules,
        "reason_code": reason_code,
    }


def summarize(field_results: list[dict[str, Any]]) -> dict[str, Any]:
    violation_count = sum(1 for item in field_results if item["classification"] == BLOCK)
    review_count = sum(1 for item in field_results if item["classification"] == REVIEW)
    allowed_count = sum(1 for item in field_results if item["classification"] == ALLOW)
    if violation_count:
        overall_status = BLOCK
    elif review_count:
        overall_status = REVIEW
    else:
        overall_status = ALLOW
    return {
        "overall_status": overall_status,
        "manual_review_required": review_count > 0,
        "evaluated_field_count": len(field_results),
        "allowed_count": allowed_count,
        "violation_count": violation_count,
        "review_count": review_count,
    }


def check_output(data: dict[str, Any]) -> dict[str, Any]:
    test_case_id = data.get("test_case_id")
    if not isinstance(test_case_id, str):
        raise ValueError("test_case_id must be a string")
    field_results: list[dict[str, Any]] = []
    for field_path, text_role, text in iter_user_visible_text_fields(data):
        classification = classify_field(text_role, text)
        field_results.append(
            {
                "field_path": field_path,
                "text_role": text_role,
                **classification,
            }
        )
    return {
        "schema_version": "0.1",
        "test_case_id": test_case_id,
        **summarize(field_results),
        "field_results": field_results,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check user-visible output safety for a synthetic analysis JSON.")
    parser.add_argument("--input", required=True, help="Input synthetic analysis JSON")
    parser.add_argument("--output", help="Optional output JSON path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        args = parse_args(argv or sys.argv[1:])
        data = read_json(Path(args.input))
        result = check_output(data)
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        return 0
    except Exception as exc:
        print(f"output safety check error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
