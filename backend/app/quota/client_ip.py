"""Resolve the real client IP for the demo per-IP brake.

Deployment is Cloudflare edge → cloudflared tunnel → uvicorn at localhost:8000,
so ``request.client.host`` is the tunnel, never the visitor. Behind Cloudflare
the canonical visitor IP is the ``CF-Connecting-IP`` header (single value, set by
the edge); ``X-Forwarded-For`` is the portable fallback (the first hop is the
client). Both are only trusted when ``demo_trust_forwarded_for`` is on — off, a
client could spoof the header and dodge the cap, so we use the socket peer.

IPv6 is normalized to its /64 prefix: a single host is handed a whole /64, so
without this it could rotate addresses within its allocation to defeat the cap.
"""

import ipaddress

from fastapi import Request

from app.config import settings


def client_ip(request: Request) -> str | None:
    """Best-effort client IP, or ``None`` if it can't be determined (fail-open)."""
    raw = _raw_ip(request)
    if raw is None:
        return None
    return _normalize(raw)


def _raw_ip(request: Request) -> str | None:
    if settings.demo_trust_forwarded_for:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()  # first hop = original client
    return request.client.host if request.client else None


def _normalize(raw: str) -> str | None:
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return None  # unparseable header value -> fail-open, skip the cap
    if isinstance(addr, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{addr}/64", strict=False).network_address)
    return str(addr)
