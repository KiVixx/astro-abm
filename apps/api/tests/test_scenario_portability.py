from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from astro_abm_api.main import app


PASSWORD = "correct-horse-battery-staple"


def _payload(visibility: str = "public") -> dict[str, object]:
    return {
        "title": "Portable Worldline",
        "start_date": "2026-07-01",
        "end_date": "2026-07-02",
        "assets": ["BTC"],
        "agent_ids": ["macro_allocator"],
        "llm_provider": "mock",
        "visibility": visibility,
    }


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("astro_abm_csrf") or ""}


def test_export_is_canonical_and_hash_is_stable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    client = TestClient(app)
    report = client.post("/scenarios", json=_payload()).json()

    first = client.get(f"/scenarios/{report['scenario_id']}/export")
    second = client.get(f"/scenarios/{report['scenario_id']}/export")

    assert first.status_code == second.status_code == 200
    assert first.json()["schema_version"] == "astro-abm-worldline-v1"
    assert first.json()["content_hash"] == second.json()["content_hash"]
    assert first.json()["content_hash"].startswith("sha256:")


def test_import_rejects_tampered_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    client = TestClient(app)
    report = client.post("/scenarios", json=_payload()).json()
    envelope = client.get(f"/scenarios/{report['scenario_id']}/export").json()
    tampered = deepcopy(envelope)
    tampered["report"]["title"] = "Tampered"

    rejected = client.post("/scenarios/import", json={"envelope": tampered})

    assert rejected.status_code == 400
    assert "hash mismatch" in rejected.json()["detail"]


def test_import_uses_new_id_and_owner_visibility(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    guest = TestClient(app)
    source = guest.post("/scenarios", json=_payload()).json()
    envelope = guest.get(f"/scenarios/{source['scenario_id']}/export").json()

    user = TestClient(app)
    registered = user.post(
        "/auth/register",
        json={"username": "portable", "password": PASSWORD},
    )
    assert registered.status_code == 201
    imported = user.post(
        "/scenarios/import",
        headers=_csrf(user),
        json={"envelope": envelope, "visibility": "private"},
    )

    assert imported.status_code == 200
    body = imported.json()
    assert body["scenario_id"] != source["scenario_id"]
    assert body["visibility"] == "private"
    assert body["provenance"]["import"]["source_content_hash"] == envelope["content_hash"]
    assert guest.get(f"/scenarios/{body['scenario_id']}").status_code == 404
    assert user.get(f"/scenarios/{body['scenario_id']}").status_code == 200


def test_guest_import_is_forced_public(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    source_client = TestClient(app)
    source = source_client.post("/scenarios", json=_payload()).json()
    envelope = source_client.get(f"/scenarios/{source['scenario_id']}/export").json()
    importer = TestClient(app)

    imported = importer.post(
        "/scenarios/import",
        json={"envelope": envelope, "visibility": "private"},
    )

    assert imported.status_code == 200
    assert imported.json()["visibility"] == "public"
