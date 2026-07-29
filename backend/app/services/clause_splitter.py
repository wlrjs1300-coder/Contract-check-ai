from __future__ import annotations

import hashlib
import re


ARTICLE_RE = re.compile(r"^제\s*\d+\s*조(?:\s*\(([^)]*)\))?(?:\s+(.*))?$")
ARTICLE_ITEM_RE = re.compile(r"^제\s*\d+\s*항(?:\s*\(([^)]*)\))?(?:\s+(.*))?$")
NUMBER_DOT_RE = re.compile(r"^(\d+)\.\s*(.*)$")
NUMBER_PAREN_RE = re.compile(r"^(\d+)\)\s*(.*)$")
PAREN_NUMBER_RE = re.compile(r"^\((\d+)\)\s*(.*)$")
CIRCLED_RE = re.compile(r"^([\u2460-\u2468])\s*(.*)$")
HANGUL_DOT_RE = re.compile(r"^([가-하])\.\s*(.*)$")
SPECIAL_CLAUSE_RE = re.compile(r"^전문\s*(.*)$")
APPENDIX_RE = re.compile(r"^부칙\s*(?:\(([^)]*)\))?(?:\s*(.*))?$")


def _short_source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _normalize_title(raw_title: str | None) -> str | None:
    if not raw_title:
        return None

    title = raw_title.strip()
    if title.startswith("(") and title.endswith(")"):
        title = title[1:-1].strip()
    elif title.startswith("（") and title.endswith("）"):
        title = title[1:-1].strip()
    return title or None


def _detect_marker(line: str) -> dict[str, str | bool] | None:
    stripped = line.strip()
    if not stripped:
        return None

    for pattern, clause_type in (
        (ARTICLE_RE, "normal"),
        (ARTICLE_ITEM_RE, "normal"),
        (NUMBER_DOT_RE, "normal"),
        (NUMBER_PAREN_RE, "normal"),
        (PAREN_NUMBER_RE, "normal"),
        (CIRCLED_RE, "normal"),
        (HANGUL_DOT_RE, "normal"),
        (SPECIAL_CLAUSE_RE, "special_agreement"),
        (APPENDIX_RE, "appendix"),
    ):
        match = pattern.match(stripped)
        if not match:
            continue
        marker_text = match.group(0)
        if pattern in (ARTICLE_RE, ARTICLE_ITEM_RE):
            title = (match.group(1) or "").strip()
            inline = (match.group(2) or "").strip()
            if title:
                return {
                    "marker": marker_text.split()[0] if marker_text.split() else marker_text,
                    "title": title,
                    "rest": inline,
                    "inline_text": "",
                    "include_rest_as_body": False,
                    "clause_type": clause_type,
                }
            return {
                "marker": marker_text.split()[0] if marker_text.split() else marker_text,
                "title": None,
                "rest": "",
                "inline_text": inline,
                "include_rest_as_body": True,
                "clause_type": clause_type,
            }

        rest = (match.group(1) or match.group(2) or "").strip()
        return {
            "marker": marker_text.split()[0] if marker_text.split() else marker_text,
            "rest": rest,
            "clause_type": clause_type,
            "inline_text": rest,
            "title": None,
            "include_rest_as_body": pattern
            in (NUMBER_DOT_RE, NUMBER_PAREN_RE, PAREN_NUMBER_RE, CIRCLED_RE, HANGUL_DOT_RE),
        }
    return None


def split_clauses(text: str, document_id: str) -> dict[str, object]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    clauses: list[dict[str, object]] = []
    unclassified_sections: list[str] = []

    for paragraph in paragraphs:
        lines = paragraph.splitlines()
        marker = _detect_marker(lines[0])

        if marker is None:
            unclassified_sections.append(paragraph)
            continue

        body_lines = []
        if marker["inline_text"]:
            body_lines.append(str(marker["inline_text"]))
        if len(lines) > 1:
            body_lines.extend(lines[1:])

        body = "\n".join(body_lines).strip()
        ordinal = len(clauses) + 1
        clauses.append(
            {
                "clause_id": f"clause-{ordinal:03d}",
                "reference_id": f"{document_id}:clause:{ordinal}",
                "source_hash": _short_source_hash(paragraph),
                "ordinal": ordinal,
                "marker": marker["marker"],
                "clause_type": marker["clause_type"],
                "title": _normalize_title(str(marker.get("title"))),
                "body": body,
                "warnings": ["empty_body"] if not body else [],
            }
        )

    document_warnings: list[str] = []
    if not clauses:
        document_warnings.append("no_clause_marker_detected")

    return {
        "document_id": document_id,
        "clause_count": len(clauses),
        "clauses": clauses,
        "unclassified_sections": unclassified_sections,
        "document_warnings": document_warnings,
    }


def _normalize_block_ids(
    blocks: list[dict[str, object]],
    page_number: int,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    used: set[str] = set()

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue

        block_id = str(block.get("block_id", "")).strip()
        if not block_id or block_id in used:
            block_id = f"p{page_number}-b{index + 1}"
        used.add(block_id)

        text = str(block.get("text", ""))
        normalized.append(
            {
                "block_id": block_id,
                "text": text,
                "start_in_page_offset": int(block.get("start_in_page_offset", 0)),
                "end_in_page_offset": int(
                    block.get("end_in_page_offset", 0) or len(text)
                ),
            }
        )
    if not normalized:
        normalized.append(
            {
                "block_id": f"p{page_number}-b1",
                "text": "",
                "start_in_page_offset": 0,
                "end_in_page_offset": 0,
            }
        )
    return normalized


def split_clauses_with_snapshot(
    pages: list[dict[str, object]],
    *,
    document_id: str,
) -> dict[str, object]:
    if not pages:
        return {
            "document_id": document_id,
            "clause_count": 0,
            "clauses": [],
            "unclassified_sections": [],
            "document_warnings": ["empty_snapshot"],
            "page_metadata": [],
            "snapshot_version": 1,
            "split_method": "whole_document_fallback",
        }

    sorted_pages = sorted(
        [page for page in pages if isinstance(page, dict)],
        key=lambda page: int(page.get("page_number", 0)),
    )

    page_text_map: dict[int, str] = {}
    page_metadata: list[dict[str, object]] = []
    page_blocks: dict[int, list[dict[str, object]]] = {}

    lines: list[tuple[int, str, int]] = []
    for page_index, page in enumerate(sorted_pages, start=1):
        page_number = int(page.get("page_number", page_index))
        page_text = str(page.get("final_text", ""))
        page_text_map[page_number] = page_text
        blocks_raw = page.get("blocks") if isinstance(page.get("blocks"), list) else []
        blocks = _normalize_block_ids(blocks_raw, page_number)
        page["blocks"] = blocks
        page_blocks[page_number] = blocks
        page_metadata.append(
            {
                "page_number": page_number,
                "blocks": blocks,
            }
        )

        offset = 0
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                offset += len(raw_line) + 1
                continue
            lines.append((page_number, line, offset))
            offset += len(raw_line) + 1

    clauses: list[dict[str, object]] = []
    unclassified_sections: list[str] = []

    has_marker = any(_detect_marker(line[1]) is not None for line in lines)
    if not has_marker:
        for page in sorted_pages:
            page_number = int(page.get("page_number", 0))
            page_text = page_text_map.get(page_number, "")
            clause_id = f"snapshot-clause-{len(clauses) + 1:03d}"
            clauses.append(
                {
                    "clause_id": clause_id,
                    "reference_id": f"{document_id}:clause:{len(clauses) + 1}",
                    "source_hash": _short_source_hash(page_text),
                    "ordinal": len(clauses) + 1,
                    "marker": "unclassified",
                    "clause_type": "normal",
                    "title": None,
                    "body": page_text.strip(),
                    "text": page_text,
                    "warnings": [],
                    "clause_number": len(clauses) + 1,
                    "clause_title": None,
                    "clause_level": "document",
                    "parent_clause_id": None,
                    "page_start": page_number,
                    "page_end": page_number,
                    "start_offset": 0,
                    "end_offset": len(page_text),
                    "block_ids": [block["block_id"] for block in page_blocks.get(page_number, [])],
                    "split_method": "whole_document_fallback",
                }
            )
        return {
            "document_id": document_id,
            "clause_count": len(clauses),
            "clauses": clauses,
            "unclassified_sections": unclassified_sections,
            "document_warnings": [],
            "page_metadata": page_metadata,
            "split_method": "whole_document_fallback",
            "snapshot_version": 1,
        }

    clause_number = 0
    current: dict[str, object] | None = None

    def _close_current() -> None:
        nonlocal current
        if current is None:
            return
        body = str(current.get("body", "")).strip()
        if body:
            clauses.append(current)
        current = None

    for page_number, line, line_offset in lines:
        marker = _detect_marker(line)
        if marker is None:
            if current is not None:
                current["body"] = f"{current['body']}\n{line}"
                current["end_offset"] = line_offset + len(line)
                current["page_end"] = page_number
            else:
                unclassified_sections.append(line)
            continue

        _close_current()
        clause_number += 1
        rest = str(marker.get("inline_text", "")) if marker["inline_text"] else ""
        title = _normalize_title(str(marker.get("title", "")))
        blocks = page_blocks.get(page_number, [])

        current = {
            "clause_id": f"snapshot-clause-{clause_number:03d}",
            "reference_id": f"{document_id}:clause:{clause_number}",
            "source_hash": _short_source_hash(line),
            "ordinal": clause_number,
            "marker": marker["marker"],
            "clause_type": marker["clause_type"],
            "title": title,
            "body": rest,
            "text": line,
            "warnings": ["empty_body"] if not rest else [],
            "clause_number": clause_number,
            "clause_title": title,
            "clause_level": "line",
            "parent_clause_id": None,
            "page_start": page_number,
            "page_end": page_number,
                "start_offset": line_offset,
                "end_offset": line_offset + len(line),
            "block_ids": [block["block_id"] for block in blocks],
            "split_method": "marker_split",
            }

    _close_current()

    if not clauses:
        first_page = sorted_pages[0]
        page_number = int(first_page.get("page_number", 1))
        full_text = str(first_page.get("final_text", ""))
        clauses = [
            {
                "clause_id": "snapshot-clause-001",
                "reference_id": f"{document_id}:clause:1",
                "source_hash": _short_source_hash(full_text),
                "ordinal": 1,
                "marker": "unclassified",
                "clause_type": "normal",
                "title": None,
                "body": full_text,
                "text": full_text,
                "warnings": [],
                "clause_number": 1,
                "clause_title": None,
                "clause_level": "document",
                "parent_clause_id": None,
                "page_start": page_number,
                "page_end": page_number,
                "start_offset": 0,
                "end_offset": len(full_text),
                "block_ids": [block["block_id"] for block in page_blocks.get(page_number, [])],
                "split_method": "whole_document_fallback",
            }
        ]
        document_warnings = ["fallback_clause_from_snapshot"]
    else:
        document_warnings = []

    return {
        "document_id": document_id,
        "clause_count": len(clauses),
        "clauses": clauses,
        "unclassified_sections": unclassified_sections,
        "document_warnings": document_warnings,
        "page_metadata": page_metadata,
        "split_method": "marker_or_fallback",
        "snapshot_version": 1,
    }
