from __future__ import annotations

import json
import stat
from pathlib import Path

import requests
from fastapi.testclient import TestClient

from astro_abm_api.main import app


def preset_payload(**updates):
    payload = {
        "name": "Local Gemini",
        "provider": "openai_compatible",
        "real_enabled": False,
        "base_url": "https://llm.local/v1",
        "model": "local-model",
        "api_key": "local-secret-key",
        "worldline_provider": "llm",
        "chunk_size_days": 3,
        "call_delay_seconds": 0,
        "timeout_seconds": 120,
        "max_output_tokens": 5000,
        "custom_user_prompt": "Use supplied context only.",
        "default_language": "zh-Hant",
    }
    payload.update(updates)
    return payload


def scenario_payload():
    return {
        "title": "Preset regeneration smoke",
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "assets": ["BTC"],
        "agent_ids": ["crypto_retail_fomo"],
        "llm_provider": "mock",
        "visibility": "private",
        "language": "zh-Hant",
        "worldline_provider": "deterministic_mock",
    }


def test_local_llm_preset_crud_redacts_key(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "local-config"
    monkeypatch.setenv("ASTRO_ABM_LOCAL_CONFIG_DIR", str(config_dir))
    client = TestClient(app)

    created_response = client.post("/llm/presets", json=preset_payload())
    assert created_response.status_code == 200
    created = created_response.json()
    preset_id = created["preset_id"]
    assert created["has_api_key"] is True
    assert "api_key" not in created
    assert "local-secret-key" not in created_response.text

    store_path = config_dir / "llm_presets.json"
    assert store_path.exists()
    assert stat.S_IMODE(store_path.stat().st_mode) == 0o600
    assert "local-secret-key" in store_path.read_text(encoding="utf-8")

    listed = client.get("/llm/presets")
    assert listed.status_code == 200
    assert listed.json()[0]["has_api_key"] is True
    assert "local-secret-key" not in listed.text

    updated_payload = preset_payload(name="Updated local preset", api_key=None)
    updated = client.put(f"/llm/presets/{preset_id}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated local preset"
    assert updated.json()["has_api_key"] is True

    tested = client.post(f"/llm/presets/{preset_id}/test")
    assert tested.status_code == 200
    assert tested.json()["dry_run"] is True
    assert tested.json()["credential_status"] == "stored_local"
    assert "local-secret-key" not in tested.text

    deleted = client.delete(f"/llm/presets/{preset_id}")
    assert deleted.status_code == 200
    assert client.get("/llm/presets").json() == []


def test_worldline_regeneration_uses_local_preset_without_saving_key(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_LOCAL_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    monkeypatch.delenv("ASTRO_ABM_LLM_API_KEY", raising=False)
    authorization_headers: list[str] = []

    valid_payload = {
        "summary": "Preset-backed worldline chunk.",
        "days": [
            {
                "date": "2026-07-01",
                "agent_events": [
                    {
                        "agent_id": "crypto_retail_fomo",
                        "what_happened": "The simulated group reviewed narrative pressure.",
                        "why_it_happened": "The supplied scenario context was used.",
                        "impact_on_tomorrow": "The next simulated state remains under review.",
                        "impact_scores": {
                            "sentiment_delta": 0,
                            "narrative_pressure_delta": 1,
                            "leverage_pressure_delta": 0,
                            "liquidity_pressure_delta": 0,
                            "volatility_pressure_delta": 0,
                            "stress_pressure_delta": 0,
                        },
                        "confidence": "low",
                        "caveats": ["scenario rehearsal only"],
                    }
                ],
                "causal_links": [],
                "next_day_update": "End of simulated horizon.",
                "world_state_after": {},
            }
        ],
        "caveats": [],
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(valid_payload)}}]}

    def fake_post(*args, **kwargs):
        authorization_headers.append(kwargs["headers"].get("Authorization", ""))
        return Response()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fake_post)
    client = TestClient(app)
    preset = client.post(
        "/llm/presets",
        json=preset_payload(real_enabled=True, call_delay_seconds=0),
    ).json()
    report = client.post("/scenarios", json=scenario_payload()).json()

    response = client.post(
        f"/scenarios/{report['scenario_id']}/worldline/regenerate-from",
        json={"start_chunk_index": 0, "preset_id": preset["preset_id"]},
    )

    assert response.status_code == 200
    body = response.json()
    worldline = body["report"]["worldline_simulation"]
    assert body["regeneration_status"] == "completed"
    assert body["llm_completed_chunk_count"] == 1
    assert body["fallback_chunk_count"] == 0
    assert body["skipped_chunk_count"] == 0
    assert worldline["generation_config"]["preset_id"] == preset["preset_id"]
    assert worldline["generation_config"]["preset_name"] == "Local Gemini"
    assert worldline["generation_config"]["credential_status"] == "stored_local"
    assert authorization_headers == ["Bearer local-secret-key"]
    scenario_path = tmp_path / "scenarios" / f"{report['scenario_id']}.json"
    assert "local-secret-key" not in scenario_path.read_text(encoding="utf-8")

    reused_response = client.post(
        f"/scenarios/{report['scenario_id']}/worldline/regenerate-from",
        json={"start_chunk_index": 0},
    )

    assert reused_response.status_code == 200
    reused_worldline = reused_response.json()["report"]["worldline_simulation"]
    assert reused_worldline["generation_config"]["preset_id"] == preset["preset_id"]
    assert authorization_headers == ["Bearer local-secret-key", "Bearer local-secret-key"]
    assert "local-secret-key" not in scenario_path.read_text(encoding="utf-8")


def test_worldline_regeneration_halts_network_after_two_failed_chunks(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_LOCAL_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    calls = 0

    class UnauthorizedResponse:
        def raise_for_status(self):
            response = requests.Response()
            response.status_code = 401
            raise requests.HTTPError("401 Client Error: Unauthorized", response=response)

    def unauthorized_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return UnauthorizedResponse()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", unauthorized_post)
    client = TestClient(app)
    preset = client.post(
        "/llm/presets",
        json=preset_payload(real_enabled=True, chunk_size_days=3),
    ).json()
    payload = scenario_payload()
    payload["end_date"] = "2026-07-10"
    report = client.post("/scenarios", json=payload).json()

    responses = [
        client.post(
            f"/scenarios/{report['scenario_id']}/worldline/regenerate-from",
            json={
                "start_chunk_index": chunk_index,
                "preset_id": preset["preset_id"],
                "regeneration_id": "regen_progress_test",
                "progressive": True,
            },
        )
        for chunk_index in range(4)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert [response.json()["rebuilt_chunk_count"] for response in responses] == [1, 2, 3, 4]
    body = responses[-1].json()
    assert body["regeneration_status"] == "failed_fallback"
    assert body["llm_completed_chunk_count"] == 0
    assert body["fallback_chunk_count"] == 2
    assert body["skipped_chunk_count"] == 2
    assert calls == 2
    worldline = body["report"]["worldline_simulation"]
    assert worldline["status"] == "fallback"
    assert worldline["last_regeneration"]["generation_halted"] is True
    assert worldline["last_regeneration"]["status"] == "failed_fallback"
    assert "status=failed_fallback" in body["report"]["markdown_report"]
    statuses = [item["status"] for item in worldline["provenance"]["chunk_history"]]
    assert statuses == ["fallback", "fallback", "skipped_after_halt", "skipped_after_halt"]


def test_worldline_regeneration_missing_preset_returns_404(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_LOCAL_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    client = TestClient(app)
    report = client.post("/scenarios", json=scenario_payload()).json()

    response = client.post(
        f"/scenarios/{report['scenario_id']}/worldline/regenerate-from",
        json={"start_chunk_index": 0, "preset_id": "missing_preset"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "LLM preset not found"


def test_worldline_regeneration_missing_original_preset_falls_back_safely(
    monkeypatch, tmp_path: Path
) -> None:
    scenario_dir = tmp_path / "scenarios"
    monkeypatch.setenv("ASTRO_ABM_LOCAL_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(scenario_dir))
    client = TestClient(app)
    report = client.post("/scenarios", json=scenario_payload()).json()
    scenario_path = scenario_dir / f"{report['scenario_id']}.json"
    saved = json.loads(scenario_path.read_text(encoding="utf-8"))
    saved["worldline_simulation"]["generation_config"].update(
        {
            "worldline_provider": "llm",
            "llm_provider": "openai_compatible",
            "llm_real_enabled": False,
            "llm_base_url": "http://missing-preset.local/v1",
            "llm_model": "missing-model",
            "preset_id": "deleted_preset",
            "preset_name": "Deleted preset",
            "credential_status": "stored_local",
        }
    )
    scenario_path.write_text(json.dumps(saved), encoding="utf-8")

    response = client.post(
        f"/scenarios/{report['scenario_id']}/worldline/regenerate-from",
        json={"start_chunk_index": 0},
    )

    assert response.status_code == 200
    worldline = response.json()["report"]["worldline_simulation"]
    assert worldline["generation_config"]["credential_status"] == "unavailable"
    assert "Original local LLM preset was unavailable" in " ".join(worldline["caveats"])
