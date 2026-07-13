"""Compare masked synthetic contract usefulness against frozen expectations.

This PR-4 helper reuses the PR-2 clause splitter and PR-3 masking code. It
keeps source and masked contract text out of the returned result object.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SPIKE_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[4]
SPLITTER_PATH = SPIKE_ROOT / "scripts" / "clause_split" / "split_clauses.py"
DETECTOR_PATH = SPIKE_ROOT / "scripts" / "pii_masking" / "detect_and_mask.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SPLITTER = _load_module("pr2_split_clauses", SPLITTER_PATH)
DETECTOR = _load_module("pr3_detect_and_mask", DETECTOR_PATH)


def read_fixture(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path.name}: UTF-8 BOM is not allowed")
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name}: input is not valid UTF-8: {exc.reason}") from exc


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_policy(text: str, allow_linebreak_shift: bool = True) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    if allow_linebreak_shift:
        normalized = normalized.replace("\n", " ")
    return re.sub(r"[ \f\v]+", " ", normalized).strip()


def _segments_match(left: str, right: str) -> bool:
    return normalize_for_policy(left) == normalize_for_policy(right)


def _clause_text(clause: dict[str, Any]) -> str:
    parts = [
        clause.get("marker") or "",
        clause.get("raw_heading") or "",
        clause.get("body") or "",
    ]
    return "\n".join(part for part in parts if part)


def _expected_clause_markers(split_result: dict[str, Any]) -> list[str]:
    return [clause["marker"] for clause in split_result.get("clauses", [])]


def _matching_clause(split_result: dict[str, Any], marker: str) -> dict[str, Any] | None:
    for clause in split_result.get("clauses", []):
        if clause.get("marker") == marker:
            return clause
    return None


def _clauses_containing_any(split_result: dict[str, Any], patterns: list[str]) -> set[int]:
    matches: set[int] = set()
    for clause in split_result.get("clauses", []):
        clause_text = _clause_text(clause)
        if any(pattern in clause_text for pattern in patterns):
            matches.add(int(clause["ordinal"]))
    return matches


def _patterns_present(
    patterns: list[str],
    target: str,
    verification_mode: str,
) -> tuple[bool, int]:
    if verification_mode == "exact_presence":
        missing = sum(1 for pattern in patterns if pattern not in target)
        return missing == 0, missing

    normalized_target = normalize_for_policy(target)
    missing = sum(
        1
        for pattern in patterns
        if normalize_for_policy(pattern) not in normalized_target
    )
    return missing == 0, missing


def _context_target(
    context: dict[str, Any],
    masked_text: str,
    masked_split: dict[str, Any],
) -> tuple[str, bool]:
    scope = context.get("scope", {})
    scope_type = scope.get("type")
    if scope_type == "document":
        observations = list(masked_split.get("document_warnings", []))
        if "no_clause_marker_detected" in observations:
            observations.append("\uc870\ud56d \ub9c8\ucee4 \uc5c6\uc74c")
        return "\n".join([masked_text, *observations]), True
    if scope_type == "clause":
        marker = scope.get("clause_identifier")
        if not isinstance(marker, str):
            return "", False
        clause = _matching_clause(masked_split, marker)
        if clause is None:
            return "", False
        return _clause_text(clause), True
    return "", False


def _evaluate_required_contexts(
    contexts: list[dict[str, Any]],
    masked_text: str,
    masked_split: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for context in contexts:
        target, scope_found = _context_target(context, masked_text, masked_split)
        patterns = context.get("required_patterns", [])
        mode = context.get("verification_mode", "normalized_presence")
        present, missing_count = _patterns_present(patterns, target, mode) if scope_found else (False, len(patterns))
        results.append(
            {
                "context_id": context["context_id"],
                "scope_type": context.get("scope", {}).get("type"),
                "scope_found": scope_found,
                "require_all_in_same_scope": bool(context.get("require_all_in_same_scope")),
                "verification_mode": mode,
                "automatic_status": "PASS" if present else "FAIL",
                "missing_patterns_count": missing_count,
                "manual_review_required": mode == "pattern_presence_plus_manual_review",
            }
        )
    return results


def _evaluate_party_roles(
    expectations: list[dict[str, Any]],
    masked_text: str,
    masked_split: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for expectation in expectations:
        indicators = expectation.get("role_indicators", [])
        token_patterns = expectation.get("expected_token_patterns", [])
        indicator_present, missing_indicators = _patterns_present(
            indicators,
            masked_text,
            expectation.get("verification_mode", "normalized_presence"),
        )
        token_present, missing_tokens = _patterns_present(
            token_patterns,
            masked_text,
            expectation.get("verification_mode", "normalized_presence"),
        )
        indicator_clauses = _clauses_containing_any(masked_split, indicators)
        token_clauses = _clauses_containing_any(masked_split, token_patterns)

        fallback_used = False
        if token_patterns:
            linked = bool(indicator_clauses.intersection(token_clauses))
            if linked:
                context_link_status = "linked"
            elif indicator_present and token_present:
                context_link_status = "fallback_document"
                fallback_used = True
            else:
                context_link_status = "missing"
        else:
            linked = indicator_present
            context_link_status = "indicator_only" if indicator_present else "missing"

        passed = indicator_present and token_present and (linked or fallback_used)
        results.append(
            {
                "role": expectation["role"],
                "expected_token_type": expectation.get("expected_token_type"),
                "automatic_status": "PASS" if passed else "FAIL",
                "context_link_status": context_link_status,
                "fallback_used": fallback_used,
                "missing_role_indicators_count": missing_indicators,
                "missing_token_patterns_count": missing_tokens,
                "manual_review_required": True,
            }
        )
    return results


def _independent_non_pii_preservation(
    source_text: str,
    masked_text: str,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    sorted_entities = sorted(entities, key=lambda item: (item["start_offset"], item["end_offset"]))
    invalid_span_count = 0
    overlap_count = 0
    missing_token_count = 0
    non_pii_segment_mismatch_count = 0
    source_cursor = 0
    masked_cursor = 0
    previous_end = 0

    for entity in sorted_entities:
        start = entity.get("start_offset")
        end = entity.get("end_offset")
        token = entity.get("mask_token")
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(token, str):
            invalid_span_count += 1
            continue
        if not (0 <= start < end <= len(source_text)):
            invalid_span_count += 1
            continue
        if start < previous_end:
            overlap_count += 1
            continue

        source_segment = source_text[source_cursor:start]
        expected_token_index = masked_cursor + len(source_segment)
        if masked_text.startswith(token, expected_token_index):
            token_index = expected_token_index
        else:
            token_index = -1
            search_from = masked_cursor
            while True:
                candidate = masked_text.find(token, search_from)
                if candidate < 0:
                    break
                if _segments_match(source_segment, masked_text[masked_cursor:candidate]):
                    token_index = candidate
                    break
                search_from = candidate + len(token)
        if token_index < 0:
            missing_token_count += 1
            break

        masked_segment = masked_text[masked_cursor:token_index]
        if not _segments_match(source_segment, masked_segment):
            non_pii_segment_mismatch_count += 1

        source_cursor = end
        masked_cursor = token_index + len(token)
        previous_end = end

    suffix_preserved = _segments_match(source_text[source_cursor:], masked_text[masked_cursor:])
    normalized_comparison_passed = (
        invalid_span_count == 0
        and overlap_count == 0
        and missing_token_count == 0
        and non_pii_segment_mismatch_count == 0
        and suffix_preserved
    )
    return {
        "passed": normalized_comparison_passed,
        "entity_count": len(entities),
        "invalid_span_count": invalid_span_count,
        "overlap_count": overlap_count,
        "missing_token_count": missing_token_count,
        "non_pii_segment_mismatch_count": non_pii_segment_mismatch_count,
        "suffix_preserved": suffix_preserved,
        "normalized_comparison_passed": normalized_comparison_passed,
    }


def _repeated_token_consistency(entities: list[dict[str, Any]]) -> dict[str, Any]:
    by_type_and_hash: dict[tuple[str, str], set[str]] = {}
    by_type_token_to_hash: dict[tuple[str, str], set[str]] = {}
    for entity in entities:
        source_hash = entity.get("source_hash")
        entity_type = entity.get("entity_type")
        mask_token = entity.get("mask_token")
        if not isinstance(source_hash, str) or not isinstance(entity_type, str) or not isinstance(mask_token, str):
            continue
        by_type_and_hash.setdefault((entity_type, source_hash), set()).add(mask_token)
        by_type_token_to_hash.setdefault((entity_type, mask_token), set()).add(source_hash)

    same_value_conflicts = sum(1 for tokens in by_type_and_hash.values() if len(tokens) > 1)
    distinct_value_conflicts = sum(1 for hashes in by_type_token_to_hash.values() if len(hashes) > 1)
    return {
        "passed": same_value_conflicts == 0 and distinct_value_conflicts == 0,
        "same_value_conflicts": same_value_conflicts,
        "distinct_value_conflicts": distinct_value_conflicts,
    }


def compare_case(case: dict[str, Any]) -> dict[str, Any]:
    source_path = REPO_ROOT / case["source_fixture"]
    source_text = read_fixture(source_path)
    normalized_source = DETECTOR.normalize_text(source_text)
    avoid_token_collisions = "preexisting_token_collision_avoided" in case.get("expected", {})
    masked_result = DETECTOR.detect_and_mask(
        normalized_source,
        avoid_preexisting_token_collisions=avoid_token_collisions,
    )
    masked_text = masked_result["masked_text"]

    source_split = SPLITTER.split_text(normalized_source, case["test_case_id"], "fixture")
    masked_split = SPLITTER.split_text(masked_text, case["test_case_id"], "fixture")
    expected_markers = case["clause_expectation"]["expected_identifiers"]
    actual_markers = _expected_clause_markers(masked_split)
    source_markers = _expected_clause_markers(source_split)

    expected_count = case["clause_expectation"]["expected_count"]
    source_clause_count = len(source_split.get("clauses", []))
    masked_clause_count = len(masked_split.get("clauses", []))
    source_no_clause_warning = "no_clause_marker_detected" in source_split.get("document_warnings", [])
    masked_no_clause_warning = "no_clause_marker_detected" in masked_split.get("document_warnings", [])
    no_clause_expected = bool(case["clause_expectation"]["no_clause_marker_expected"])

    non_pii_result = _independent_non_pii_preservation(
        normalized_source,
        masked_text,
        masked_result["entities"],
    )

    contract_applicable = case.get("contract_type_check", {}).get("applicable", True)
    if contract_applicable is False or case["expected"].get("contract_type_preserved") is None:
        contract_type_preserved: bool | None = None
        contract_type_status = "N/A"
        missing_contract_patterns = 0
    else:
        contract_type_preserved, missing_contract_patterns = _patterns_present(
            case.get("contract_type_patterns", []),
            masked_text,
            "normalized_presence",
        )
        contract_type_status = "PASS" if contract_type_preserved else "FAIL"

    required_context_results = _evaluate_required_contexts(
        case.get("required_context", []),
        masked_text,
        masked_split,
    )
    party_role_results = _evaluate_party_roles(
        case.get("party_role_expectations", []),
        masked_text,
        masked_split,
    )
    repeated = _repeated_token_consistency(masked_result["entities"])
    residual_count = len(DETECTOR.detect_entities(masked_text))
    collision_metadata = {
        "preexisting_token_count": masked_result.get("preexisting_token_count", 0),
        "preexisting_token_collision_avoided": bool(masked_result.get("token_collision_avoided", True)),
        "reserved_token_types": sorted(masked_result.get("highest_preexisting_ordinal_by_type", {}).keys()),
        "collision_count": int(masked_result.get("reused_reserved_ordinal_count", 0))
        + int(masked_result.get("preexisting_token_preservation_failures", 0)),
        "reused_reserved_ordinal_count": int(masked_result.get("reused_reserved_ordinal_count", 0)),
        "preexisting_token_preservation_failures": int(
            masked_result.get("preexisting_token_preservation_failures", 0)
        ),
    }

    clause_count_preserved = source_clause_count == expected_count == masked_clause_count
    if no_clause_expected:
        clause_count_preserved = (
            clause_count_preserved
            and source_clause_count == 0
            and masked_clause_count == 0
            and source_no_clause_warning
            and masked_no_clause_warning
        )
    clause_order_preserved = (
        source_markers == expected_markers
        and actual_markers == expected_markers
        and source_markers == actual_markers
    )

    return {
        "test_case_id": case["test_case_id"],
        "source_fixture": case["source_fixture"],
        "source_text_sha256": sha256_text(normalized_source),
        "masked_text_sha256": sha256_text(masked_text),
        "clause_count_preserved": clause_count_preserved,
        "expected_clause_count": expected_count,
        "actual_clause_count": masked_clause_count,
        "source_clause_count": source_clause_count,
        "source_no_clause_marker_detected": source_no_clause_warning,
        "masked_no_clause_marker_detected": masked_no_clause_warning,
        "clause_order_preserved": clause_order_preserved,
        "clause_identity_preserved": clause_order_preserved,
        "non_pii_text_preserved": non_pii_result["passed"],
        "non_pii_comparison": non_pii_result,
        "contract_type_preserved": contract_type_preserved,
        "contract_type_status": contract_type_status,
        "missing_contract_patterns_count": missing_contract_patterns,
        "repeated_token_consistency": repeated["passed"],
        "repeated_token_conflicts": {
            "same_value_conflicts": repeated["same_value_conflicts"],
            "distinct_value_conflicts": repeated["distinct_value_conflicts"],
        },
        "preexisting_token_collision": collision_metadata,
        "required_context_results": required_context_results,
        "party_role_prescreen": party_role_results,
        "residual_detector_matches": residual_count,
        "manual_review_required": bool(case.get("manual_review", {}).get("required")),
    }
