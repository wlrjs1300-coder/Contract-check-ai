# PR-5 Output Safety Validation Report

## 1. Purpose

- Validate whether a local output safety filter can be applied to user-visible AI contract analysis text.
- Detect legal conclusion assertions, outcome guarantees, direct legal action instructions, and dismissal of expert review.
- Distinguish quoted source text from generated analysis text.
- Validate a rule-based `ALLOW` / `BLOCK` / `REVIEW` classification flow.

## 2. Validation Scope

Evaluated user-visible roles:

- `summary`
- `source_quote`
- `analysis`
- `reason`
- `recommended_action`
- `disclaimer`

Excluded fields:

- `expert_review_recommended`
- `item_id`
- `reference_id`
- `contract_type`
- `schema_version`
- `test_case_id`
- `synthetic_notice`

## 3. Frozen Criteria

Initial frozen criteria:

- path: `spikes/v0.2.1-core-validation/data/fixtures/output-safety-expected.sample.json`
- frozen commit: `76e691e7d478abb440bcf39052bc78f618ec3cde`
- status: preserved for history

Corrective frozen criteria:

- path: `spikes/v0.2.1-core-validation/data/fixtures/output-safety-expected.v0.2.sample.json`
- frozen commit: `14f1005a9adc9c7ab6640a31bc2f5fedd70c83a5`
- corrective basis: field coverage gap found during independent review
- coverage: all 48 user-visible text fields

The frozen fixture and expected files were not changed during implementation or corrective work.

## 4. Implementation

Checker:

```text
spikes/v0.2.1-core-validation/scripts/output_safety/check_output_safety.py
```

Evaluator:

```text
spikes/v0.2.1-core-validation/scripts/output_safety/evaluate_output_safety.py
```

Implementation notes:

- Uses only the Python standard library.
- Does not call external AI services.
- Does not perform network access.
- Does not install packages.
- Runs the checker through a subprocess from the evaluator.
- Avoids importing checker internals into the evaluator.
- Emits classification, categories, action, matched rule ids, and reason codes.
- Does not repeat or store full raw user-visible text in the result JSON.
- Uses role-based and context-based rules rather than fixture filename or test case branching.

## 5. Classification Policy

Overall status priority:

1. If any field is `BLOCK`, the overall status is `BLOCK`.
2. If no field is `BLOCK` and at least one field is `REVIEW`, the overall status is `REVIEW`.
3. If all fields are `ALLOW`, the overall status is `ALLOW`.

`manual_review_required`:

- `true` when at least one field is `REVIEW`
- `false` when only `ALLOW` and `BLOCK` fields are present

Main `BLOCK` categories:

- illegality determination
- invalidity determination
- legal effect certainty
- legal safety guarantee
- litigation outcome guarantee
- refund guarantee
- other outcome guarantee
- direct legal action instruction
- expert review dismissal

Main `ALLOW` categories:

- cautious language
- uncertainty disclosure
- non-advice disclaimer
- negated prohibited expression
- expert review recommendation
- meta explanation without a dangerous conclusion

Main `REVIEW` category:

- quoted source language containing prohibited legal expressions where the boundary between quotation and generated conclusion should be checked

## 6. Corrective Review History

- The first implementation passed against the frozen fixture set.
- Independent review found that the initial expected set covered only part of the user-visible output fields.
- Corrective expected v0.2 was frozen before corrective implementation.
- The evaluator was updated to run the checker twice per fixture and compare both stdout and parsed JSON for deterministic behavior.
- Further independent review found source quote heuristics, fixture phrase dependence, and insufficient generalization.
- Corrective commits generalized role-based rules and reduced fixture-specific phrase dependence.
- Later review found damaged string literals and overly broad certainty terms.
- Damaged literals were removed, generic sentence endings were removed from certainty terms, and normal UTF-8 Korean rule strings were retained.
- Final review found that meta or mixed expressions could override dangerous conclusions.
- The final corrective implementation gives explicit blocking rules priority over meta and mixed context handling.
- The final corrective implementation also applies common dangerous-output detection to disclaimers.

Relevant commits:

- `3dda2cd79df1b27bc0b41efce8537cbdc2c4831a`
  - `feat: implement output safety validation`
- `8f1428d9e5c85fea9e089af0a2cee750350c42c0`
  - `fix: generalize output safety validation`
- `cf37718261d2f37cc31eda1760aef60ee106caf0`
  - `fix: harden output safety rule generalization`
- `8984e0614b0935b3fb4cfaa5033d5d586126d84a`
  - `fix: prioritize blocking output safety rules`

## 7. Final Evaluation Result

```text
Output safety evaluation: PASS
test_cases: 4/4
fields: 48/48
allow: 30
block: 15
review: 3
missing_paths: 0
extra_paths: 0
duplicate_paths: 0
classification_mismatches: 0
category_mismatches: 0
action_mismatches: 0
overall_mismatches: 0
manual_mismatches: 0
count_mismatches: 0
raw_text_exposure: 0
deterministic_mismatches: 0
```

Additional synthetic variation checks:

- total: `18`
- result: `18/18 PASS`

## 8. Exception and Encoding Validation

- invalid JSON failure handling: PASS
- missing input failure handling: PASS
- unsupported structure failure handling: PASS
- traceback exposure: none observed
- source UTF-8 strict: PASS
- BOM: none
- U+FFFD replacement character count: `0`
- output encoding: UTF-8
- output line ending: LF
- `py_compile`: PASS
- `git diff --check`: PASS

## 9. Security and Data Use

- No real personal data was used.
- No real contract text was used.
- Only synthetic fixture data was used.
- No external AI call was made.
- No network call was made.
- No external package was installed.
- Raw user-visible text is not repeated in checker result JSON.
- Raw source text is not logged as a validation artifact.

## 10. Known Minor

The corrective expected v0.2 file contains one non-functional rationale string with placeholder characters:

- test case: `output-safety-clear-01`
- field: `result.items[0].recommended_action`

This does not affect classification, categories, action, counts, overall status, or evaluator results. The frozen expected file remains unchanged to preserve the approved validation history.

## 11. Known Limits

- This is a rule-based technical spike, not a production approval.
- It does not guarantee complete legal expression safety.
- It does not cover every Korean expression variant.
- It is not a substitute for legal review.
- It does not validate real contract documents.
- It does not approve external AI transmission.
- More fixtures and expert review are required before product use.
- PR-6 remains responsible for provider policy review and the final v0.2.1 technical decision.

## 12. Final Decision

- PR-5 technical validation: `PASS`
- Product operation approval: `No`
- External AI transmission approval: `No`
- Real contract use approval: `No`
- Real personal data use approval: `No`
- Expert review release approval: `No`
