"""Deterministic PII detection and masking spike.

This script is intentionally limited to the frozen synthetic fixtures for the
v0.2.1 PR-3 experiment. It does not use external services or third-party
packages, and it never stores detected raw values in the output object.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MASK_PREFIXES = {
    "person": "PERSON",
    "phone": "PHONE",
    "email": "EMAIL",
    "address": "ADDRESS",
    "date_of_birth": "BIRTH",
    "national_id_number": "RRN",
    "business_registration_number": "BIZ_NO",
    "account_number": "ACCOUNT",
}

PERSON_LABELS = (
    "성명:",
    "이름:",
    "근로자:",
    "사용자:",
    "대표자:",
    "임대인:",
    "임차인:",
)
ADDRESS_LABELS = (
    "사업장 주소:",
    "근무지 주소:",
    "주소:",
    "소재지:",
    "거주지:",
)
DATE_OF_BIRTH_LABELS = ("생년월일:", "생일:")
ACCOUNT_LABELS = ("계좌번호:", "계좌:")

VALUE_BOUNDARY_LABELS = tuple(
    sorted(
        set(
            PERSON_LABELS
            + ADDRESS_LABELS
            + DATE_OF_BIRTH_LABELS
            + ACCOUNT_LABELS
            + (
                "전화번호:",
                "이메일:",
                "주민등록번호:",
                "외국인등록번호:",
                "사업자등록번호:",
                "회사:",
            )
        ),
        key=len,
        reverse=True,
    )
)

PHONE_RE = re.compile(r"010-\d{4}-\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NATIONAL_ID_RE = re.compile(r"\d{6}-\d{7}")
BUSINESS_NUMBER_RE = re.compile(r"\d{3}-\d{2}-\d{5}")
ACCOUNT_NUMBER_RE = re.compile(r"\d{3}-\d{4}-\d{4}")
MASK_TOKEN_RE = re.compile(r"^\[[A-Z_]+_\d+\]$")
MASK_TOKEN_SPAN_RE = re.compile(r"\[([A-Z_]+)_(\d+)\]")
ENTITY_TYPE_BY_PREFIX = {prefix: entity_type for entity_type, prefix in MASK_PREFIXES.items()}


@dataclass(order=True)
class Candidate:
    start_offset: int
    end_offset: int
    entity_type: str
    source_line_start: int
    source_line_end: int
    detection_order: int = field(compare=False, default=0)


def normalize_text(text: str) -> str:
    """Normalize source text according to the frozen expected convention."""
    if text.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is not allowed")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _line_spans(text: str) -> list[tuple[int, int, int, str]]:
    spans: list[tuple[int, int, int, str]] = []
    offset = 0
    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        line_body = line[:-1] if line.endswith("\n") else line
        spans.append((line_number, offset, offset + len(line_body), line_body))
        offset += len(line)
    if text == "":
        spans.append((1, 0, 0, ""))
    return spans


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _source_hash(text: str, start: int, end: int) -> str:
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()[:12]


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _value_end_before_next_label(line: str, value_start_in_line: int) -> int:
    end = len(line)
    for label in VALUE_BOUNDARY_LABELS:
        pos = line.find(label, value_start_in_line)
        if pos != -1:
            end = min(end, pos)
    return end


def _labeled_value_candidates(
    text: str,
    labels: tuple[str, ...],
    entity_type: str,
    order_start: int,
    value_regex: re.Pattern[str] | None = None,
) -> tuple[list[Candidate], int]:
    candidates: list[Candidate] = []
    order = order_start
    for line_number, line_start, _line_end, line in _line_spans(text):
        for label in sorted(labels, key=len, reverse=True):
            search_from = 0
            while True:
                label_pos = line.find(label, search_from)
                if label_pos == -1:
                    break
                value_start = label_pos + len(label)
                value_end = _value_end_before_next_label(line, value_start)
                absolute_start = line_start + value_start
                absolute_end = line_start + value_end
                absolute_start, absolute_end = _trim_span(text, absolute_start, absolute_end)
                if value_regex is not None:
                    value = text[absolute_start:absolute_end]
                    match = value_regex.search(value)
                    if match:
                        absolute_start += match.start()
                        absolute_end = absolute_start + len(match.group(0))
                    else:
                        search_from = value_start
                        continue
                elif MASK_TOKEN_RE.fullmatch(text[absolute_start:absolute_end]):
                    search_from = value_start
                    continue
                if absolute_start < absolute_end:
                    candidates.append(
                        Candidate(
                            start_offset=absolute_start,
                            end_offset=absolute_end,
                            entity_type=entity_type,
                            source_line_start=line_number,
                            source_line_end=line_number,
                            detection_order=order,
                        )
                    )
                    order += 1
                search_from = value_start
    return candidates, order


def _regex_candidates(
    text: str,
    pattern: re.Pattern[str],
    entity_type: str,
    order_start: int,
) -> tuple[list[Candidate], int]:
    candidates: list[Candidate] = []
    order = order_start
    for match in pattern.finditer(text):
        start, end = match.span()
        candidates.append(
            Candidate(
                start_offset=start,
                end_offset=end,
                entity_type=entity_type,
                source_line_start=_line_for_offset(text, start),
                source_line_end=_line_for_offset(text, end - 1),
                detection_order=order,
            )
        )
        order += 1
    return candidates, order


def _overlaps(a: Candidate, b: Candidate) -> bool:
    return max(a.start_offset, b.start_offset) < min(a.end_offset, b.end_offset)


def find_preexisting_mask_tokens(text: str) -> list[dict[str, Any]]:
    """Find already-masked token spans without treating them as PII entities."""
    normalized = normalize_text(text)
    tokens: list[dict[str, Any]] = []
    for match in MASK_TOKEN_SPAN_RE.finditer(normalized):
        prefix, ordinal_text = match.groups()
        entity_type = ENTITY_TYPE_BY_PREFIX.get(prefix)
        if entity_type is None:
            continue
        ordinal = int(ordinal_text)
        if ordinal <= 0:
            continue
        start, end = match.span()
        tokens.append(
            {
                "entity_type": entity_type,
                "ordinal": ordinal,
                "start_offset": start,
                "end_offset": end,
                "token": match.group(0),
            }
        )
    return tokens


def _overlaps_span(candidate: Candidate, span: dict[str, Any]) -> bool:
    return max(candidate.start_offset, span["start_offset"]) < min(candidate.end_offset, span["end_offset"])


def _deduplicate_and_resolve(
    candidates: list[Candidate],
    protected_spans: list[dict[str, Any]] | None = None,
) -> list[Candidate]:
    priority = {
        "person": 10,
        "address": 10,
        "date_of_birth": 10,
        "account_number": 10,
        "business_registration_number": 9,
        "national_id_number": 8,
        "phone": 7,
        "email": 7,
    }
    selected: list[Candidate] = []
    protected = protected_spans or []
    for candidate in sorted(
        candidates,
        key=lambda c: (
            c.start_offset,
            -(c.end_offset - c.start_offset),
            -priority.get(c.entity_type, 0),
            c.detection_order,
        ),
    ):
        if any(_overlaps_span(candidate, span) for span in protected):
            continue
        duplicate = any(
            candidate.start_offset == existing.start_offset
            and candidate.end_offset == existing.end_offset
            and candidate.entity_type == existing.entity_type
            for existing in selected
        )
        if duplicate:
            continue
        if any(_overlaps(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda c: c.start_offset)


def _dense_cluster_lines(candidates: list[Candidate]) -> set[int]:
    line_counts: dict[int, int] = {}
    for candidate in candidates:
        line_counts[candidate.source_line_start] = line_counts.get(candidate.source_line_start, 0) + 1
    return {line for line, count in line_counts.items() if count >= 3}


def detect_entities(
    text: str,
    avoid_preexisting_token_collisions: bool = False,
) -> list[dict[str, Any]]:
    """Detect supported synthetic PII entities without returning raw values."""
    normalized = normalize_text(text)
    preexisting_tokens = find_preexisting_mask_tokens(normalized) if avoid_preexisting_token_collisions else []
    candidates: list[Candidate] = []
    order = 0

    for labels, entity_type, regex in (
        (PERSON_LABELS, "person", None),
        (ADDRESS_LABELS, "address", None),
        (DATE_OF_BIRTH_LABELS, "date_of_birth", None),
        (ACCOUNT_LABELS, "account_number", ACCOUNT_NUMBER_RE),
    ):
        new_candidates, order = _labeled_value_candidates(normalized, labels, entity_type, order, regex)
        candidates.extend(new_candidates)

    for pattern, entity_type in (
        (BUSINESS_NUMBER_RE, "business_registration_number"),
        (NATIONAL_ID_RE, "national_id_number"),
        (PHONE_RE, "phone"),
        (EMAIL_RE, "email"),
    ):
        new_candidates, order = _regex_candidates(normalized, pattern, entity_type, order)
        candidates.extend(new_candidates)

    resolved = _deduplicate_and_resolve(candidates, preexisting_tokens)
    dense_lines = _dense_cluster_lines(resolved)

    entities: list[dict[str, Any]] = []
    for ordinal, candidate in enumerate(resolved, 1):
        warnings: list[str] = []
        if candidate.source_line_start in dense_lines:
            warnings.append("dense_cluster")
        entities.append(
            {
                "ordinal": ordinal,
                "entity_type": candidate.entity_type,
                "start_offset": candidate.start_offset,
                "end_offset": candidate.end_offset,
                "source_line_start": candidate.source_line_start,
                "source_line_end": candidate.source_line_end,
                "mask_token": "",
                "source_hash": _source_hash(normalized, candidate.start_offset, candidate.end_offset),
                "warnings": warnings,
            }
        )
    return assign_mask_tokens(normalized, entities, preexisting_tokens)


def _highest_preexisting_ordinal_by_type(
    preexisting_tokens: list[dict[str, Any]],
) -> dict[str, int]:
    highest = {entity_type: 0 for entity_type in MASK_PREFIXES}
    for token in preexisting_tokens:
        entity_type = token["entity_type"]
        highest[entity_type] = max(highest[entity_type], token["ordinal"])
    return highest


def assign_mask_tokens(
    text: str,
    entities: list[dict[str, Any]],
    preexisting_tokens: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Assign stable per-type mask tokens without persisting raw values."""
    existing_tokens = preexisting_tokens or []
    highest_existing = _highest_preexisting_ordinal_by_type(existing_tokens)
    next_number = {entity_type: highest + 1 for entity_type, highest in highest_existing.items()}
    token_by_value: dict[tuple[str, str], str] = {}
    assigned: list[dict[str, Any]] = []

    for entity in entities:
        entity_type = entity["entity_type"]
        value = text[entity["start_offset"] : entity["end_offset"]]
        key = (entity_type, value)
        repeated = key in token_by_value
        if repeated:
            token = token_by_value[key]
        else:
            token = f"[{MASK_PREFIXES[entity_type]}_{next_number[entity_type]}]"
            token_by_value[key] = token
            next_number[entity_type] += 1
        copied = dict(entity)
        copied["mask_token"] = token
        warnings = list(copied.get("warnings", []))
        if repeated and "repeated_value" not in warnings:
            warnings.append("repeated_value")
        copied["warnings"] = warnings
        assigned.append(copied)
    return assigned


def mask_text(text: str, entities: list[dict[str, Any]]) -> str:
    """Replace detected entity spans with mask tokens."""
    normalized = normalize_text(text)
    parts: list[str] = []
    cursor = 0
    for entity in sorted(entities, key=lambda item: item["start_offset"]):
        parts.append(normalized[cursor : entity["start_offset"]])
        parts.append(entity["mask_token"])
        cursor = entity["end_offset"]
    parts.append(normalized[cursor:])
    return "".join(parts)


def detect_and_mask(
    text: str,
    avoid_preexisting_token_collisions: bool = False,
) -> dict[str, Any]:
    normalized = normalize_text(text)
    preexisting_tokens = find_preexisting_mask_tokens(normalized) if avoid_preexisting_token_collisions else []
    entities = detect_entities(normalized, avoid_preexisting_token_collisions)
    masked = mask_text(normalized, entities)
    highest_existing = _highest_preexisting_ordinal_by_type(preexisting_tokens)
    reserved_ordinals_by_type = {
        MASK_PREFIXES[entity_type]: highest
        for entity_type, highest in highest_existing.items()
        if highest > 0
    }
    reused_reserved = 0
    for entity in entities:
        prefix = MASK_PREFIXES[entity["entity_type"]]
        highest = reserved_ordinals_by_type.get(prefix, 0)
        token_number = int(entity["mask_token"].rsplit("_", 1)[1].rstrip("]"))
        if highest and token_number <= highest:
            reused_reserved += 1
    preservation_failures = sum(
        1 for token in preexisting_tokens if normalized[token["start_offset"] : token["end_offset"]] not in masked
    )
    document_warnings: list[str] = []
    if not entities:
        document_warnings.append("no_pii_detected")
    return {
        "entities": entities,
        "masked_text": masked,
        "masked_text_sha256": hashlib.sha256(masked.encode("utf-8")).hexdigest(),
        "document_warnings": document_warnings,
        "preexisting_token_count": len(preexisting_tokens),
        "highest_preexisting_ordinal_by_type": reserved_ordinals_by_type,
        "token_collision_avoided": reused_reserved == 0 and preservation_failures == 0,
        "preexisting_token_preservation_failures": preservation_failures,
        "reused_reserved_ordinal_count": reused_reserved,
    }


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")
    return data.decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and mask synthetic PII fixture text.")
    parser.add_argument("--input", required=True, help="UTF-8 fixture text path")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    try:
        result = detect_and_mask(_read_text(Path(args.input)))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(payload + "\n", encoding="utf-8", newline="\n")
    sys.stdout.buffer.write((payload + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
