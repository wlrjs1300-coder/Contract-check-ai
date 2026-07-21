from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence


MAX_EVIDENCE_SOURCE_TEXT_LENGTH = 1200
MAX_FINDING_EVIDENCE_COUNT = 10
MAX_CANDIDATE_COUNT = 50
MAX_SNAPSHOT_TEXT_LENGTH = 2_000_000


class EvidenceValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def normalize_snapshot_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    return value


def calculate_snapshot_hash(snapshot: list[dict[str, object]]) -> str:
    canonical_pages: list[dict[str, object]] = []
    for page in snapshot:
        if not isinstance(page, dict):
            continue

        blocks = []
        for index, block in enumerate(
            page.get("blocks") if isinstance(page.get("blocks"), list) else []
        ):
            if not isinstance(block, dict):
                continue
            blocks.append(
                {
                    "block_id": str(block.get("block_id", f"p{page.get('page_number', index+1)}-b{index+1}")),
                    "text": normalize_snapshot_text(str(block.get("text", ""))),
                    "start_in_page_offset": int(block.get("start_in_page_offset", 0)),
                    "end_in_page_offset": int(
                        block.get(
                            "end_in_page_offset",
                            len(str(block.get("text", ""))),
                        )
                    ),
                }
            )

        canonical_pages.append(
            {
                "page_number": int(page.get("page_number", -1)),
                "final_text": normalize_snapshot_text(str(page.get("final_text", ""))),
                "blocks": blocks,
            }
        )

    canonical = json.dumps(canonical_pages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _quote_offsets(page_text: str, source_text: str) -> tuple[str, int, int]:
    if not source_text:
        return "invalid", -1, -1

    canonical_page = normalize_snapshot_text(page_text)
    canonical_source = normalize_snapshot_text(source_text)

    exact_matches = [m for m in re.finditer(re.escape(source_text), page_text)]
    if len(exact_matches) == 1:
        match = exact_matches[0]
        return "exact_match", match.start(), match.end()
    if len(exact_matches) > 1:
        return "ambiguous_match", -1, -1

    normalized_matches = [m for m in re.finditer(re.escape(canonical_source), canonical_page)]
    if len(normalized_matches) == 1:
        match = normalized_matches[0]
        return "normalized_unique_match", match.start(), match.end()
    if len(normalized_matches) > 1:
        return "ambiguous_match", -1, -1

    return "no_match", -1, -1


def resolve_quote_match(page_text: str, source_text: str) -> dict[str, object]:
    status, start, end = _quote_offsets(page_text, source_text)
    if status in {"exact_match", "normalized_unique_match"}:
        return {
            "status": status,
            "code": None,
            "start_offset": start,
            "end_offset": end,
        }
    return {
        "status": "no_match" if status == "no_match" else "ambiguous_match",
        "code": "evidence_ambiguous" if status == "ambiguous_match" else "evidence_text_mismatch",
        "start_offset": start,
        "end_offset": end,
    }


def _iter_block_ranges(blocks: list[dict[str, object]]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("block_id", ""))
        if not block_id:
            continue
        block_text = str(block.get("text", ""))
        start = int(block.get("start_in_page_offset", 0))
        end = int(block.get("end_in_page_offset", start + len(block_text)))
        ranges.append((start, end, block_id))
    return ranges


def _normalize_block_ids(block_ids: Sequence[str] | None) -> list[str] | None:
    if block_ids is None:
        return None
    if not isinstance(block_ids, Sequence):
        return None
    return [str(block_id) for block_id in block_ids]


def build_evidence_candidates(
    *,
    document_id: str,
    extraction_id: str,
    clause_id: str,
    source_text: str,
    snapshot: list[dict[str, object]],
    snapshot_hash: str | None = None,
    clause_start_offset: int | None = None,
    clause_end_offset: int | None = None,
    page_number: int | None = None,
    block_ids: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    if not source_text.strip():
        raise EvidenceValidationError("evidence_reference_invalid", "source_text is required.")
    if len(source_text) > MAX_EVIDENCE_SOURCE_TEXT_LENGTH:
        raise EvidenceValidationError(
            "evidence_reference_invalid",
            "source_text is too long.",
        )
    if not snapshot:
        return []

    target_block_ids = set(_normalize_block_ids(block_ids) or [])
    candidates: list[dict[str, object]] = []
    next_suffix = 1

    for page in snapshot:
        if not isinstance(page, dict):
            continue
        current_page_number = page.get("page_number")
        if not isinstance(current_page_number, int):
            continue
        if page_number is not None and current_page_number != page_number:
            continue

        page_text = str(page.get("final_text", ""))
        if len(page_text) > MAX_SNAPSHOT_TEXT_LENGTH:
            raise EvidenceValidationError(
                "evidence_page_not_found",
                "snapshot page text is too large.",
            )

        status, start, end = _quote_offsets(page_text, source_text)

        if status in {"ambiguous_match", "no_match"}:
            if status == "ambiguous_match":
                candidates.append(
                    {
                        "evidence_id": f"{clause_id}-e{next_suffix:03d}",
                        "document_id": document_id,
                        "extraction_id": extraction_id,
                        "page_number": current_page_number,
                        "clause_id": clause_id,
                        "source_text": source_text,
                        "start_offset": 0,
                        "end_offset": 0,
                        "block_ids": [],
                        "evidence_type": "source_quote",
                        "validation_status": "evidence_ambiguous",
                        "confidence": 0.0,
                        "evidence_snapshot_hash": snapshot_hash,
                        "clause_start_offset": clause_start_offset,
                        "clause_end_offset": clause_end_offset,
                    }
                )
                next_suffix += 1
            continue

        blocks = page.get("blocks") if isinstance(page.get("blocks"), list) else []
        block_ranges = _iter_block_ranges(blocks)
        overlapping_blocks: list[str] = []
        for block_start, block_end, block_id in block_ranges:
            if not (end <= block_start or start >= block_end):
                overlapping_blocks.append(block_id)
        if not overlapping_blocks and target_block_ids:
            overlapping_blocks = [b for b in target_block_ids if b in {x[2] for x in block_ranges}]

        candidate = {
            "evidence_id": f"{clause_id}-e{next_suffix:03d}",
            "document_id": document_id,
            "extraction_id": extraction_id,
            "page_number": current_page_number,
            "clause_id": clause_id,
            "source_text": source_text,
            "start_offset": start,
            "end_offset": end,
            "block_ids": overlapping_blocks,
            "evidence_type": "source_quote",
            "validation_status": status,
            "confidence": 1.0,
            "evidence_snapshot_hash": snapshot_hash,
            "clause_start_offset": clause_start_offset,
            "clause_end_offset": clause_end_offset,
        }
        candidates.append(candidate)
        next_suffix += 1

        if len(candidates) >= MAX_CANDIDATE_COUNT:
            break

    return candidates


def validate_evidence_reference(
    *,
    evidence: dict[str, object],
    snapshot_pages: dict[int, dict[str, object]],
    document_id: str,
    extraction_id: str,
    snapshot_hash: str | None,
    clause_id: str,
    clause_start_offset: int | None = None,
    clause_end_offset: int | None = None,
) -> dict[str, object]:
    source_text = str(evidence.get("source_text", ""))
    if not source_text.strip():
        raise EvidenceValidationError("evidence_reference_invalid", "source_text is required.")
    if len(source_text) > MAX_EVIDENCE_SOURCE_TEXT_LENGTH:
        raise EvidenceValidationError("evidence_reference_invalid", "source_text is too long.")

    if evidence.get("document_id") != document_id:
        raise EvidenceValidationError("evidence_reference_invalid", "document_id mismatch.")
    if evidence.get("extraction_id") != extraction_id:
        raise EvidenceValidationError("evidence_reference_invalid", "extraction_id mismatch.")
    if evidence.get("evidence_snapshot_hash") != snapshot_hash:
        raise EvidenceValidationError("evidence_snapshot_mismatch", "snapshot hash mismatch.")
    if evidence.get("clause_id") != clause_id:
        raise EvidenceValidationError("evidence_clause_not_found", "clause_id mismatch.")

    page_number = evidence.get("page_number")
    if not isinstance(page_number, int):
        raise EvidenceValidationError("evidence_page_not_found", "page_number is required.")
    if page_number not in snapshot_pages:
        raise EvidenceValidationError("evidence_page_not_found", "invalid page_number.")

    page = snapshot_pages[page_number]
    page_text = str(page.get("final_text", ""))

    start_offset = evidence.get("start_offset")
    end_offset = evidence.get("end_offset")
    if not isinstance(start_offset, int) or not isinstance(end_offset, int):
        raise EvidenceValidationError("evidence_offset_invalid", "offset type error.")
    if start_offset < 0 or end_offset <= start_offset:
        raise EvidenceValidationError("evidence_offset_invalid", "offset range error.")
    if end_offset > len(page_text):
        raise EvidenceValidationError("evidence_offset_invalid", "offset out of range.")

    matched = page_text[start_offset:end_offset]
    if matched != source_text:
        status = resolve_quote_match(page_text, source_text)["status"]
        if status != "exact_match" and status != "normalized_unique_match":
            if status == "ambiguous_match":
                raise EvidenceValidationError("evidence_ambiguous", "ambiguous quote.")
            raise EvidenceValidationError("evidence_text_mismatch", "text mismatch.")

    block_ids = evidence.get("block_ids")
    if not isinstance(block_ids, list) or not block_ids:
        raise EvidenceValidationError("evidence_block_not_found", "block_ids required.")

    page_block_ids = {
        str(block.get("block_id", ""))
        for block in page.get("blocks", [])
        if isinstance(block, dict)
    }
    for block_id in block_ids:
        if str(block_id) not in page_block_ids:
            raise EvidenceValidationError("evidence_block_not_found", "unknown block id.")

    if (
        clause_start_offset is not None
        and clause_end_offset is not None
        and not (clause_start_offset <= start_offset <= clause_end_offset)
    ):
        raise EvidenceValidationError(
            "evidence_clause_not_found",
            "evidence range out of clause range.",
        )

    if (
        clause_start_offset is not None
        and clause_end_offset is not None
        and end_offset > clause_end_offset
    ):
        raise EvidenceValidationError(
            "evidence_clause_not_found",
            "evidence range out of clause range.",
        )

    return evidence


def validate_finding_evidence(
    *,
    evidence_list: list[dict[str, object]],
    snapshot: list[dict[str, object]],
    document_id: str,
    extraction_id: str,
    clause_id: str,
    snapshot_hash: str | None,
    clause_start_offset: int | None = None,
    clause_end_offset: int | None = None,
) -> list[dict[str, object]]:
    if not evidence_list:
        raise EvidenceValidationError("evidence_missing", "No evidence.")
    if len(evidence_list) > MAX_FINDING_EVIDENCE_COUNT:
        evidence_list = evidence_list[:MAX_FINDING_EVIDENCE_COUNT]

    snapshot_pages = {
        int(page["page_number"]): page
        for page in snapshot
        if isinstance(page, dict) and isinstance(page.get("page_number"), int)
    }

    validated: list[dict[str, object]] = []
    seen: set[tuple[int, int, int]] = set()
    for evidence in evidence_list:
        validated_one = validate_evidence_reference(
            evidence=evidence,
            snapshot_pages=snapshot_pages,
            document_id=document_id,
            extraction_id=extraction_id,
            snapshot_hash=snapshot_hash,
            clause_id=clause_id,
            clause_start_offset=clause_start_offset,
            clause_end_offset=clause_end_offset,
        )
        key = (
            int(validated_one["page_number"]),
            int(validated_one["start_offset"]),
            int(validated_one["end_offset"]),
        )
        if key in seen:
            continue
        seen.add(key)
        validated.append(validated_one)

    if not validated:
        raise EvidenceValidationError("evidence_missing", "No unique evidence remains.")

    return validated


def bind_evidence_to_finding(
    *,
    document_id: str,
    extraction_id: str,
    clause,
    snapshot: list[dict[str, object]],
    snapshot_hash: str | None,
    snapshot_version: int | None,
) -> list[dict[str, object]]:
    del snapshot_version
    clause_id = clause.reference_id
    source_text = str(getattr(clause, "body", ""))

    if not snapshot:
        return [
            {
                "evidence_id": f"{clause_id}-e001",
                "document_id": document_id,
                "extraction_id": extraction_id,
                "page_number": 1,
                "clause_id": clause_id,
                "source_text": source_text[:MAX_EVIDENCE_SOURCE_TEXT_LENGTH],
                "start_offset": 0,
                "end_offset": 0,
                "block_ids": [],
                "evidence_type": "source_quote",
                "validation_status": "not_available",
                "confidence": 0.0,
            }
        ]

    candidates = build_evidence_candidates(
        document_id=document_id,
        extraction_id=extraction_id,
        clause_id=clause_id,
        source_text=source_text[:MAX_EVIDENCE_SOURCE_TEXT_LENGTH],
        snapshot=snapshot,
        snapshot_hash=snapshot_hash,
        clause_start_offset=getattr(clause, "start_offset", None),
        clause_end_offset=getattr(clause, "end_offset", None),
        block_ids=_normalize_block_ids(getattr(clause, "block_ids", None)),
    )

    if not candidates:
        raise EvidenceValidationError(
            "evidence_missing",
            "No matching quote candidates found.",
        )

    return validate_finding_evidence(
        evidence_list=candidates,
        snapshot=snapshot,
        document_id=document_id,
        extraction_id=extraction_id,
        clause_id=clause_id,
        snapshot_hash=snapshot_hash,
        clause_start_offset=getattr(clause, "start_offset", None),
        clause_end_offset=getattr(clause, "end_offset", None),
    )


def extract_normalized_snapshot_text(pages: list[dict[str, object]]) -> str:
    return "\n".join(
        normalize_snapshot_text(str(page.get("final_text", "")))
        for page in pages
        if isinstance(page, dict)
    )
