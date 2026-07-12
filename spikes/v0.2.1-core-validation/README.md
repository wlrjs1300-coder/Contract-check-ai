# v0.2.1 Core Validation Spike

## Purpose

This directory contains the shared foundation for ContractCheck AI v0.2.1 core validation spikes.

v0.2.1 is not product feature implementation. It is a technical uncertainty reduction phase for later design decisions around clause splitting, personal data detection and masking, output safety, and AI provider policy review.

PR-1 created the foundation structure. PR-2 adds a local clause splitting experiment for synthetic TXT and simple JSON input only.

This spike does not implement personal data detection, masking, output filtering, provider adapters, PDF extraction, or external AI calls.

## Scope

This foundation includes:

- common spike directory structure
- experiment purpose and execution rules
- shared result schema
- minimal synthetic data generator
- clause splitting experiment scripts
- small non-sensitive fixture files
- Git ignore rules for generated data, raw outputs, and summary outputs
- v0.2.1 progress checklist

## PR Roadmap

| PR | Scope | Status |
|---|---|---|
| PR-1 | Experiment foundation structure | Completed |
| PR-2 | Clause splitting validation | Current PR |
| PR-3 | Personal data detection and masking | Future PR |
| PR-4 | Masked contract analysis usefulness | Future PR |
| PR-5 | Output safety validation | Future PR |
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

## Follow-up

Later PRs will implement each experiment separately. This foundation intentionally avoids implementing experiment logic so that each validation topic can be reviewed independently.
