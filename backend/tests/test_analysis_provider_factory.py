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


def test_pilot_requires_explicit_synthetic_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.delenv("ANALYSIS_PROVIDER", raising=False)
    assert resolve_provider_name() == "not_configured"
    with pytest.raises(AnalysisProviderConfigError) as exc_info:
        create_analysis_provider()
    assert exc_info.value.code == "analysis_provider_forbidden"


def test_pilot_allows_only_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    monkeypatch.setenv("ANALYSIS_PROVIDER", "synthetic")
    assert create_analysis_provider().provider_name == "synthetic"


@pytest.mark.parametrize(
    "provider_name",
    [
        "fake",
        "default",
        "unavailable",
        "real_placeholder",
        "not_configured",
        "real",
        "unknown",
    ],
)
def test_pilot_rejects_every_non_synthetic_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
) -> None:
    monkeypatch.setenv("APP_ENV", "pilot")
    with pytest.raises(AnalysisProviderConfigError) as exc_info:
        create_analysis_provider(provider_name=provider_name)
    assert exc_info.value.code == "analysis_provider_forbidden"
