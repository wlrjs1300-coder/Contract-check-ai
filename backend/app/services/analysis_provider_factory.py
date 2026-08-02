from __future__ import annotations

import os

from backend.app.core.runtime_environment import get_app_env
from backend.app.services.analysis_provider import (
    AnalysisProvider,
    DEFAULT_ANALYSIS_PROVIDER,
    ExternalAnalysisProviderUnavailable,
    SyntheticAnalysisProvider,
)
from backend.app.services.fake_analysis_provider import FakeAnalysisProvider


class AnalysisProviderConfigError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def resolve_provider_name() -> str:
    configured = os.getenv("ANALYSIS_PROVIDER", "").strip().lower()
    if configured:
        return configured

    app_env = get_app_env()
    if app_env == "test":
        return "synthetic"
    if app_env == "development":
        return "unavailable"
    if app_env == "pilot":
        return "not_configured"
    if app_env in {"prod", "production"}:
        return "not_configured"
    return "not_configured"


def create_analysis_provider(
    *,
    provider_name: str | None = None,
) -> AnalysisProvider:
    selected = provider_name or resolve_provider_name()
    app_env = get_app_env()
    is_prod = app_env in {"prod", "production"}
    is_pilot = app_env == "pilot"

    if is_pilot and selected != "synthetic":
        raise AnalysisProviderConfigError(
            "analysis_provider_forbidden",
            "configured provider is forbidden in pilot.",
        )

    if selected == "synthetic":
        if is_prod:
            raise AnalysisProviderConfigError(
                "analysis_provider_forbidden",
                "synthetic provider is forbidden in production.",
            )
        return SyntheticAnalysisProvider()
    if selected == "fake":
        if is_prod or is_pilot:
            raise AnalysisProviderConfigError(
                "analysis_provider_forbidden",
                "fake provider is forbidden in production.",
            )
        return FakeAnalysisProvider()
    if selected in {"unavailable", "real_placeholder"}:
        return ExternalAnalysisProviderUnavailable()
    if selected in {"", "default"}:
        return DEFAULT_ANALYSIS_PROVIDER
    if selected == "not_configured":
        raise AnalysisProviderConfigError(
            "analysis_provider_not_configured",
            "no provider configured for this environment.",
        )
    if selected == "real":
        raise AnalysisProviderConfigError(
            "analysis_provider_unavailable",
            "real provider is unavailable.",
        )

    raise AnalysisProviderConfigError(
        "analysis_provider_unknown",
        f"unknown provider '{selected}'",
    )


def is_provider_forbidden_in_env(provider: AnalysisProvider) -> bool:
    provider_name = getattr(provider, "provider_name", "")
    app_env = get_app_env()
    if app_env == "pilot":
        return provider_name != "synthetic"
    return provider_name in {"fake", "synthetic"} and app_env in {
        "production",
        "prod",
    }
