from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from astro_abm_api.main import app


def scenario_payload() -> dict[str, object]:
    return {
        "title": "BTC ETH Daily Scenario",
        "description": "API test scenario",
        "start_date": "2026-07-01",
        "end_date": "2026-09-30",
        "assets": ["BTC", "ETH"],
        "agent_ids": ["crypto_retail_fomo", "leveraged_trader", "macro_allocator"],
        "llm_provider": "mock",
        "visibility": "private",
    }


def inclusive_day_count(start_date: str, end_date: str) -> int:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    return (end - start).days + 1


def test_list_agents() -> None:
    client = TestClient(app)
    response = client.get("/agents")

    assert response.status_code == 200
    agent_ids = {agent["agent_id"] for agent in response.json()}
    assert "crypto_retail_fomo" in agent_ids
    assert "leveraged_trader" in agent_ids
    assert "macro_allocator" in agent_ids


def test_create_list_and_get_scenario(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    create_response = client.post("/scenarios", json=scenario_payload())

    assert create_response.status_code == 200
    report = create_response.json()
    scenario_id = report["scenario_id"]
    assert report["title"] == "BTC ETH Daily Scenario"
    assert report["daily_context"]["data_layer"] == "daily"
    assert report["scenario_summary"] == report["simulation_summary"]
    assert report["risk_themes"] == report["risks"]
    assert len(report["daily_timeline"]) == inclusive_day_count(
        "2026-07-01", "2026-09-30"
    )
    first_day = report["daily_timeline"][0]
    assert first_day["date"] == "2026-07-01"
    assert first_day["day_index"] == 1
    assert len(first_day["agent_states"]) == len(scenario_payload()["agent_ids"])
    assert "association only" in first_day["disclaimer"]
    assert "scenario rehearsal only" in first_day["disclaimer"]
    assert "not financial advice" in first_day["disclaimer"]
    assert "not a trading signal" in first_day["disclaimer"]
    assert first_day["astro_context"]["intensity"] in {"low", "medium", "high"}
    assert first_day["market_context"]["stress_regime"] in {
        "calm",
        "watchful",
        "elevated",
    }
    assert "association only" in report["disclaimer"]
    assert "scenario rehearsal only" in report["disclaimer"]
    assert "not financial advice" in report["disclaimer"]
    assert "not a trading signal" in report["disclaimer"]
    assert "association only" in report["markdown_report"]
    assert "## Daily Timeline" in report["markdown_report"]
    assert "## 2026-07-01" in report["markdown_report"]
    assert (tmp_path / f"{scenario_id}.json").exists()
    assert (tmp_path / f"{scenario_id}.md").exists()

    list_response = client.get("/scenarios")
    assert list_response.status_code == 200
    summaries = list_response.json()
    assert len(summaries) == 1
    assert summaries[0]["scenario_id"] == scenario_id
    assert summaries[0]["agent_names"] == [
        "Crypto Retail FOMO",
        "Leveraged Trader",
        "Macro Allocator",
    ]
    assert "markdown_report" not in summaries[0]

    get_response = client.get(f"/scenarios/{scenario_id}")
    assert get_response.status_code == 200
    assert get_response.json()["scenario_id"] == scenario_id


def test_no_secret_is_saved_in_scenario_output(monkeypatch, tmp_path: Path) -> None:
    secret = "test-secret-key-should-not-appear"
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ASTRO_ABM_LLM_API_KEY", secret)
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "http://localhost:11434/v1",
            "llm_model": "local-model",
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    scenario_id = response.json()["scenario_id"]
    output_text = (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")
    output_json = json.loads(output_text)
    assert secret not in output_text
    assert "daily_timeline" in output_json
    assert output_json["provenance"]["llm"]["credential_status"] == "redacted"
    assert output_json["provenance"]["llm"]["network_call_performed"] is False


def test_old_scenario_report_without_daily_timeline_loads(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post("/scenarios", json=scenario_payload())
    assert response.status_code == 200
    report = response.json()
    scenario_id = "old_style_report"
    report["scenario_id"] = scenario_id
    report.pop("daily_timeline")
    report.pop("scenario_summary")
    report.pop("risk_themes")
    (tmp_path / f"{scenario_id}.json").write_text(json.dumps(report), encoding="utf-8")

    get_response = client.get(f"/scenarios/{scenario_id}")

    assert get_response.status_code == 200
    loaded = get_response.json()
    assert loaded["scenario_id"] == scenario_id
    assert loaded["daily_timeline"] == []
    assert loaded["scenario_summary"] is None
    assert loaded["risk_themes"] == []


def test_invalid_date_range_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"start_date": "2026-10-01", "end_date": "2026-09-30"})

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 422


def test_unknown_agent_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload["agent_ids"] = ["crypto_retail_fomo", "unknown_agent"]

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 400
    assert "unknown_agent" in response.json()["detail"]


def test_path_traversal_scenario_id_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.get("/scenarios/../secret")

    assert response.status_code in {400, 404}


def test_llm_test_is_dry_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    mock_response = client.post("/llm/test", json={"provider": "mock"})
    configured_response = client.post(
        "/llm/test",
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "model": "local-model",
            "api_key": "not-written-anywhere",
        },
    )

    assert mock_response.status_code == 200
    assert mock_response.json()["dry_run"] is True
    assert configured_response.status_code == 200
    assert configured_response.json()["dry_run"] is True
    assert configured_response.json()["reachable"] is True
