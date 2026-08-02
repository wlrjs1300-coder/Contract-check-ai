from __future__ import annotations

import pytest

from backend.app.core.proxy_config import (
    ProxyConfigurationError,
    get_proxy_config,
)


def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENV",
        "TRUST_PROXY_HEADERS",
        "TRUSTED_PROXY_CIDRS",
        "REQUIRE_HTTPS",
        "ALLOWED_HOSTS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_non_production_defaults_do_not_trust_forwarded_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_proxy_env(monkeypatch)
    config = get_proxy_config()
    assert not config.trust_proxy_headers
    assert not config.trusted_proxy_networks
    assert not config.require_https
    assert not config.allowed_hosts


def test_proxy_networks_and_hosts_are_trimmed_deduplicated_and_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv(
        "TRUSTED_PROXY_CIDRS",
        "192.0.2.4/24, 192.0.2.0/24, 2001:db8::1/64",
    )
    monkeypatch.setenv(
        "ALLOWED_HOSTS",
        " API.EXAMPLE.INVALID. ,api.example.invalid,2001:db8::1",
    )
    config = get_proxy_config()
    assert tuple(network.with_prefixlen for network in config.trusted_proxy_networks) == (
        "192.0.2.0/24",
        "2001:db8::/64",
    )
    assert config.allowed_hosts == ("api.example.invalid", "2001:db8::1")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRUSTED_PROXY_CIDRS", "*"),
        ("TRUSTED_PROXY_CIDRS", "192.0.2.0/24,,198.51.100.1"),
        ("TRUSTED_PROXY_CIDRS", "not-an-address"),
        ("ALLOWED_HOSTS", "*"),
        ("ALLOWED_HOSTS", "https://api.example.invalid"),
        ("ALLOWED_HOSTS", "api.example.invalid/path"),
    ],
)
def test_invalid_proxy_network_or_host_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    monkeypatch.setenv(name, value)
    with pytest.raises(ProxyConfigurationError, match="Invalid proxy configuration"):
        get_proxy_config()


def test_trust_enabled_requires_nonempty_networks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    with pytest.raises(ProxyConfigurationError):
        get_proxy_config()


@pytest.mark.parametrize(
    ("missing", "replacement"),
    [
        ("TRUST_PROXY_HEADERS", None),
        ("REQUIRE_HTTPS", None),
        ("REQUIRE_HTTPS", "false"),
        ("ALLOWED_HOSTS", None),
        ("ALLOWED_HOSTS", ""),
    ],
)
def test_production_proxy_contract_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
    replacement: str | None,
) -> None:
    _clear_proxy_env(monkeypatch)
    values = {
        "APP_ENV": "production",
        "TRUST_PROXY_HEADERS": "false",
        "TRUSTED_PROXY_CIDRS": "",
        "REQUIRE_HTTPS": "true",
        "ALLOWED_HOSTS": "api.example.invalid",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    if replacement is None:
        monkeypatch.delenv(missing)
    else:
        monkeypatch.setenv(missing, replacement)
    with pytest.raises(ProxyConfigurationError):
        get_proxy_config()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRUST_PROXY_HEADERS", None),
        ("REQUIRE_HTTPS", None),
        ("REQUIRE_HTTPS", "false"),
        ("ALLOWED_HOSTS", None),
        ("ALLOWED_HOSTS", "*"),
        ("TRUST_PROXY_HEADERS", "invalid"),
    ],
)
def test_pilot_proxy_contract_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str | None,
) -> None:
    _clear_proxy_env(monkeypatch)
    values = {
        "APP_ENV": "pilot",
        "TRUST_PROXY_HEADERS": "false",
        "TRUSTED_PROXY_CIDRS": "",
        "REQUIRE_HTTPS": "true",
        "ALLOWED_HOSTS": "pilot.example.invalid",
    }
    for key, configured in values.items():
        monkeypatch.setenv(key, configured)
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(ProxyConfigurationError):
        get_proxy_config()
