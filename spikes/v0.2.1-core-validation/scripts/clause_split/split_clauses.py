"""Deterministic clause splitting spike for v0.2.1 synthetic fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARTICLE_RE = re.compile(r"^(제\s*\d+\s*조)(?:\s*(.*))?$")
NUMBER_DOT_RE = re.compile(r"^(\d+\.)(?:\s+(.*))?$")
NUMBER_PAREN_RE = re.compile(r"^(\d+\))(?:\s+(.*))?$")
PAREN_NUMBER_RE = re.compile(r"^(\(\d+\))(?:\s+(.*))?$")
CIRCLED_RE = re.compile(r"^([①②③④⑤⑥⑦⑧⑨])(?:\s+(.*))?$")
TITLE_RE = re.compile(r"^\(([^)]+)\)\s*(.*)$")
INLINE_MARKER_RE = re.compile(r"(?<![\d.])\b\d+[.)]\s+\S")


@dataclass(frozen=True)
class Line:
    number: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Paragraph:
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int
    lines: list[Line]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True)
class Marker:
    marker: str
    rest: str
    clause_type: str


def normalize_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not valid UTF-8: {exc.reason}") from exc


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")


def read_input(path: Path) -> tuple[str, str | None, str]:
    text = normalize_bytes(path.read_bytes())
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON input: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON input must be an object")
        if "text" not in payload:
            raise ValueError("JSON input must contain a 'text' field")
        if not isinstance(payload.get("text"), str):
            raise ValueError("JSON input 'text' field must be a string")
        case_id = payload.get("test_case_id")
        if case_id is not None and not isinstance(case_id, str):
            raise ValueError("JSON input 'test_case_id' must be a string when present")
        return payload["text"].replace("\r\n", "\n").replace("\r", "\n"), case_id, "json"
    return text, None, "fixture"


def default_test_case_id(path: Path) -> str:
    name = path.name
    if name.endswith(".sample.txt"):
        return name[: -len(".sample.txt")]
    if name.endswith(".txt"):
        return name[: -len(".txt")]
    return path.stem


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_source_hash(text: str) -> str:
    return sha256_text(text)[:12]


def build_lines(text: str) -> list[Line]:
    lines: list[Line] = []
    offset = 0
    parts = text.split("\n")
    for index, value in enumerate(parts):
        lines.append(Line(index + 1, offset, offset + len(value), value))
        offset += len(value)
        if index < len(parts) - 1:
            offset += 1
    return lines


def build_paragraphs(lines: list[Line]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    current: list[Line] = []
    for line in lines:
        if line.text.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append(make_paragraph(current))
            current = []
    if current:
        paragraphs.append(make_paragraph(current))
    return paragraphs


def make_paragraph(lines: list[Line]) -> Paragraph:
    return Paragraph(
        start_line=lines[0].number,
        end_line=lines[-1].number,
        start_offset=lines[0].start,
        end_offset=lines[-1].end,
        lines=list(lines),
    )


def detect_marker(line: str) -> Marker | None:
    stripped = line.strip()
    if stripped == "특약":
        return Marker("특약", "", "special_agreement")
    if stripped == "부칙":
        return Marker("부칙", "", "appendix")

    for regex in (ARTICLE_RE, NUMBER_DOT_RE, NUMBER_PAREN_RE, PAREN_NUMBER_RE, CIRCLED_RE):
        match = regex.match(line)
        if match:
            marker = match.group(1)
            rest = match.group(2) or ""
            clause_type = "special_agreement" if rest.strip() == "특약" else "normal"
            return Marker(marker, rest, clause_type)
    return None


def detect_non_clause_type(paragraph: Paragraph) -> str | None:
    first = paragraph.lines[0].text.strip()
    if first.startswith("머리글:"):
        return "header"
    if first.startswith("바닥글:"):
        return "footer"
    if first == "서명란":
        return "signature"
    return None


def build_clause(paragraph: Paragraph, marker: Marker, ordinal: int, test_case_id: str, text: str) -> dict[str, Any]:
    raw_heading = marker.rest
    title: str | None = None
    body_lines: list[str] = []

    explicit_title = TITLE_RE.match(raw_heading)
    if explicit_title:
        title = explicit_title.group(1)
        first_body = explicit_title.group(2)
        if first_body:
            body_lines.append(first_body)
    elif raw_heading:
        body_lines.append(raw_heading)

    if len(paragraph.lines) > 1:
        body_lines.extend(line.text for line in paragraph.lines[1:])

    body = "\n".join(body_lines)
    warnings: list[str] = []
    if not body:
        warnings.append("empty_body")
    if raw_heading and INLINE_MARKER_RE.search(raw_heading):
        warnings.append("inline_marker_suspected")

    if marker.marker == "부칙":
        clause_type = "appendix"
    elif marker.marker == "특약":
        clause_type = "special_agreement"
    else:
        clause_type = marker.clause_type

    source = text[paragraph.start_offset : paragraph.end_offset]
    reference_id = f"{test_case_id}:clause:{ordinal}:{paragraph.start_offset}-{paragraph.end_offset}"
    return {
        "clause_id": f"clause-{ordinal:03d}",
        "reference_id": reference_id,
        "source_hash": short_source_hash(source),
        "ordinal": ordinal,
        "marker": marker.marker,
        "clause_type": clause_type,
        "title": title,
        "raw_heading": raw_heading,
        "body": body,
        "start_offset": paragraph.start_offset,
        "end_offset": paragraph.end_offset,
        "source_line_start": paragraph.start_line,
        "source_line_end": paragraph.end_line,
        "warnings": warnings,
    }


def build_non_clause(paragraph: Paragraph, section_type: str) -> dict[str, Any]:
    return {
        "type": section_type,
        "text": paragraph.text,
        "start_offset": paragraph.start_offset,
        "end_offset": paragraph.end_offset,
        "source_line_start": paragraph.start_line,
        "source_line_end": paragraph.end_line,
        "warnings": [],
    }


def build_unclassified(paragraph: Paragraph, text: str) -> dict[str, Any]:
    return {
        "type": "unclassified",
        "text": text[paragraph.start_offset : paragraph.end_offset],
        "start_offset": paragraph.start_offset,
        "end_offset": paragraph.end_offset,
        "source_line_start": paragraph.start_line,
        "source_line_end": paragraph.end_line,
        "warnings": ["unclassified_text"],
    }


def append_unclassified(sections: list[dict[str, Any]], paragraph: Paragraph, text: str) -> None:
    if sections:
        previous = sections[-1]
        between = text[previous["end_offset"] : paragraph.start_offset]
        if not between.strip():
            previous["text"] = text[previous["start_offset"] : paragraph.end_offset]
            previous["end_offset"] = paragraph.end_offset
            previous["source_line_end"] = paragraph.end_line
            return
    sections.append(build_unclassified(paragraph, text))


def split_text(text: str, test_case_id: str, input_type: str = "fixture") -> dict[str, Any]:
    lines = build_lines(text)
    paragraphs = build_paragraphs(lines)

    clauses: list[dict[str, Any]] = []
    non_clause_sections: list[dict[str, Any]] = []
    unclassified_sections: list[dict[str, Any]] = []

    for paragraph in paragraphs:
        marker = detect_marker(paragraph.lines[0].text)
        if marker:
            clauses.append(build_clause(paragraph, marker, len(clauses) + 1, test_case_id, text))
            continue

        section_type = detect_non_clause_type(paragraph)
        if section_type:
            non_clause_sections.append(build_non_clause(paragraph, section_type))
            continue

        append_unclassified(unclassified_sections, paragraph, text)

    document_warnings: list[str] = []
    if not clauses:
        document_warnings.append("no_clause_marker_detected")

    return {
        "test_case_id": test_case_id,
        "input_type": input_type,
        "source_text_sha256": sha256_text(text),
        "clauses": clauses,
        "non_clause_sections": non_clause_sections,
        "unclassified_sections": unclassified_sections,
        "document_warnings": document_warnings,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split synthetic contract fixture text into clauses.")
    parser.add_argument("--input", required=True, help="TXT fixture or simple JSON input")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--test-case-id", help="Optional test case id override")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    try:
        args = parse_args(argv or sys.argv[1:])
        input_path = Path(args.input)
        text, json_case_id, input_type = read_input(input_path)
        test_case_id = args.test_case_id or json_case_id or default_test_case_id(input_path)
        result = split_text(text, test_case_id, input_type)
        output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(output, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(output)
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
