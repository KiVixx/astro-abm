from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.services.auth_store import AuthStore


PASSWORD = "correct-horse-battery-staple"


def _scenario_payload(*, visibility: str = "private") -> dict[str, object]:
    return {
        "title": "Ownership test",
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "assets": ["BTC"],
        "agent_ids": ["macro_allocator"],
        "llm_provider": "mock",
        "visibility": visibility,
    }


def _client(monkeypatch, tmp_path) -> tuple[TestClient, str]:
    database_path = tmp_path / "accounts.sqlite3"
    monkeypatch.setenv("ASTRO_ABM_ACCOUNTS_DB_PATH", str(database_path))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.setenv("ASTRO_ABM_ENV", "development")
    return TestClient(app), str(database_path)


def _register(client: TestClient, username: str = "alice"):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "password": PASSWORD,
            "display_name": "Alice",
        },
    )


def test_register_creates_extensible_identity_and_session(monkeypatch, tmp_path) -> None:
    client, database_path = _client(monkeypatch, tmp_path)

    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == "alice"
    assert body["user"]["identity_providers"] == ["password"]
    assert body["password_recovery_available"] is False
    assert body["csrf_token"]
    assert client.cookies.get("astro_abm_session")

    connection = sqlite3.connect(database_path)
    password_hash = connection.execute(
        "SELECT credential_hash FROM auth_identities WHERE provider = 'password'"
    ).fetchone()[0]
    session_hash = connection.execute("SELECT session_hash FROM sessions").fetchone()[0]
    assert password_hash.startswith("$argon2")
    assert PASSWORD not in password_hash
    assert client.cookies.get("astro_abm_session") != session_hash
    assert len(session_hash) == 64


def test_login_failure_is_generic_and_success_restores_session(monkeypatch, tmp_path) -> None:
    client, _ = _client(monkeypatch, tmp_path)
    assert _register(client).status_code == 201
    csrf_token = client.cookies.get("astro_abm_csrf")
    assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf_token}).status_code == 200

    missing = client.post(
        "/auth/login", json={"username": "missing", "password": "wrong-password"}
    )
    wrong = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong-password"}
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["detail"] == wrong.json()["detail"] == "invalid username or password"

    logged_in = client.post(
        "/auth/login", json={"username": "ALICE", "password": PASSWORD}
    )
    assert logged_in.status_code == 200
    assert client.get("/auth/me").json()["user"]["username"] == "alice"


def test_logout_requires_csrf_and_revokes_session(monkeypatch, tmp_path) -> None:
    client, _ = _client(monkeypatch, tmp_path)
    register = _register(client)
    assert register.status_code == 201

    rejected = client.post("/auth/logout")
    assert rejected.status_code == 403
    assert client.get("/auth/me").json()["authenticated"] is True

    csrf_token = client.cookies.get("astro_abm_csrf")
    accepted = client.post("/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert accepted.status_code == 200
    assert client.get("/auth/me").json() == {
        "authenticated": False,
        "user": None,
        "csrf_token": None,
        "password_recovery_available": False,
    }


def test_change_password_revokes_all_sessions(monkeypatch, tmp_path) -> None:
    first, _ = _client(monkeypatch, tmp_path)
    second = TestClient(app)
    assert _register(first).status_code == 201
    assert second.post(
        "/auth/login", json={"username": "alice", "password": PASSWORD}
    ).status_code == 200

    csrf_token = first.cookies.get("astro_abm_csrf")
    changed = first.post(
        "/auth/change-password",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "current_password": PASSWORD,
            "new_password": "a-different-secure-password",
        },
    )
    assert changed.status_code == 200
    assert first.get("/auth/me").json()["authenticated"] is False
    assert second.get("/auth/me").json()["authenticated"] is False
    assert first.post(
        "/auth/login", json={"username": "alice", "password": PASSWORD}
    ).status_code == 401
    assert first.post(
        "/auth/login",
        json={"username": "alice", "password": "a-different-secure-password"},
    ).status_code == 200


def test_duplicate_registration_does_not_return_existing_account(monkeypatch, tmp_path) -> None:
    client, _ = _client(monkeypatch, tmp_path)
    assert _register(client).status_code == 201

    duplicate = _register(client)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "account registration unavailable"


def test_registration_validation_rejects_weak_credentials(monkeypatch, tmp_path) -> None:
    client, _ = _client(monkeypatch, tmp_path)

    response = client.post(
        "/auth/register",
        json={"username": "bad name", "password": "short"},
    )

    assert response.status_code == 422


def test_guest_worldline_is_forced_public_and_mutation_stays_with_owner(
    monkeypatch, tmp_path
) -> None:
    owner, _ = _client(monkeypatch, tmp_path)
    observer = TestClient(app)

    created = owner.post("/scenarios", json=_scenario_payload(visibility="private"))

    assert created.status_code == 200
    scenario_id = created.json()["scenario_id"]
    assert created.json()["visibility"] == "public"
    assert observer.get(f"/scenarios/{scenario_id}").status_code == 200
    assert observer.delete(f"/scenarios/{scenario_id}").status_code == 404
    owner_summary = owner.get("/scenarios").json()[0]
    assert owner_summary["is_owner"] is True
    assert owner_summary["can_delete"] is True
    observer_summary = observer.get("/scenarios").json()[0]
    assert observer_summary["is_owner"] is False
    assert observer_summary["can_delete"] is False
    assert owner.delete(f"/scenarios/{scenario_id}").status_code == 200


def test_authenticated_user_can_create_private_worldline(monkeypatch, tmp_path) -> None:
    owner, _ = _client(monkeypatch, tmp_path)
    observer = TestClient(app)
    assert _register(owner).status_code == 201

    created = owner.post("/scenarios", json=_scenario_payload(visibility="private"))

    scenario_id = created.json()["scenario_id"]
    assert created.json()["visibility"] == "private"
    assert owner.get(f"/scenarios/{scenario_id}").status_code == 200
    assert observer.get(f"/scenarios/{scenario_id}").status_code == 404
    assert observer.get("/scenarios").json() == []
    assert owner.get("/scenarios").json()[0]["is_owner"] is True


def test_logged_in_user_can_claim_current_guest_worldlines(monkeypatch, tmp_path) -> None:
    client, _ = _client(monkeypatch, tmp_path)
    created = client.post("/scenarios", json=_scenario_payload(visibility="public"))
    scenario_id = created.json()["scenario_id"]
    assert _register(client).status_code == 201

    before_claim = client.delete(f"/scenarios/{scenario_id}")
    csrf_token = client.cookies.get("astro_abm_csrf")
    claim = client.post(
        "/auth/claim-guest-worldlines",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert before_claim.status_code == 404
    assert claim.status_code == 200
    assert claim.json()["claimed_worldline_count"] == 1
    assert client.delete(f"/scenarios/{scenario_id}").status_code == 200


def test_legacy_visibility_is_read_only_and_private_is_hidden(monkeypatch, tmp_path) -> None:
    guest, _ = _client(monkeypatch, tmp_path)
    public = guest.post("/scenarios", json=_scenario_payload(visibility="public")).json()
    AuthStore().delete_scenario_ownership(public["scenario_id"])

    assert TestClient(app).get(f"/scenarios/{public['scenario_id']}").status_code == 200
    assert guest.delete(f"/scenarios/{public['scenario_id']}").status_code == 404

    user = TestClient(app)
    assert _register(user, "bob").status_code == 201
    private = user.post("/scenarios", json=_scenario_payload(visibility="private")).json()
    AuthStore().delete_scenario_ownership(private["scenario_id"])

    assert user.get(f"/scenarios/{private['scenario_id']}").status_code == 404
