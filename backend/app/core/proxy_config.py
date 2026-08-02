from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass

from backend.app.core.runtime_environment import is_strict_environment

class ProxyConfigurationError(RuntimeError):
    """Raised when the ingress trust boundary is invalid."""


_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$"
)


@dataclass(frozen=True)
class ProxyConfig:
    trust_proxy_headers: bool
    trusted_proxy_networks: tuple[
        ipaddress.IPv4Network | ipaddress.IPv6Network, ...
    ]
    require_https: bool
    allowed_hosts: tuple[str, ...]

    def is_trusted_proxy(self, peer_ip: str) -> bool:
        try:
            address = ipaddress.ip_address(peer_ip)
        except ValueError:
            return False
        return any(address in network for network in self.trusted_proxy_networks)


def _is_production() -> bool:
    return is_strict_environment()


def _parse_bool(name: str, *, default: bool, production: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if production:
            raise ProxyConfigurationError("Invalid proxy configuration.")
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    raise ProxyConfigurationError("Invalid proxy configuration.")


def _parse_trusted_proxy_networks(
    value: str | None,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    if value is None or not value.strip():
        return ()

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    seen: set[str] = set()
    for item in value.split(","):
        candidate = item.strip()
        if not candidate or candidate == "*":
            raise ProxyConfigurationError("Invalid proxy configuration.")
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            raise ProxyConfigurationError("Invalid proxy configuration.") from None
        canonical = network.with_prefixlen
        if canonical not in seen:
            seen.add(canonical)
            networks.append(network)
    return tuple(networks)


def _parse_allowed_hosts(value: str | None) -> tuple[str, ...]:
    if value is None or not value.strip():
        return ()

    hosts: list[str] = []
    seen: set[str] = set()
    for item in value.split(","):
        candidate = item.strip().lower().rstrip(".")
        if not candidate or "*" in candidate:
            raise ProxyConfigurationError("Invalid proxy configuration.")
        try:
            normalized = ipaddress.ip_address(candidate).compressed
        except ValueError:
            if not _HOST_PATTERN.fullmatch(candidate):
                raise ProxyConfigurationError("Invalid proxy configuration.") from None
            normalized = candidate
        if normalized not in seen:
            seen.add(normalized)
            hosts.append(normalized)
    return tuple(hosts)


def get_proxy_config(*, enforce_production: bool = True) -> ProxyConfig:
    production = _is_production()
    trust_proxy_headers = _parse_bool(
        "TRUST_PROXY_HEADERS",
        default=False,
        production=production and enforce_production,
    )
    require_https = _parse_bool(
        "REQUIRE_HTTPS",
        default=False,
        production=production and enforce_production,
    )
    trusted_proxy_networks = _parse_trusted_proxy_networks(
        os.getenv("TRUSTED_PROXY_CIDRS")
    )
    allowed_hosts = _parse_allowed_hosts(os.getenv("ALLOWED_HOSTS"))

    if trust_proxy_headers and not trusted_proxy_networks:
        raise ProxyConfigurationError("Invalid proxy configuration.")
    if production and enforce_production and not require_https:
        raise ProxyConfigurationError("Invalid proxy configuration.")
    if production and enforce_production and not allowed_hosts:
        raise ProxyConfigurationError("Invalid proxy configuration.")

    return ProxyConfig(
        trust_proxy_headers=trust_proxy_headers,
        trusted_proxy_networks=trusted_proxy_networks,
        require_https=require_https,
        allowed_hosts=allowed_hosts,
    )
