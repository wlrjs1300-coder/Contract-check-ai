from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from fastapi import Request

from backend.app.core.proxy_config import ProxyConfig


MAX_FORWARDED_FOR_LENGTH = 512
MAX_FORWARDED_HOPS = 8


@dataclass(frozen=True)
class ClientContext:
    peer_ip: str
    client_ip: str
    scheme: str
    forwarded_used: bool


def _peer_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    try:
        return ipaddress.ip_address(request.client.host).compressed
    except ValueError:
        return "unknown"


def _forwarded_chain(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return ()
    if len(value) > MAX_FORWARDED_FOR_LENGTH:
        return None
    raw_items = value.split(",")
    if not raw_items or len(raw_items) > MAX_FORWARDED_HOPS:
        return None

    chain: list[str] = []
    for item in raw_items:
        candidate = item.strip()
        if not candidate:
            return None
        try:
            chain.append(ipaddress.ip_address(candidate).compressed)
        except ValueError:
            return None
    return tuple(chain)


def _forwarded_client_ip(
    chain: tuple[str, ...],
    *,
    peer_ip: str,
    config: ProxyConfig,
) -> str:
    for candidate in reversed(chain):
        if not config.is_trusted_proxy(candidate):
            return candidate
    return chain[0] if chain else peer_ip


def build_client_context(request: Request, config: ProxyConfig) -> ClientContext:
    peer_ip = _peer_ip(request)
    direct_scheme = request.scope.get("scheme", "http")
    if direct_scheme not in {"http", "https"}:
        direct_scheme = "http"

    if not (
        config.trust_proxy_headers
        and peer_ip != "unknown"
        and config.is_trusted_proxy(peer_ip)
    ):
        return ClientContext(
            peer_ip=peer_ip,
            client_ip=peer_ip,
            scheme=direct_scheme,
            forwarded_used=False,
        )

    chain = _forwarded_chain(request.headers.get("x-forwarded-for"))
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if (
        chain is None
        or not chain
        or forwarded_proto is None
        or forwarded_proto.strip().lower() not in {"http", "https"}
    ):
        return ClientContext(
            peer_ip=peer_ip,
            client_ip=peer_ip,
            scheme=direct_scheme,
            forwarded_used=False,
        )

    return ClientContext(
        peer_ip=peer_ip,
        client_ip=_forwarded_client_ip(chain, peer_ip=peer_ip, config=config),
        scheme=forwarded_proto.strip().lower(),
        forwarded_used=True,
    )


def normalized_host(request: Request) -> str | None:
    raw_host = request.headers.get("host")
    if raw_host is None or not raw_host.strip() or len(raw_host) > 255:
        return None
    candidate = raw_host.strip()
    if candidate.startswith("["):
        closing = candidate.find("]")
        if closing < 0:
            return None
        host = candidate[1:closing]
        suffix = candidate[closing + 1 :]
        if suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()):
            return None
    else:
        if candidate.count(":") > 1:
            return None
        host = candidate.rsplit(":", 1)[0] if ":" in candidate else candidate
    host = host.lower().rstrip(".")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        return host or None


def is_loopback_peer(context: ClientContext) -> bool:
    try:
        return ipaddress.ip_address(context.peer_ip).is_loopback
    except ValueError:
        return False
