# v0.2.1 Core Validation Spike

## Purpose

This directory contains the shared foundation for ContractCheck AI v0.2.1 core validation spikes.

v0.2.1 is not product feature implementation. It is a technical uncertainty reduction phase for later design decisions around clause splitting, personal data detection and masking, output safety, and AI provider policy review.

PR-1 created the foundation structure. PR-2 adds a local clause splitting experiment for synthetic TXT and simple JSON input only. PR-3 adds a local deterministic personal data detection and masking experiment for frozen synthetic TXT fixtures. PR-5 adds local output safety validation for synthetic user-visible analysis output.

This spike does not implement provider adapters, PDF extraction, or external AI calls.

## Scope

This foundation includes:

- common spike directory structure
- experiment purpose and execution rules
- shared result schema
- minimal synthetic data generator
- clause splitting experiment scripts
- personal data detection and masking experiment scripts
- output safety validation experiment scripts
- small non-sensitive fixture files
- local spike reports
- Git ignore rules for generated data, raw outputs, and summary outputs
- v0.2.1 progress checklist

## PR Roadmap

| PR | Scope | Status |
|---|---|---|
| PR-1 | Experiment foundation structure | Completed |
| PR-2 | Clause splitting validation | Completed |
| PR-3 | Personal data detection and masking | Completed locally |
| PR-4 | Masked contract analysis usefulness | Completed |
| PR-5 | Output safety validation | Completed / PASS |
| PR-6 | AI provider policy review and final decision | Future PR |

PDF extraction comparison and external AI experiments are not included in the six PRs above. They remain separate follow-up candidates if needed.

## Safety Rules

- Do not use real personal data.
- Do not use real contract files.
- Do not copy real contract clauses or templates.
- Do not commit generated large synthetic datasets.
- Do not commit raw output.
- Do not call external AI APIs from this foundation.
- Do not implement provider adapters in this foundation.
- Do not add cost-generating features.

Spike results are observations for reducing technical uncertainty. They are not product quality guarantees and do not prove legal safety.

## Observation Metrics

Each later spike can record observations such as:

- whether the expected result matched the observed result
- false positive cases
- false negative cases
- privacy issues
- legal expression issues
- manual review needs
- notes for design follow-up

## A/B/C/D Decision Frame

| Grade | Meaning | Typical Follow-up |
|---|---|---|
| A | Works well enough for MVP design | Continue to detailed design |
| B | Usable with clear limitations | Continue with documented constraints |
| C | Risky or unstable | Reduce scope or add mitigation |
| D | Not usable for MVP | Rework approach before design |

The A/B/C/D grade is a spike decision aid only. It is not a legal risk score, product quality score, or user-facing risk level.

## Synthetic Data Generator

Default execution:

```bash
python spikes/v0.2.1-core-validation/scripts/generate_synthetic_data.py --count 3
```

Default output directory:

```text
spikes/v0.2.1-core-validation/data/generated/
```

The generator uses a fixed default seed for reproducibility. Use `--seed` to change it.

```bash
python spikes/v0.2.1-core-validation/scripts/generate_synthetic_data.py --seed 20260712 --count 3
```

`config/experiment.example.json` is a reference template for future experiment configuration expansion. The current `generate_synthetic_data.py` script does not read this file automatically; current execution settings are passed through CLI arguments.

The generator does not overwrite existing files by default. Choose a new output directory or remove generated local files when repeating the same command.

## Generated and Raw Data Policy

Generated files under `data/generated/` are local experiment artifacts and are ignored by Git.

Raw outputs under `outputs/raw/` are also ignored by Git. Raw input and raw external responses must not be committed.

Summary outputs under `outputs/summary/` are local execution artifacts and are ignored by Git.

Tracked fixture files are limited to small `.sample.txt` files under `data/fixtures/`.

## Clause Splitting Experiment

PR-2 uses frozen expected data written before implementation:

```text
spikes/v0.2.1-core-validation/data/fixtures/clause-split-expected.sample.json
```

The expected file must not be changed to match implementation output. If observed output differs, adjust the splitter or record the limitation in the report.

Run the splitter with a TXT fixture:

```bash
python spikes/v0.2.1-core-validation/scripts/clause_split/split_clauses.py --input spikes/v0.2.1-core-validation/data/fixtures/employment-contract-01.sample.txt
```

Run the splitter with a simple JSON input:

```json
{
  "test_case_id": "example-case",
  "text": "제1조 예시\n합성 본문"
}
```

Evaluate all frozen fixture expectations:

```bash
python spikes/v0.2.1-core-validation/scripts/clause_split/evaluate_clause_split.py --expected spikes/v0.2.1-core-validation/data/fixtures/clause-split-expected.sample.json
```

The splitter writes both stdout and `--output` files as UTF-8 with LF line endings.
On Windows PowerShell 5.1, shell redirection with `>` can re-encode native command output; use `--output` when a UTF-8/LF file artifact is required.
The evaluator runs `split_clauses.py` through a subprocess and validates the actual CLI stdout path.

Optional actual and summary outputs may be written under `outputs/summary/`, which is excluded from Git.

The splitter is limited to UTF-8 TXT and simple JSON input. It does not read PDFs, call external AI, install packages, or process real contracts.

The experiment preserves all non-whitespace source text in clauses, non-clause sections, or unclassified sections. This lossless source coverage is an experiment invariant for PR-2.

## PII Detection and Masking Experiment

PR-3 uses frozen expected data written before implementation:

```text
spikes/v0.2.1-core-validation/data/fixtures/pii-masking-expected.sample.json
```

Run the PR-3 evaluator:

```bash
python spikes/v0.2.1-core-validation/scripts/pii_masking/evaluate_pii_masking.py
```

The current local validation result is:

```text
PII masking evaluation: PASS
test_cases: 4/4
entities: 26/26
exclusions: 15/15
residual_entities: 0
```

The evaluator also verifies exclusion overlap and exclusion self-overlap. The current frozen fixture set has exclusion self-overlap count 0.

PR-3 covers these deterministic synthetic taxonomy entries:

- `person` -> `[PERSON_n]`
- `phone` -> `[PHONE_n]`
- `email` -> `[EMAIL_n]`
- `address` -> `[ADDRESS_n]`
- `date_of_birth` -> `[BIRTH_n]`
- `national_id_number` -> `[RRN_n]`
- `business_registration_number` -> `[BIZ_NO_n]`
- `account_number` -> `[ACCOUNT_n]`

The PR-3 report is stored at:

```text
spikes/v0.2.1-core-validation/reports/pr-3-pii-masking.md
```

This experiment uses synthetic fixtures only. It does not approve real personal data handling, real contract processing, external AI transfer, or production service release.

If `detect_and_mask.py --output` is used, it writes masked JSON only when the user explicitly provides the option. Real data storage and retention rules remain a separate design concern.

## Output Safety Validation Experiment

PR-5 uses frozen corrective expected data written before corrective implementation:

```text
spikes/v0.2.1-core-validation/data/fixtures/output-safety-expected.v0.2.sample.json
```

Run the PR-5 evaluator:

```bash
python spikes/v0.2.1-core-validation/scripts/output_safety/evaluate_output_safety.py
```

The current local validation result is:

```text
Output safety evaluation: PASS
test_cases: 4/4
fields: 48/48
allow: 30
block: 15
review: 3
all mismatches: 0
raw_text_exposure: 0
deterministic_mismatches: 0
```

The PR-5 report is stored at:

```text
spikes/v0.2.1-core-validation/reports/pr-5-output-safety-validation-report.md
```

This experiment validates rule-based output safety behavior for synthetic user-visible analysis output only. It does not approve production use, real contract processing, external AI transfer, or legal safety.

The next planned spike is PR-6 provider policy review and final v0.2.1 technical decision.

## Follow-up

Later PRs will implement each experiment separately. This foundation intentionally avoids implementing experiment logic so that each validation topic can be reviewed independently.
