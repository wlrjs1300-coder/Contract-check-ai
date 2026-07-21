from dataclasses import FrozenInstanceError

import pytest

from backend.app.services.analysis_provider import (
    AnalysisProviderInput,
    SyntheticAnalysisProvider,
)


def test_synthetic_provider_returns_expected_result() -> None:
    provider_input = AnalysisProviderInput(
        reference_id="document-id:clause:1",
        masked_text="Synthetic clause body.",
    )

    provider = SyntheticAnalysisProvider()

    result = provider.analyze_clause(provider_input)

    assert result.reference_id == provider_input.reference_id
    assert result.display_label == "추가 확인"
    assert result.summary == "Synthetic provider result."
    assert result.expert_review_recommended is False

    result.validate()


def test_analysis_provider_input_is_immutable() -> None:
    provider_input = AnalysisProviderInput(
        reference_id="document-id:clause:1",
        masked_text="Masked clause body.",
    )

    assert provider_input.reference_id == "document-id:clause:1"
    assert provider_input.masked_text == "Masked clause body."

    with pytest.raises(FrozenInstanceError):
        provider_input.masked_text = "Changed clause body."
