from __future__ import annotations

import hashlib
import ipaddress
import os

from fastapi import Request


TRUSTED_PROXY_IPS_ENV = "ASTRO_ABM_TRUSTED_PROXY_IPS"
RATE_LIMIT_SALT_ENV = "ASTRO_ABM_RATE_LIMIT_SALT"


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted_proxy(peer):
        return _normalized_ip(peer)

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [_normalized_ip(item.strip()) for item in forwarded.split(",") if item.strip()]
    chain.append(_normalized_ip(peer))
    for candidate in reversed(chain):
        if not _is_trusted_proxy(candidate):
            return candidate
    return chain[0] if chain else "unknown"


def client_rate_key(request: Request) -> str:
    salt = os.getenv(RATE_LIMIT_SALT_ENV, "astro-abm-development-rate-limit")
    digest = hashlib.sha256(f"{salt}:{client_ip(request)}".encode("utf-8")).hexdigest()
    return f"ip_sha256:{digest}"


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw in os.getenv(TRUSTED_PROXY_IPS_ENV, "").split(","):
        value = raw.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return networks


def _is_trusted_proxy(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in _trusted_networks())


def _normalized_ip(value: str) -> str:
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        return "unknown"
