import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.services.pii_masking import (
    detect_and_mask,
    detect_entities,
    normalize_text,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PATH = (
    REPO_ROOT
    / "spikes"
    / "v0.2.1-core-validation"
    / "data"
    / "fixtures"
    / "pii-masking-expected.sample.json"
)

FORBIDDEN_ENTITY_FIELDS = {
    "text",
    "raw_text",
    "value",
    "source_value",
    "matched_text",
}


def _read_utf8(path: Path) -> str:
    data = path.read_bytes()

    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed")

    return data.decode("utf-8")


def _load_expected() -> dict[str, Any]:
    return json.loads(_read_utf8(EXPECTED_PATH))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intervals(
    records: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    return [
        (record["start_offset"], record["end_offset"])
        for record in records
    ]


def _overlap_count(
    left: list[tuple[int, int]],
    right: list[tuple[int, int]],
) -> int:
    count = 0

    for left_start, left_end in left:
        for right_start, right_end in right:
            if max(left_start, right_start) < min(
                left_end,
                right_end,
            ):
                count += 1

    return count


def test_pii_masking_matches_frozen_expectations() -> None:
    expected = _load_expected()

    passed_cases = 0
    actual_entity_count = 0
    expected_entity_count = 0
    exclusion_overlap_count = 0
    residual_entity_count = 0

    for case in expected["test_cases"]:
        source_path = REPO_ROOT / case["source_file"]
        source_text = normalize_text(_read_utf8(source_path))
        actual = detect_and_mask(source_text)

        assert _sha256_text(source_text) == case["source_text_sha256"]
        assert (
            actual["masked_text_sha256"]
            == case["expected_masked_text_sha256"]
        )
        assert (
            actual["document_warnings"]
            == case["expected_document_warnings"]
        )

        actual_entities = actual["entities"]
        expected_entities = case["expected_entities"]

        assert len(actual_entities) == len(expected_entities)

        for actual_entity, expected_entity in zip(
            actual_entities,
            expected_entities,
            strict=True,
        ):
            assert actual_entity["ordinal"] == expected_entity["ordinal"]
            assert (
                actual_entity["entity_type"]
                == expected_entity["entity_type"]
            )
            assert (
                actual_entity["start_offset"]
                == expected_entity["start_offset"]
            )
            assert (
                actual_entity["end_offset"]
                == expected_entity["end_offset"]
            )
            assert (
                actual_entity["source_line_start"]
                == expected_entity["source_line_start"]
            )
            assert (
                actual_entity["source_line_end"]
                == expected_entity["source_line_end"]
            )
            assert (
                actual_entity["mask_token"]
                == expected_entity["expected_mask_token"]
            )
            assert (
                actual_entity["source_hash"]
                == expected_entity["expected_entity_source_hash"]
            )
            assert (
                actual_entity["warnings"]
                == expected_entity["expected_warnings"]
            )
            assert not (
                FORBIDDEN_ENTITY_FIELDS
                & actual_entity.keys()
            )

        exclusions = case["expected_false_positive_exclusions"]
        case_exclusion_overlap = _overlap_count(
            _intervals(actual_entities),
            _intervals(exclusions),
        )
        assert case_exclusion_overlap == 0

        residual_entities = detect_entities(actual["masked_text"])
        assert residual_entities == []

        passed_cases += 1
        actual_entity_count += len(actual_entities)
        expected_entity_count += len(expected_entities)
        exclusion_overlap_count += case_exclusion_overlap
        residual_entity_count += len(residual_entities)

    assert passed_cases == 4
    assert actual_entity_count == 26
    assert expected_entity_count == 26
    assert exclusion_overlap_count == 0
    assert residual_entity_count == 0
