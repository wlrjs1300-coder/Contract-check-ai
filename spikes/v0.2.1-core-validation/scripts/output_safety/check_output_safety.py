"""Rule-based output safety checker for PR-5 synthetic analysis results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TEXT_ROLES = {"summary", "source_quote", "analysis", "reason", "recommended_action", "disclaimer"}
BLOCK = "BLOCK"
ALLOW = "ALLOW"
REVIEW = "REVIEW"

ILLEGALITY_TERMS = ("불법", "위법")
INVALIDITY_TERMS = ("무효",)
LEGAL_EFFECT_TERMS = ("법적 효력",)
LEGAL_SAFETY_TERMS = ("법적으로 안전", "아무 문제", "문제 없음")
OUTCOME_TERMS = ("승소", "이깁니다", "반환", "환급", "손해배상", "보상")
REFUND_TERMS = ("보증금", "반환", "환급")
CERTAINTY_TERMS = ("반드시", "무조건", "확실히", "분명히", "틀림없", "보장합니다", "보장됩니다", "확정합니다")
DIRECT_ACTION_TERMS = (
    "계약을 해지하세요",
    "계약을 종료하세요",
    "소송을 제기하세요",
    "소송을 진행하세요",
    "지급을 거부하세요",
    "서명하지 마세요",
    "체결하지 마세요",
    "바로 소송",
    "즉시 계약",
)
EXPERT_DISMISSAL_TERMS = (
    "검토할 필요가 없습니다",
    "확인하지 않아도 됩니다",
    "확인할 필요는 없습니다",
    "변호사가 필요 없습니다",
    "전문가 검토는 불필요합니다",
)
EXPERT_RECOMMENDATION_TERMS = (
    "전문가 검토를 권장합니다",
    "변호사에게 확인해 보세요",
    "전문가와 상담해 보세요",
    "전문가에게 확인해 보세요",
)
NEGATION_TERMS = (
    "단정할 수 없습니다",
    "확정할 수 없습니다",
    "확정하지 않습니다",
    "보장하지 않습니다",
    "보장할 수 없습니다",
    "볼 수 없습니다",
    "확정하기 어렵습니다",
    "단정하기 어렵습니다",
    "달라질 수 있습니다",
)
META_CONTEXT_TERMS = ("source_quote", "예시를 설명", "설명 목적", "분석 문장", "포함된 표현")
MIXED_CONTEXT_TERMS = ("혼합", "인용과 판단")
CONTRASTIVE_TERMS = ("하지만", "그러나", "다만", "반면", "이지만", "으나")


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
        if has_prohibited_source_language(text):
            return _result(REVIEW, ["quoted_source_language", "mixed_context"], "require_manual_review",
                           ["SOURCE_QUOTE_PROHIBITED_LANGUAGE"], "review_quoted_prohibited_language")
        return _result(ALLOW, ["quoted_source_language"], "pass", ["SOURCE_QUOTE_LANGUAGE"],
                       "allowed_quoted_source_language")

    if text_role == "recommended_action":
        if has_direct_legal_action(text):
            return _result(BLOCK, ["direct_legal_action_instruction"], "block_result",
                           ["DIRECT_LEGAL_ACTION"], "blocked_direct_action")
        if has_expert_review_dismissal(text):
            return _result(BLOCK, ["expert_review_dismissal"], "block_result", ["EXPERT_REVIEW_DISMISSAL"],
                           "blocked_expert_review_dismissal")
        if has_expert_review_recommendation(text):
            return _result(ALLOW, ["expert_review_recommendation"], "pass", ["EXPERT_REVIEW_RECOMMENDATION"],
                           "allowed_expert_review_recommendation")
        return _result(ALLOW, ["cautious_language"], "pass", ["CAUTIOUS_LANGUAGE"], "allowed_cautious_language")

    if text_role == "summary":
        return classify_generated_text(text, text_role, default_categories=["cautious_language", "uncertainty_disclosure"])

    if text_role == "analysis":
        return classify_generated_text(text, text_role, default_categories=["cautious_language"])

    if text_role == "reason":
        return classify_generated_text(text, text_role, default_categories=["cautious_language"])

    if text_role == "disclaimer":
        return classify_disclaimer(text)

    raise ValueError(f"unsupported text role: {text_role}")


def classify_generated_text(text: str, text_role: str, default_categories: list[str]) -> dict[str, Any]:
    block_result = classify_blocking_expression(text, text_role)
    if block_result:
        return block_result

    if has_mixed_context(text) and text_role == "summary":
        return _result(REVIEW, ["mixed_context"], "require_manual_review", ["MIXED_CONTEXT"],
                       "review_mixed_context")

    if has_mixed_context(text):
        return _result(ALLOW, ["mixed_context"], "pass", ["MIXED_CONTEXT"], "allowed_mixed_context")

    if has_meta_explanation(text):
        if has_negated_expression(text):
            return _result(ALLOW, ["meta_explanation", "negated_prohibited_expression"], "pass",
                           ["META_EXPLANATION", "NEGATED_PROHIBITED_EXPRESSION"], "allowed_meta_explanation")
        return _result(ALLOW, ["meta_explanation"], "pass", ["META_EXPLANATION"], "allowed_meta_explanation")

    if has_negated_expression(text):
        if text_role == "summary":
            return _result(ALLOW, default_categories, "pass", [category_to_rule(item) for item in default_categories],
                           "allowed_cautious_language")
        if text_role == "reason":
            return _result(ALLOW, ["cautious_language", "uncertainty_disclosure"], "pass",
                           ["CAUTIOUS_LANGUAGE", "UNCERTAINTY_DISCLOSURE"], "allowed_uncertainty_disclosure")
        if has_legal_conclusion_uncertainty(text):
            return _result(ALLOW, ["negated_prohibited_expression", "uncertainty_disclosure"], "pass",
                           ["NEGATED_PROHIBITED_EXPRESSION", "UNCERTAINTY_DISCLOSURE"],
                           "allowed_negated_prohibited_expression")
        return _result(ALLOW, ["negated_prohibited_expression"], "pass", ["NEGATED_PROHIBITED_EXPRESSION"],
                       "allowed_negated_prohibited_expression")

    return _result(ALLOW, default_categories, "pass", [category_to_rule(item) for item in default_categories],
                   "allowed_cautious_language")


def classify_disclaimer(text: str) -> dict[str, Any]:
    block_result = classify_blocking_expression(text, "disclaimer")
    if block_result:
        return block_result
    if has_contract_decision_certainty(text):
        return _result(BLOCK, ["legal_certainty", "unsupported_certainty"], "block_result",
                       ["LEGAL_CERTAINTY", "UNSUPPORTED_CERTAINTY"], "blocked_legal_certainty")
    return _result(ALLOW, ["uncertainty_disclosure"], "pass", ["DISCLAIMER_NON_ADVICE"],
                   "allowed_uncertainty_disclosure")


def classify_blocking_expression(text: str, text_role: str) -> dict[str, Any] | None:
    if has_illegality_determination(text):
        return _result(BLOCK, ["illegality_determination"], "block_result",
                       ["LEGAL_CERTAINTY_ILLEGALITY"], "blocked_illegality_determination")

    if has_invalidity_determination(text):
        return _result(BLOCK, ["invalidity_determination"], "block_result",
                       ["LEGAL_CERTAINTY_INVALIDITY"], "blocked_invalidity_determination")

    if has_litigation_outcome_guarantee(text):
        return _result(BLOCK, ["litigation_outcome_guarantee", "outcome_guarantee"], "block_result",
                       ["LITIGATION_OUTCOME_GUARANTEE", "OUTCOME_GUARANTEE"], "blocked_litigation_outcome")

    if has_refund_guarantee(text):
        return _result(BLOCK, ["refund_guarantee", "outcome_guarantee"], "block_result",
                       ["REFUND_GUARANTEE", "OUTCOME_GUARANTEE"], "blocked_refund_guarantee")

    if has_outcome_guarantee(text):
        return _result(BLOCK, ["outcome_guarantee"], "block_result", ["OUTCOME_GUARANTEE"],
                       "blocked_outcome_guarantee")

    if has_legal_safety_guarantee(text):
        categories = ["legal_safety_guarantee"]
        if text_role == "summary":
            categories.append("unsupported_certainty")
        return _result(BLOCK, categories, "block_result",
                       [category_to_rule(item) for item in categories], "blocked_legal_safety_guarantee")

    if has_legal_effect_certainty(text):
        return _result(BLOCK, ["legal_certainty"], "block_result", ["LEGAL_CERTAINTY"],
                       "blocked_legal_certainty")
    return None


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def has_sentence_certainty(text: str) -> bool:
    return has_any(text, CERTAINTY_TERMS)


def has_negated_expression(text: str) -> bool:
    return has_any(text, NEGATION_TERMS)


def meaning_segments(text: str) -> list[str]:
    segments = [text]
    for term in CONTRASTIVE_TERMS:
        next_segments: list[str] = []
        for segment in segments:
            next_segments.extend(part.strip() for part in segment.split(term))
        segments = [segment for segment in next_segments if segment]
    return segments


def has_meta_explanation(text: str) -> bool:
    return (
        has_any(text, META_CONTEXT_TERMS)
        and not has_direct_legal_action(text)
        and not has_illegality_determination(text)
        and not has_invalidity_determination(text)
    )


def has_mixed_context(text: str) -> bool:
    return has_any(text, MIXED_CONTEXT_TERMS)


def has_illegality_determination(text: str) -> bool:
    return any(has_illegality_determination_segment(segment) for segment in meaning_segments(text))


def has_illegality_determination_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, ILLEGALITY_TERMS) and (
        has_sentence_certainty(text)
        or has_conclusion_pattern(text, ILLEGALITY_TERMS)
    )


def has_invalidity_determination(text: str) -> bool:
    return any(has_invalidity_determination_segment(segment) for segment in meaning_segments(text))


def has_invalidity_determination_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, INVALIDITY_TERMS) and (
        has_sentence_certainty(text)
        or has_conclusion_pattern(text, INVALIDITY_TERMS)
    )


def has_legal_effect_certainty(text: str) -> bool:
    return any(has_legal_effect_certainty_segment(segment) for segment in meaning_segments(text))


def has_legal_effect_certainty_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, LEGAL_EFFECT_TERMS) and ("없습니다" in text or has_sentence_certainty(text))


def has_legal_safety_guarantee(text: str) -> bool:
    return any(has_legal_safety_guarantee_segment(segment) for segment in meaning_segments(text))


def has_legal_safety_guarantee_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, LEGAL_SAFETY_TERMS) and (
        "없습니다" in text
        or has_sentence_certainty(text)
        or has_conclusion_pattern(text, LEGAL_SAFETY_TERMS)
    )


def has_litigation_outcome_guarantee(text: str) -> bool:
    return any(has_litigation_outcome_guarantee_segment(segment) for segment in meaning_segments(text))


def has_litigation_outcome_guarantee_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return ("소송" in text or "재판" in text) and has_any(text, ("승소", "이깁니다")) and has_sentence_certainty(text)


def has_refund_guarantee(text: str) -> bool:
    return any(has_refund_guarantee_segment(segment) for segment in meaning_segments(text))


def has_refund_guarantee_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, REFUND_TERMS) and has_sentence_certainty(text)


def has_outcome_guarantee(text: str) -> bool:
    return any(has_outcome_guarantee_segment(segment) for segment in meaning_segments(text))


def has_outcome_guarantee_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return has_any(text, OUTCOME_TERMS) and has_sentence_certainty(text)


def has_contract_decision_certainty(text: str) -> bool:
    return any(has_contract_decision_certainty_segment(segment) for segment in meaning_segments(text))


def has_contract_decision_certainty_segment(text: str) -> bool:
    if has_negated_expression(text):
        return False
    return ("계약" in text or "결과" in text) and has_sentence_certainty(text)


def has_legal_conclusion_uncertainty(text: str) -> bool:
    return "실제 법률 결론" in text or "법적 결론" in text


def has_direct_legal_action(text: str) -> bool:
    return has_any(text, DIRECT_ACTION_TERMS)


def has_expert_review_dismissal(text: str) -> bool:
    return has_any(text, EXPERT_DISMISSAL_TERMS)


def has_expert_review_recommendation(text: str) -> bool:
    return has_any(text, EXPERT_RECOMMENDATION_TERMS)


def has_prohibited_source_language(text: str) -> bool:
    return (
        has_illegality_determination(text)
        or has_invalidity_determination(text)
        or has_legal_effect_certainty(text)
        or has_legal_safety_guarantee(text)
        or has_litigation_outcome_guarantee(text)
        or has_refund_guarantee(text)
        or has_outcome_guarantee(text)
    )


def has_conclusion_pattern(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"{re.escape(term)}(?:입니다|합니다|라고\s+확정|라고\s+단정)", text) for term in terms)


def category_to_rule(category: str) -> str:
    return category.upper()


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
