from __future__ import annotations

import sqlite3

from fastapi import Request
from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.client_identity import client_ip, client_rate_key


def _payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "assets": ["BTC"],
        "agent_ids": ["macro_allocator"],
        "llm_provider": "mock",
        "visibility": "public",
    }


def test_new_guest_cookie_cannot_bypass_ip_create_limit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_IP_CREATE_RATE_PER_HOUR", "1")
    first = TestClient(app, client=("203.0.113.10", 50000))
    fresh_cookie_jar = TestClient(app, client=("203.0.113.10", 50001))

    assert first.post("/scenarios", json=_payload("First")).status_code == 200
    rejected = fresh_cookie_jar.post("/scenarios", json=_payload("Second"))

    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "3600"
    assert "network rate limit" in rejected.json()["detail"]
    with sqlite3.connect(AuthStore().database_path) as connection:
        guest_count = connection.execute("SELECT COUNT(*) FROM guest_workspaces").fetchone()[0]
    assert guest_count == 1


def test_untrusted_peer_cannot_spoof_forwarded_ip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_IP_CREATE_RATE_PER_HOUR", "1")
    monkeypatch.setenv("ASTRO_ABM_TRUSTED_PROXY_IPS", "127.0.0.1/32")
    first = TestClient(app, client=("203.0.113.10", 50000))
    second = TestClient(app, client=("203.0.113.10", 50001))

    assert first.post(
        "/scenarios",
        headers={"X-Forwarded-For": "198.51.100.1"},
        json=_payload("First"),
    ).status_code == 200
    rejected = second.post(
        "/scenarios",
        headers={"X-Forwarded-For": "198.51.100.2"},
        json=_payload("Second"),
    )

    assert rejected.status_code == 429


def test_trusted_proxy_uses_rightmost_untrusted_forwarded_address(monkeypatch) -> None:
    monkeypatch.setenv("ASTRO_ABM_TRUSTED_PROXY_IPS", "127.0.0.0/8,10.0.0.0/8")
    monkeypatch.setenv("ASTRO_ABM_RATE_LIMIT_SALT", "test-salt")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"198.51.100.20, 10.0.0.8")],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )

    assert client_ip(request) == "198.51.100.20"
    assert client_rate_key(request).startswith("ip_sha256:")
    assert "198.51.100.20" not in client_rate_key(request)


def test_registration_rate_limit_precedes_password_hash(monkeypatch) -> None:
    monkeypatch.setenv("ASTRO_ABM_IP_REGISTER_RATE_PER_HOUR", "1")
    client = TestClient(app, client=("203.0.113.22", 50000))
    payload = {"username": "first-user", "password": "correct-horse-battery-staple"}
    assert client.post("/auth/register", json=payload).status_code == 201

    rejected = client.post(
        "/auth/register",
        json={"username": "second-user", "password": "another-secure-password"},
    )

    assert rejected.status_code == 429
    assert "network rate limit" in rejected.json()["detail"]


def test_scenario_horizon_limit_rejects_before_guest_creation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_MAX_DAYS", "2")
    client = TestClient(app, client=("203.0.113.30", 50000))
    payload = _payload("Too long")
    payload["end_date"] = "2026-07-03"

    rejected = client.post("/scenarios", json=payload)

    assert rejected.status_code == 422
    assert "maximum of 2 days" in rejected.json()["detail"]
    with sqlite3.connect(AuthStore().database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM guest_workspaces").fetchone()[0] == 0


def test_worldline_list_has_bounded_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    client = TestClient(app, client=("203.0.113.31", 50000))
    assert client.post("/scenarios", json=_payload("First")).status_code == 200
    assert client.post("/scenarios", json=_payload("Second")).status_code == 200

    response = client.get("/scenarios?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
