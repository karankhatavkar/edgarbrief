"""Unit tests for client-IP resolution — no network.

A minimal fake stands in for ``fastapi.Request``: ``client_ip`` only reads
``request.headers.get(...)`` (case-insensitive) and ``request.client.host``.
"""

from types import SimpleNamespace

from app.quota import client_ip as mod
from app.quota.client_ip import client_ip


class _Headers:
    """Case-insensitive header lookup, like Starlette's Headers.get."""

    def __init__(self, **headers):
        self._h = {k.lower(): v for k, v in headers.items()}

    def get(self, key):
        return self._h.get(key.lower())


def _request(*, headers=None, peer="10.0.0.9"):
    client = SimpleNamespace(host=peer) if peer is not None else None
    return SimpleNamespace(headers=_Headers(**(headers or {})), client=client)


def _trust(monkeypatch, value: bool) -> None:
    monkeypatch.setattr(mod.settings, "demo_trust_forwarded_for", value)


def test_untrusted_uses_socket_peer_and_ignores_headers(monkeypatch):
    _trust(monkeypatch, False)
    req = _request(headers={"CF-Connecting-IP": "9.9.9.9"}, peer="10.0.0.9")
    assert client_ip(req) == "10.0.0.9"


def test_trusted_prefers_cf_connecting_ip(monkeypatch):
    _trust(monkeypatch, True)
    req = _request(
        headers={"CF-Connecting-IP": "9.9.9.9", "X-Forwarded-For": "1.1.1.1, 2.2.2.2"},
        peer="10.0.0.9",
    )
    assert client_ip(req) == "9.9.9.9"


def test_trusted_falls_back_to_first_forwarded_hop(monkeypatch):
    _trust(monkeypatch, True)
    req = _request(headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2"}, peer="10.0.0.9")
    assert client_ip(req) == "1.1.1.1"


def test_trusted_without_headers_uses_peer(monkeypatch):
    _trust(monkeypatch, True)
    req = _request(headers={}, peer="10.0.0.9")
    assert client_ip(req) == "10.0.0.9"


def test_ipv6_collapsed_to_64_prefix(monkeypatch):
    _trust(monkeypatch, True)
    req = _request(headers={"CF-Connecting-IP": "2001:db8:abcd:1234:5678:9abc:def0:1"})
    assert client_ip(req) == "2001:db8:abcd:1234::"


def test_unparseable_ip_fails_open_to_none(monkeypatch):
    _trust(monkeypatch, True)
    req = _request(headers={"CF-Connecting-IP": "not-an-ip"})
    assert client_ip(req) is None


def test_no_peer_and_no_headers_is_none(monkeypatch):
    _trust(monkeypatch, False)
    req = _request(headers={}, peer=None)
    assert client_ip(req) is None
