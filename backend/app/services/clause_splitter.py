from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


ARTICLE_RE = re.compile(r"^(제\s*\d+\s*조)(?:\s*(.*))?$")
NUMBER_DOT_RE = re.compile(r"^(\d+\.)(?:\s+(.*))?$")
NUMBER_PAREN_RE = re.compile(r"^(\d+\))(?:\s+(.*))?$")
PAREN_NUMBER_RE = re.compile(r"^(\(\d+\))(?:\s+(.*))?$")
CIRCLED_RE = re.compile(r"^([①②③④⑤⑥⑦⑧⑨])(?:\s+(.*))?$")
TITLE_RE = re.compile(r"^\(([^)]+)\)\s*(.*)$")


@dataclass(frozen=True)
class Marker:
    marker: str
    rest: str
    clause_type: str


def _short_source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _detect_marker(line: str) -> Marker | None:
    stripped = line.strip()

    if stripped == "특약":
        return Marker("특약", "", "special_agreement")

    if stripped == "부칙":
        return Marker("부칙", "", "appendix")

    for pattern in (
        ARTICLE_RE,
        NUMBER_DOT_RE,
        NUMBER_PAREN_RE,
        PAREN_NUMBER_RE,
        CIRCLED_RE,
    ):
        match = pattern.match(stripped)

        if match:
            marker = match.group(1)
            rest = match.group(2) or ""
            clause_type = (
                "special_agreement"
                if rest.strip() == "특약"
                else "normal"
            )
            return Marker(marker, rest, clause_type)

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

        title: str | None = None
        body_lines: list[str] = []

        explicit_title = TITLE_RE.match(marker.rest)

        if explicit_title:
            title = explicit_title.group(1)
            first_body = explicit_title.group(2)

            if first_body:
                body_lines.append(first_body)
        elif marker.rest:
            body_lines.append(marker.rest)

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
                "marker": marker.marker,
                "clause_type": marker.clause_type,
                "title": title,
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
