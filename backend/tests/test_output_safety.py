import json
from pathlib import Path
from typing import Any

from backend.app.services.output_safety import check_output


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PATH = (
    REPO_ROOT
    / "spikes"
    / "v0.2.1-core-validation"
    / "data"
    / "fixtures"
    / "output-safety-expected.v0.2.sample.json"
)

FORBIDDEN_RESULT_FIELDS = {
    "text",
    "raw_text",
    "value",
    "source_value",
    "matched_text",
}


def _read_utf8_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()

    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")

    loaded = json.loads(data.decode("utf-8"))

    if not isinstance(loaded, dict):
        raise ValueError("JSON root must be an object.")

    return loaded


def test_output_safety_matches_frozen_expectations() -> None:
    expected = _read_utf8_json(EXPECTED_PATH)

    passed_cases = 0
    evaluated_field_count = 0
    allowed_count = 0
    violation_count = 0
    review_count = 0

    for case in expected["test_cases"]:
        fixture_path = REPO_ROOT / case["source_fixture"]
        fixture = _read_utf8_json(fixture_path)
        actual = check_output(fixture)

        assert actual["test_case_id"] == case["test_case_id"]
        assert (
            actual["overall_status"]
            == case["expected_overall_status"]
        )
        assert (
            actual["violation_count"]
            == case["expected_violation_count"]
        )
        assert (
            actual["allowed_count"]
            == case["expected_allowed_count"]
        )
        assert (
            actual["review_count"]
            == case["expected_review_count"]
        )
        assert (
            actual["evaluated_field_count"]
            == case["expected_total_evaluated_field_count"]
        )
        assert (
            actual["manual_review_required"]
            == case["expected_manual_review_required"]
        )

        expected_by_path = {
            item["field_path"]: item
            for item in case["field_expectations"]
        }
        actual_by_path = {
            item["field_path"]: item
            for item in actual["field_results"]
        }

        assert actual_by_path.keys() == expected_by_path.keys()

        for field_path, expected_field in expected_by_path.items():
            actual_field = actual_by_path[field_path]

            assert (
                actual_field["text_role"]
                == expected_field["text_role"]
            )
            assert (
                actual_field["classification"]
                == expected_field["expected_classification"]
            )
            assert (
                actual_field["categories"]
                == expected_field["expected_categories"]
            )
            assert (
                actual_field["action"]
                == expected_field["expected_action"]
            )
            assert not (
                FORBIDDEN_RESULT_FIELDS
                & actual_field.keys()
            )

        passed_cases += 1
        evaluated_field_count += actual["evaluated_field_count"]
        allowed_count += actual["allowed_count"]
        violation_count += actual["violation_count"]
        review_count += actual["review_count"]

    assert passed_cases == 4
    assert evaluated_field_count == 48
    assert allowed_count == 30
    assert violation_count == 15
    assert review_count == 3
