from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.models.marksix import MarkSixLlmWorldlineRequest
from astro_abm_api.services import marksix_llm


def _request() -> MarkSixLlmWorldlineRequest:
    return MarkSixLlmWorldlineRequest(
        base_url="https://llm.example/v1", model="test-model", api_key="secret-test-key",
    )


def _patch_context(monkeypatch) -> None:
    monkeypatch.setattr(marksix_llm, "planetary_snapshot", lambda value: {
        "date": value.isoformat(), "planets": [{"body": "Mercury", "longitude_deg": 12.3}],
        "moon_phase_zone": "full_moon_zone",
    })
    monkeypatch.setattr(marksix_llm, "_history_context", lambda request, snapshot: {
        "context_type": request.astro_context_type, "body": request.astro_body,
        "condition": request.astro_condition, "sample_counts": {"condition_draws": 20},
        "number_statistics": [],
    })


def test_llm_marksix_guess_validates_and_redacts_key(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(marksix_llm, "_call_openai_compatible", lambda *args, **kwargs: json.dumps({
        "numbers": [1, 2, 3, 4, 5, 6], "extra_number": 7,
        "rationale": "Entertainment comparison.", "confidence": "low", "caveats": ["No predictive edge."],
    }))
    result = marksix_llm.generate_marksix_llm_worldline(_request())
    assert result["worldline"]["draws"][0]["numbers"] == [1, 2, 3, 4, 5, 6]
    assert result["prompt_context"]["credential_status"] == "redacted"
    assert "secret-test-key" not in json.dumps(result)


def test_llm_marksix_guess_rejects_duplicate_or_out_of_range_numbers(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(marksix_llm, "_call_openai_compatible", lambda *args, **kwargs: json.dumps({
        "numbers": [1, 1, 3, 4, 5, 60], "extra_number": 7,
    }))
    with pytest.raises(ValueError, match="seven unique"):
        marksix_llm.generate_marksix_llm_worldline(_request())


def test_llm_marksix_endpoint_returns_safe_validated_payload(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(marksix_llm, "_call_openai_compatible", lambda *args, **kwargs: json.dumps({
        "numbers": [8, 9, 10, 11, 12, 13], "extra_number": 14,
        "rationale": "歷史比較只作娛樂。", "confidence": "低", "caveats": [],
    }))
    response = TestClient(app).post("/marksix/llm-worldlines", json={
        "base_url": "https://llm.example/v1", "model": "test-model", "api_key": "never-return-me",
    })
    assert response.status_code == 200
    assert response.json()["worldline"]["draws"][0]["extra_number"] == 14
    assert response.json()["public_library_id"].startswith("marksix-public-")
    assert "never-return-me" not in response.text

    library = TestClient(app).get("/marksix/llm-worldlines")
    assert library.status_code == 200
    assert len(library.json()) == 1
    assert library.json()[0]["library_id"] == response.json()["public_library_id"]
    assert library.json()[0]["numbers"] == [8, 9, 10, 11, 12, 13]
    assert "base_url" not in library.text
    assert "api_key" not in library.text
    assert "never-return-me" not in library.text
    assert TestClient(app).get("/marksix/llm-worldlines?limit=1&offset=1").json() == []

    detail = TestClient(app).get(f"/marksix/llm-worldlines/{response.json()['public_library_id']}")
    assert detail.status_code == 200
    assert detail.json()["rationale"] == "歷史比較只作娛樂。"
    assert "credential_status" not in detail.json()["prompt_context"]
    assert "llm.example" not in detail.text


def test_invalid_llm_output_is_not_added_to_public_library(monkeypatch) -> None:
    _patch_context(monkeypatch)
    monkeypatch.setattr(marksix_llm, "_call_openai_compatible", lambda *args, **kwargs: "not-json")
    client = TestClient(app)
    response = client.post("/marksix/llm-worldlines", json={
        "base_url": "https://llm.example/v1", "model": "test-model", "api_key": "secret",
    })
    assert response.status_code == 502
    assert client.get("/marksix/llm-worldlines").json() == []


def test_public_llm_worldline_missing_record_returns_404() -> None:
    response = TestClient(app).get("/marksix/llm-worldlines/missing")
    assert response.status_code == 404


def test_history_comparison_matches_next_draw_planet_phase(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def analyze(*, body: str, condition: str):
        captured.update(body=body, condition=condition)
        return {
            "context_type": "planet_motion", "body": body, "condition": condition,
            "rule_era": "current_6_of_49", "start_date": "2002-07-04", "end_date": "2026-09-05",
            "total_draws": 10, "condition_draws": 2, "baseline_draws": 8,
            "numbers": [{"number": value, "lift": 1.0, "rate_difference": 0.0, "q_value_fdr": 1.0} for value in range(1, 50)],
        }

    monkeypatch.setattr(marksix_llm, "analyze_retrograde_numbers", analyze)
    marksix_llm._history_context(_request(), {
        "planets": [{"body": "Mercury", "motion_phase": "post_station"}],
        "moon_phase_zone": "waning_other",
    })
    assert captured == {"body": "Mercury", "condition": "post_station"}
