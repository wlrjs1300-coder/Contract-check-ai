# v0.2.1 Core Validation Spike

## Purpose

This directory contains the shared foundation for ContractCheck AI v0.2.1 core validation spikes.

v0.2.1 is not product feature implementation. It is a technical uncertainty reduction phase for later design decisions around clause splitting, personal data detection and masking, output safety, and AI provider policy review.

This PR only creates the foundation structure. It does not implement actual clause splitting, personal data detection, masking, output filtering, provider adapters, or external AI calls.

## Scope

This foundation includes:

- common spike directory structure
- experiment purpose and execution rules
- shared result schema
- minimal synthetic data generator
- two small non-sensitive fixture files
- Git ignore rules for generated data and raw outputs
- v0.2.1 progress checklist

## PR Roadmap

| PR | Scope | Status |
|---|---|---|
| PR-1 | Experiment foundation structure | Current PR |
| PR-2 | Clause splitting validation | Future PR |
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

Tracked fixture files are limited to small `.sample.txt` files under `data/fixtures/`.

## Follow-up

Later PRs will implement each experiment separately. This foundation intentionally avoids implementing experiment logic so that each validation topic can be reviewed independently.
