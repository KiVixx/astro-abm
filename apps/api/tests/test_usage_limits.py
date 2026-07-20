from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.services.auth_store import AuthStore


def _payload(title: str = "Limit test") -> dict[str, object]:
    return {
        "title": title,
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "assets": ["BTC"],
        "agent_ids": ["macro_allocator"],
        "llm_provider": "mock",
        "visibility": "public",
    }


def test_guest_scenario_quota_returns_clear_429(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_GUEST_SCENARIO_QUOTA", "1")
    client = TestClient(app)

    assert client.post("/scenarios", json=_payload("First")).status_code == 200
    rejected = client.post("/scenarios", json=_payload("Second"))

    assert rejected.status_code == 429
    assert rejected.json()["detail"] == "worldline storage quota reached"


def test_create_rate_limit_is_recorded_per_guest(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_GUEST_SCENARIO_QUOTA", "10")
    monkeypatch.setenv("ASTRO_ABM_CREATE_RATE_PER_HOUR", "1")
    client = TestClient(app)

    assert client.post("/scenarios", json=_payload("First")).status_code == 200
    rejected = client.post("/scenarios", json=_payload("Second"))

    assert rejected.status_code == 429
    assert "rate limit" in rejected.json()["detail"]


def test_expired_guest_cleanup_removes_owned_report(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "scenarios"
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(output_dir))
    client = TestClient(app)
    report = client.post("/scenarios", json=_payload()).json()
    database_path = AuthStore().database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE guest_workspaces SET expires_at = '2000-01-01T00:00:00+00:00'")

    store = AuthStore()
    ids = store.expired_guest_scenario_ids()
    assert ids == [report["scenario_id"]]
    assert (output_dir / f"{report['scenario_id']}.json").exists()

    from astro_abm_api.services.guest_cleanup import cleanup_expired_guest_worldlines

    assert cleanup_expired_guest_worldlines() == (1, 1)
    assert not (output_dir / f"{report['scenario_id']}.json").exists()
    assert store.expired_guest_scenario_ids() == []
