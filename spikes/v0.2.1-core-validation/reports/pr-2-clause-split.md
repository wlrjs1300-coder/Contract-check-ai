# PR-2 Clause Splitting Validation

## Purpose

This report records the v0.2.1 PR-2 clause splitting spike for ContractCheck AI.

The goal is to reduce uncertainty around deterministic Korean clause splitting before the formal v0.5 pipeline design. This is an experiment result, not product code and not a legal safety guarantee.

## Input Fixtures

Four synthetic fixtures were used.

| Test case | Fixture | Purpose |
|---|---|---|
| `employment-contract-01` | `employment-contract-01.sample.txt` | Basic article markers and signature boundary |
| `employment-contract-02` | `employment-contract-02.sample.txt` | Mixed marker styles, header, footer, signature, unclassified text |
| `clause-split-edge-01` | `clause-split-edge-01.sample.txt` | No clause marker detected |
| `clause-split-edge-02` | `clause-split-edge-02.sample.txt` | Inline marker suspicion, empty clauses, explicit title, special agreement, appendix |

All fixtures are synthetic and contain no real personal data or real contract text.

## Expected Freeze

Expected data was written and approved before implementation.

```text
spikes/v0.2.1-core-validation/data/fixtures/clause-split-expected.sample.json
```

Authorship status:

```text
approved-frozen-before-implementation
```

The implementation was written after the expected file was available. The expected file was not changed to match implementation output.

## Implementation Strategy

The splitter uses Python standard library only.

The core strategy is:

1. Read UTF-8 input and reject UTF-8 BOM.
2. Normalize CRLF and CR to LF.
3. Track 0-based offsets and 1-based line numbers on normalized text.
4. Split the document into non-empty paragraphs.
5. Classify each paragraph as a clause, non-clause section, or unclassified section.
6. Preserve every non-whitespace source character in exactly one section.

## Supported Markers

The splitter recognizes:

- `제1조`
- `제 1 조`
- `제1조(제목)`
- `제 1 조 (제목)`
- `1.`
- `1)`
- `(1)`
- `①` through `⑨`
- line exactly equal to `특약`
- line exactly equal to `부칙`

`특약 내용은...` and `부칙 안의...` are not treated as independent markers.

## Unsupported Scope

This PR does not include:

- PDF input
- external AI calls
- provider adapters
- personal data detection
- masking
- legal expression filtering
- product API or backend integration
- package installation

## Observation Metrics

The evaluator checks:

- expected source hash and fixture hash match
- clause count and fields
- marker, clause type, title, raw heading, body
- offset and line numbers
- clause warnings
- non-clause sections
- unclassified sections
- document warnings
- `reference_id` format and offset consistency
- `source_hash` recalculation
- duplicate `reference_id`
- overlapping sections
- uncovered non-whitespace source characters

## Fixture Results

| Test case | Passed | Expected clauses | Actual clauses | Notes |
|---|---:|---:|---:|---|
| `employment-contract-01` | true | 8 | 8 | Signature section preserved |
| `employment-contract-02` | true | 6 | 6 | Header, footer, signature, and unclassified sections preserved |
| `clause-split-edge-01` | true | 0 | 0 | `no_clause_marker_detected` observed |
| `clause-split-edge-02` | true | 8 | 8 | Inline marker, empty body, title, appendix, and special agreement cases observed |

## Inline Marker Result

`clause-split-edge-02` produced `inline_marker_suspected` for the first clause where an additional marker-like `2.` appears in the same line.

The numeric patterns `3.5개월`, `2) 선택 항목`, and `1,000` were not treated as new clauses.

## Empty Clause Result

`clause-split-edge-02` produced two `empty_body` warnings:

- `3.`
- `제6조`

Both were preserved as clauses with empty body strings.

## Title Result

The explicit title `기간 표현` was extracted from:

```text
제 2 조 (기간 표현) ...
```

The parenthesized title was excluded from the body. Other heading text was not forced into `title`.

## Appendix and Special Agreement Result

`부칙` was classified as `appendix`.

Standalone `특약` and the `제5조 특약` case were classified as `special_agreement`.

본문 lines beginning with `특약 내용은...` or `부칙 안의...` were preserved as body text, not split as new markers.

## Non-Clause and Unclassified Result

Header, footer, and signature sections were preserved as `non_clause_sections`.

Text that was not a clause or non-clause section was preserved as `unclassified_sections` with `unclassified_text` warnings.

## Source Coverage Result

Observed result:

- overlapping sections: 0
- uncovered non-whitespace characters: 0
- duplicate reference IDs: 0
- invalid source hashes: 0

## Independent Review Follow-up

Independent review found that Windows stdout could use the local code page and CRLF conversion if CLI streams were not configured explicitly.

Follow-up changes:

- `split_clauses.py` now configures stdout and stderr as UTF-8 with LF newlines at CLI startup.
- `evaluate_clause_split.py` now configures stdout and stderr as UTF-8 with LF newlines at CLI startup.
- The evaluator no longer calls `split_text` directly in the same process.
- The evaluator runs `split_clauses.py` with `subprocess.run`, captures stdout and stderr as bytes, rejects UTF-8 BOM, rejects CRLF, decodes stdout with UTF-8 strict mode, checks CLI exit code, and parses actual JSON from the real CLI path.
- Expected input and fixture files were not changed.
- Normal input errors now return concise `stderr` messages such as `error: UTF-8 BOM is not allowed` instead of full tracebacks.

Revalidation after the follow-up changes:

- 4 fixtures passed.
- `reference_id` errors: 0
- `source_hash` errors: 0
- overlapping sections: 0
- uncovered non-whitespace characters: 0
- stdout UTF-8/LF validation: passed
- `--output` UTF-8/LF validation: passed by separate manual execution
- deterministic stdout bytes for repeated input: passed

## Known Limits

- Validation is based on the 4 synthetic fixtures listed in this report.
- This does not guarantee support for all general contract formats.
- Paragraph boundaries currently drive most splitting behavior.
- The splitter does not parse tables beyond preserving them as unclassified text.
- The splitter does not evaluate legal meaning.
- The splitter does not support PDF extraction.
- The splitter does not detect or mask personal data.
- The splitter does not implement legal expression checking.
- The splitter is not production parser code.
- Product code integration is not included in this PR.

## Tentative A/B/C/D Judgment

Tentative judgment: B

Reason:

- The implementation matches the frozen synthetic expected data and preserves source coverage.
- The current approach is usable as a design reference with documented constraints.
- More varied real-world-like synthetic cases are needed before product design relies on this approach.

## Expected Change History

- Initial freeze: `approved-frozen-before-implementation`
- Changes after initial freeze: none
