from __future__ import annotations

import pytest
from backend.app.services.analysis_provider_factory import (
    AnalysisProviderConfigError,
    create_analysis_provider,
    resolve_provider_name,
)
from backend.app.services.fake_analysis_provider import FakeAnalysisProvider


def test_resolve_provider_name_default_test_environment() -> None:
    assert resolve_provider_name() == "synthetic"


def test_factory_selects_fake_in_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ANALYSIS_PROVIDER", "fake")

    provider = create_analysis_provider()
    assert isinstance(provider, FakeAnalysisProvider)


def test_factory_forbids_fake_and_synthetic_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(AnalysisProviderConfigError) as fake_exc:
        create_analysis_provider(provider_name="fake")
    assert fake_exc.value.code == "analysis_provider_forbidden"

    with pytest.raises(AnalysisProviderConfigError) as syn_exc:
        create_analysis_provider(provider_name="synthetic")
    assert syn_exc.value.code == "analysis_provider_forbidden"


def test_factory_not_configured_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(AnalysisProviderConfigError) as exc:
        create_analysis_provider()

    assert exc.value.code == "analysis_provider_not_configured"


def test_factory_unknown_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    with pytest.raises(AnalysisProviderConfigError) as exc:
        create_analysis_provider(provider_name="unknown")

    assert exc.value.code == "analysis_provider_unknown"


def test_factory_development_defaults_to_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    provider = create_analysis_provider()
    assert provider.provider_name == "unavailable"
