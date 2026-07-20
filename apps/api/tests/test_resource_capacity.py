from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from fastapi import HTTPException

from astro_abm_api.main import app
from astro_abm_api.services.auth_store import AuthStore
from astro_abm_api.services.generation_capacity import generation_capacity
from astro_abm_api.services.scenario_access import ScenarioActor


def _payload(title: str, *, end_date: str = "2026-07-01") -> dict[str, object]:
    return {
        "title": title,
        "start_date": "2026-07-01",
        "end_date": end_date,
        "assets": ["BTC"],
        "agent_ids": ["macro_allocator"],
        "llm_provider": "mock",
        "visibility": "public",
    }


def test_request_body_limit_rejects_before_route_and_keeps_cors(monkeypatch) -> None:
    monkeypatch.setenv("ASTRO_ABM_MAX_REQUEST_BODY_BYTES", "1024")
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        content=b"x" * 2048,
        headers={
            "Content-Type": "application/json",
            "Origin": "http://127.0.0.1:3000",
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large", "max_bytes": 1024}
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_global_report_count_stops_new_worldlines(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "scenarios"
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_STORE_MAX_REPORTS", "1")
    client = TestClient(app)

    assert client.post("/scenarios", json=_payload("First")).status_code == 200
    rejected = client.post("/scenarios", json=_payload("Second"))

    assert rejected.status_code == 507
    assert rejected.json()["category"] == "report_count"
    assert rejected.headers["Retry-After"] == "3600"
    assert len(list(output_dir.glob("*.json"))) == 1


def test_single_report_size_limit_stops_oversized_worldline(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "scenarios"
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_MAX_REPORT_BYTES", str(64 * 1024))
    client = TestClient(app)

    rejected = client.post(
        "/scenarios",
        json=_payload("Oversized", end_date="2026-09-30"),
    )

    assert rejected.status_code == 507
    assert rejected.json()["category"] == "single_report_bytes"
    assert list(output_dir.glob("*.json")) == []


def test_generation_lease_enforces_global_capacity_and_releases(monkeypatch) -> None:
    store = AuthStore()
    first = store.try_acquire_generation_lease(
        actor_type="guest",
        actor_id="one",
        global_limit=1,
        actor_limit=1,
        lease_seconds=60,
    )
    assert first
    assert store.try_acquire_generation_lease(
        actor_type="guest",
        actor_id="two",
        global_limit=1,
        actor_limit=1,
        lease_seconds=60,
    ) is None

    store.release_generation_lease(first)
    second = store.try_acquire_generation_lease(
        actor_type="guest",
        actor_id="two",
        global_limit=1,
        actor_limit=1,
        lease_seconds=60,
    )
    assert second
    store.release_generation_lease(second)


def test_generation_capacity_returns_fast_retryable_503(monkeypatch) -> None:
    monkeypatch.setenv("ASTRO_ABM_GENERATION_GLOBAL_CONCURRENCY", "1")
    store = AuthStore()
    held = store.try_acquire_generation_lease(
        actor_type="guest",
        actor_id="held",
        global_limit=1,
        actor_limit=1,
        lease_seconds=60,
    )
    assert held

    try:
        with generation_capacity(ScenarioActor("guest", "waiting", None), store):
            raise AssertionError("capacity should not be acquired")
    except HTTPException as error:
        assert error.status_code == 503
        assert error.headers == {"Retry-After": "5"}
    finally:
        store.release_generation_lease(held)


def test_short_rate_window_does_not_delete_daily_limit_history() -> None:
    store = AuthStore()
    now = datetime.now(UTC)
    with store._connect() as connection:
        connection.execute(
            """
            INSERT INTO operation_events (actor_type, actor_id, operation, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "network",
                "ip_sha256:test",
                "scenario_create_ip_daily",
                (now - timedelta(hours=2)).isoformat(),
            ),
        )

    assert store.record_operation_if_allowed(
        actor_type="network",
        actor_id="ip_sha256:test",
        operation="scenario_create_ip_hourly",
        limit=10,
        window_seconds=3600,
    )

    with sqlite3.connect(store.database_path) as connection:
        daily_events = connection.execute(
            """
            SELECT COUNT(*) FROM operation_events
            WHERE actor_id = ? AND operation = ?
            """,
            ("ip_sha256:test", "scenario_create_ip_daily"),
        ).fetchone()[0]
    assert daily_events == 1


def test_operational_cleanup_removes_only_expired_state() -> None:
    store = AuthStore()
    now = datetime.now(UTC)
    with store._connect() as connection:
        connection.executemany(
            """
            INSERT INTO operation_events (actor_type, actor_id, operation, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("network", "old", "test", (now - timedelta(days=3)).isoformat()),
                ("network", "recent", "test", now.isoformat()),
            ],
        )
        connection.executemany(
            """
            INSERT INTO generation_leases (
                lease_id, actor_type, actor_id, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "expired",
                    "guest",
                    "one",
                    (now - timedelta(minutes=2)).isoformat(),
                    (now - timedelta(minutes=1)).isoformat(),
                ),
                (
                    "active",
                    "guest",
                    "two",
                    now.isoformat(),
                    (now + timedelta(minutes=5)).isoformat(),
                ),
            ],
        )

    removed = store.cleanup_operational_state(max_event_age_seconds=172800)

    assert removed["operation_events"] == 1
    assert removed["generation_leases"] == 1
    status = store.abuse_protection_status()
    assert status["operation_events"] == 1
    assert status["active_generation_leases"] == 1


def test_rate_limiter_fails_closed_quickly_when_database_is_locked(monkeypatch) -> None:
    store = AuthStore()
    store.abuse_protection_status()
    monkeypatch.setenv("ASTRO_ABM_RATE_LIMIT_DB_TIMEOUT_SECONDS", "0.05")
    locker = sqlite3.connect(store.database_path)
    locker.execute("BEGIN IMMEDIATE")
    try:
        started = time.perf_counter()
        allowed = store.record_operation_if_allowed(
            actor_type="network",
            actor_id="ip_sha256:locked",
            operation="scenario_create_hour",
            limit=10,
            window_seconds=3600,
        )
        elapsed = time.perf_counter() - started
    finally:
        locker.rollback()
        locker.close()

    assert allowed is False
    assert elapsed < 0.5
