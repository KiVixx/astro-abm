from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.models.report import ScenarioReport
from astro_abm_api.services.llm_context import build_llm_context
from astro_abm_api.services.llm_prompts import build_messages


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


@pytest.fixture(autouse=True)
def isolated_research_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_RESEARCH_OUTPUT_ROOT", str(tmp_path / "missing-research"))
    monkeypatch.delenv("ASTRO_ABM_ENABLE_REAL_LLM", raising=False)


def test_list_agents() -> None:
    client = TestClient(app)
    response = client.get("/agents")

    assert response.status_code == 200
    agent_ids = {agent["agent_id"] for agent in response.json()}
    assert "crypto_retail_fomo" in agent_ids
    assert "leveraged_trader" in agent_ids
    assert "macro_allocator" in agent_ids


def test_list_supported_market_series_assets() -> None:
    client = TestClient(app)

    response = client.get("/assets")

    assert response.status_code == 200
    assets = response.json()
    asset_ids = [asset["asset"] for asset in assets]
    assert asset_ids == ["BTC", "ETH", "SPX", "NDX", "GOLD", "DXY", "VIX", "US10Y"]
    assert "CREDITPROXY" not in asset_ids
    assert {asset["market_daily_supported"] for asset in assets} == {True}
    assert {asset["series_type"] for asset in assets} >= {
        "crypto_price",
        "equity_index",
        "commodity_price",
        "currency_index",
        "volatility_index",
        "rate_series",
    }


def test_create_list_and_get_scenario(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    create_response = client.post("/scenarios", json=scenario_payload())

    assert create_response.status_code == 200
    report = create_response.json()
    scenario_id = report["scenario_id"]
    assert report["title"] == "BTC ETH Daily Scenario"
    assert report["language"] == "en"
    assert report["llm_report"] is None
    assert report["provenance"]["language"] == "en"
    assert report["daily_context"]["data_layer"] == "daily"
    assert report["assets"] == ["BTC", "ETH"]
    assert [profile["asset"] for profile in report["asset_profiles"]] == ["BTC", "ETH"]
    assert report["asset_profiles"][0]["series_type"] == "crypto_price"
    assert report["scenario_summary"] == report["simulation_summary"]
    assert report["risk_themes"] == report["risks"]
    assert len(report["daily_timeline"]) == inclusive_day_count(
        "2026-07-01", "2026-09-30"
    )
    assert report["coverage_summary"]["total_days"] == len(report["daily_timeline"])
    assert report["coverage_summary"]["placeholder_days"] == 0
    assert report["coverage_summary"]["local_research_days"] == 0
    assert report["coverage_summary"]["astro_daily_available_days"] == len(
        report["daily_timeline"]
    )
    assert report["coverage_summary"]["source_counts"]["computed_ephemeris"] == len(
        report["daily_timeline"]
    )
    assert report["coverage_summary"]["asset_coverage"][0]["coverage_status"] == "missing"
    assert report["worldline_simulation"]["status"] == "mock_completed"
    assert report["worldline_simulation"]["mode"] == "deterministic_mock_v1"
    assert report["worldline_simulation"]["horizon_days"] == len(report["daily_timeline"])
    assert len(report["worldline_simulation"]["days"]) == len(report["daily_timeline"])
    first_worldline_day = report["worldline_simulation"]["days"][0]
    assert first_worldline_day["date"] == "2026-07-01"
    assert len(first_worldline_day["agent_events"]) == len(scenario_payload()["agent_ids"])
    assert first_worldline_day["causal_links"]
    assert "Simulated worldline only" in first_worldline_day["disclaimer"]
    for value in first_worldline_day["world_state_after"].values():
        if isinstance(value, float):
            assert 0 <= value <= 1
    for event in first_worldline_day["agent_events"]:
        assert all(-2 <= value <= 2 for value in event["impact_scores"].values())
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
    assert first_day["data_coverage"]["source"] == "computed_ephemeris"
    assert first_day["data_coverage"]["astro_daily"] == "available"
    assert first_day["data_coverage"]["financial_stress_daily"] == "missing"
    assert first_day["research_signals"]["data_quality"] == "computed_ephemeris_available"
    assert first_day["astro_context"]["event_tags"][0] == "computed_ephemeris"
    assert [context["asset"] for context in first_day["asset_contexts"]] == ["BTC", "ETH"]
    assert first_day["asset_contexts"][0]["market_daily"] in {"missing", "future_placeholder"}
    assert first_day["asset_contexts"][0]["supported"] is True
    assert "association only" in report["disclaimer"]
    assert "scenario rehearsal only" in report["disclaimer"]
    assert "not financial advice" in report["disclaimer"]
    assert "not a trading signal" in report["disclaimer"]
    assert "association only" in report["markdown_report"]
    assert "## Context Coverage Summary" in report["markdown_report"]
    assert "## Simulated Worldline" in report["markdown_report"]
    assert "not a point-in-time backtest" in report["markdown_report"]
    assert "## Daily Timeline" in report["markdown_report"]
    assert "## 2026-07-01" in report["markdown_report"]
    assert "Data coverage:" in report["markdown_report"]
    assert "Market series context:" in report["markdown_report"]
    assert "CREDITPROXY" not in report["markdown_report"]
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
    assert summaries[0]["language"] == "en"

    get_response = client.get(f"/scenarios/{scenario_id}")
    assert get_response.status_code == 200
    assert get_response.json()["scenario_id"] == scenario_id


def test_delete_scenario_removes_saved_json_and_markdown(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]
    json_path = tmp_path / f"{scenario_id}.json"
    markdown_path = tmp_path / f"{scenario_id}.md"
    assert json_path.exists()
    assert markdown_path.exists()

    delete_response = client.delete(f"/scenarios/{scenario_id}")

    assert delete_response.status_code == 200
    assert delete_response.json() == {"scenario_id": scenario_id, "deleted": True}
    assert not json_path.exists()
    assert not markdown_path.exists()
    assert client.get(f"/scenarios/{scenario_id}").status_code == 404
    assert client.get("/scenarios").json() == []


def test_delete_missing_scenario_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.delete("/scenarios/missing_scenario")

    assert response.status_code == 404
    assert response.json()["detail"] == "scenario not found"


def test_future_date_uses_computed_ephemeris_without_market_observations(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "start_date": "2026-06-22",
            "end_date": "2026-06-22",
            "language": "zh-Hant",
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    day = report["daily_timeline"][0]
    assert day["date"] == "2026-06-22"
    assert day["data_coverage"]["astro_daily"] == "available"
    assert day["data_coverage"]["source"] == "computed_ephemeris"
    assert day["research_signals"]["data_quality"] == "computed_ephemeris_available"
    assert day["astro_context"]["event_tags"][0] == "computed_ephemeris"
    assert "daily_ephemeris_placeholder" not in day["astro_context"]["event_tags"]
    assert day["data_coverage"]["market_daily"] in {"missing", "future_placeholder"}
    assert "本機計算星曆" in day["daily_summary"]
    assert "天象日線可用天數：1" in report["markdown_report"]


def test_llm_daily_context_includes_ephemeris_details(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "start_date": "2026-06-22",
            "end_date": "2026-06-24",
            "language": "zh-Hant",
        }
    )
    response = client.post("/scenarios", json=payload)
    assert response.status_code == 200
    report = ScenarioReport.model_validate(response.json())

    context = build_llm_context(
        report,
        selected_dates={date(2026, 6, 22)},
        max_context_days=10,
        chunk_metadata={
            "chunk_index": 1,
            "total_chunks": 3,
            "instruction": "Generate narrative only for this chunk's dates.",
        },
    )

    assert len(context["daily_timeline"]) == 1
    ephemeris = context["daily_timeline"][0]["astro_ephemeris"]
    assert ephemeris["status"] == "available"
    assert ephemeris["source"] == "computed_swiss_ephemeris"
    assert ephemeris["sample_time_utc"] == "2026-06-22T00:00:00Z"
    assert ephemeris["moon_phase"]["name"]
    assert "observed market data" in " ".join(ephemeris["notes"])
    body_names = {body["body"] for body in ephemeris["bodies"]}
    assert {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"} <= body_names
    assert all("lon_deg" in body for body in ephemeris["bodies"])
    assert all("lon_speed_deg_day" in body for body in ephemeris["bodies"])
    assert all("is_retrograde" in body for body in ephemeris["bodies"])


def test_llm_user_prompt_is_sent_to_llm_context_but_not_saved(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    custom_prompt = "Focus on liquidity disagreement, but stay concise."
    payload = scenario_payload()
    payload.update(
        {
            "start_date": "2026-06-22",
            "end_date": "2026-06-22",
            "llm_provider": "openai_compatible",
            "llm_real_enabled": False,
            "llm_user_prompt": custom_prompt,
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report_json = response.json()
    assert custom_prompt not in json.dumps(report_json)
    report = ScenarioReport.model_validate(report_json)
    context = build_llm_context(report, user_prompt=custom_prompt)
    assert context["user_prompt"]["text"] == custom_prompt
    messages = build_messages(context)
    assert custom_prompt in messages[1]["content"]
    assert "lower priority than system safety rules" in messages[1]["content"]


def test_default_report_language_is_english(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post("/scenarios", json=scenario_payload())

    assert response.status_code == 200
    report = response.json()
    assert report["language"] == "en"
    assert "association only" in report["scenario_summary"]
    assert "## Executive Summary" in report["markdown_report"]
    assert "僅為相關性分析" not in report["scenario_summary"]


def test_asset_aliases_are_normalized(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload["assets"] = ["Gold", "XAU", "DGS10", "S&P 500"]

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    assert report["assets"] == ["GOLD", "US10Y", "SPX"]
    assert [profile["asset"] for profile in report["asset_profiles"]] == [
        "GOLD",
        "US10Y",
        "SPX",
    ]
    assert [profile["series_type"] for profile in report["asset_profiles"]] == [
        "commodity_price",
        "rate_series",
        "equity_index",
    ]


def test_unknown_custom_asset_remains_compatible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload["assets"] = ["NVDA"]

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    first_day = report["daily_timeline"][0]
    assert report["assets"] == ["NVDA"]
    assert report["asset_profiles"][0]["asset"] == "NVDA"
    assert report["asset_profiles"][0]["supported"] is False
    assert report["asset_profiles"][0]["series_type"] == "custom"
    assert first_day["asset_contexts"][0]["market_daily"] == "custom_missing"
    assert first_day["asset_contexts"][0]["data_source"] == "custom_asset_no_local_snapshot"
    assert report["coverage_summary"]["asset_coverage"][0]["coverage_status"] == "custom_missing"


def test_traditional_chinese_report_generation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload["language"] = "zh-Hant"

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    first_day = report["daily_timeline"][0]
    assert report["language"] == "zh-Hant"
    assert report["provenance"]["language"] == "zh-Hant"
    assert "僅為相關性分析" in report["scenario_summary"]
    assert "僅為情境推演" in report["disclaimer"]
    assert "不構成財務建議" in report["disclaimer"]
    assert "不是交易訊號" in report["disclaimer"]
    assert "情境報告" in report["simulation_summary"]
    assert "第 1 天" in first_day["daily_summary"]
    assert "可能反應" in report["agent_outputs"][0]["likely_reaction"]
    assert "風險討論" in first_day["agent_states"][0]["likely_reaction"]
    assert "僅為相關性分析" in report["caveats"][0]
    assert "## 執行摘要" in report["markdown_report"]
    assert "## 每日時間線" in report["markdown_report"]
    assert "僅為相關性分析" in report["markdown_report"]


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
    assert "data_coverage" in output_json["daily_timeline"][0]
    assert "research_signals" in output_json["daily_timeline"][0]
    assert output_json["provenance"]["llm"]["credential_status"] == "redacted"
    assert output_json["provenance"]["llm"]["network_call_performed"] is False
    assert output_json["llm_report"]["status"] == "dry_run"
    assert output_json["llm_report"]["provenance"]["credential_status"] == "redacted"
    assert output_json["llm_report"]["provenance"]["network_call_performed"] is False


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
    report.pop("language")
    report.pop("coverage_summary")
    report.pop("llm_report")
    report.pop("worldline_simulation")
    (tmp_path / f"{scenario_id}.json").write_text(json.dumps(report), encoding="utf-8")

    get_response = client.get(f"/scenarios/{scenario_id}")

    assert get_response.status_code == 200
    loaded = get_response.json()
    assert loaded["scenario_id"] == scenario_id
    assert loaded["daily_timeline"] == []
    assert loaded["scenario_summary"] is None
    assert loaded["risk_themes"] == []
    assert loaded["language"] is None
    assert loaded["coverage_summary"] is None
    assert loaded["llm_report"] is None
    assert loaded["worldline_simulation"] is None


def test_old_daily_timeline_without_research_fields_loads(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post("/scenarios", json=scenario_payload())
    assert response.status_code == 200
    report = response.json()
    scenario_id = "old_timeline_report"
    report["scenario_id"] = scenario_id
    report["daily_timeline"][0].pop("data_coverage")
    report["daily_timeline"][0].pop("research_signals")
    (tmp_path / f"{scenario_id}.json").write_text(json.dumps(report), encoding="utf-8")

    get_response = client.get(f"/scenarios/{scenario_id}")

    assert get_response.status_code == 200
    loaded_day = get_response.json()["daily_timeline"][0]
    assert loaded_day["data_coverage"]["source"] == "legacy_report"
    assert loaded_day["research_signals"]["data_quality"] == "unknown"


def test_scenario_uses_local_research_context_when_available(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path / "scenarios"))
    research_root = tmp_path / "research-output"
    monkeypatch.setenv("ASTRO_ABM_RESEARCH_OUTPUT_ROOT", str(research_root))
    _write_minimal_research_context(research_root)
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"start_date": "2026-07-01", "end_date": "2026-07-01"})

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    day = report["daily_timeline"][0]
    coverage_summary = report["coverage_summary"]
    assert coverage_summary["total_days"] == 1
    assert coverage_summary["local_research_days"] == 1
    assert coverage_summary["astro_daily_available_days"] == 1
    assert coverage_summary["financial_stress_available_days"] == 1
    assert coverage_summary["market_daily_available_days"] == 1
    assert coverage_summary["macro_daily_available_days"] == 1
    assert coverage_summary["source_counts"]["local_research_snapshot"] == 1
    assert coverage_summary["data_quality_counts"]["local_research_available"] == 1
    assert coverage_summary["asset_coverage"][0]["coverage_status"] == "available"
    assert day["data_coverage"]["source"] == "local_research_snapshot"
    assert day["data_coverage"]["astro_daily"] == "available"
    assert day["data_coverage"]["financial_stress_daily"] == "available"
    assert day["data_coverage"]["market_daily"] == "available"
    assert day["data_coverage"]["macro_daily"] == "available"
    assert day["research_signals"]["stress_regime"] == "stress"
    assert day["research_signals"]["volatility_regime"] == "expanded"
    assert day["research_signals"]["liquidity_regime"] == "thin"
    assert day["research_signals"]["astro_activity"] == "high"
    assert day["research_signals"]["data_quality"] == "local_research_available"
    assert day["market_context"]["stress_regime"] == "stress"
    assert "stress regime: stress" in day["market_context"]["summary"]
    assert day["astro_context"]["intensity"] == "high"
    assert day["astro_context"]["event_tags"] == ["local_astro_daily", "astro_activity:high"]
    assert "read-only daily research context snapshot" in day["daily_summary"]
    assert day["confidence"] == "low_research_context_confidence"
    assert "elevated_stress_review" in day["daily_risk_themes"]
    assert "stress_stress_review" not in day["daily_risk_themes"]
    assert "stress stress" not in day["agent_states"][0]["likely_reaction"]
    assert "local research" in report["markdown_report"]


def test_scenario_generation_does_not_call_external_http(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    def fail_request(*args, **kwargs):
        raise AssertionError("external HTTP request should not be performed")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)
    client = TestClient(app)
    response = client.post("/scenarios", json=scenario_payload())

    assert response.status_code == 200


def test_openai_compatible_disabled_returns_dry_run_without_network(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    def fail_post(*args, **kwargs):
        raise AssertionError("network call should not be performed when real LLM is disabled")

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fail_post)
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
    report = response.json()
    assert report["llm_report"]["status"] == "dry_run"
    assert report["llm_report"]["provenance"]["network_call_performed"] is False
    assert "ASTRO_ABM_ENABLE_REAL_LLM=1" in report["llm_report"]["executive_summary"]
    assert "## LLM Scenario Report" in report["markdown_report"]


def test_request_can_disable_real_llm_even_when_env_is_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ASTRO_ABM_ENABLE_REAL_LLM", "1")

    def fail_post(*args, **kwargs):
        raise AssertionError("request-level disabled flag should prevent network calls")

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fail_post)
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "llm_provider": "openai_compatible",
            "llm_real_enabled": False,
            "llm_base_url": "http://localhost:11434/v1",
            "llm_model": "local-model",
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    assert report["llm_report"]["status"] == "dry_run"
    assert report["llm_report"]["provenance"]["network_call_performed"] is False


def test_openai_compatible_mocked_network_parses_valid_json(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    request_secret = "request-level-secret"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            content = json.dumps(
                {
                    "executive_summary": "Association-only scenario reading from supplied context.",
                    "scenario_reading": "The context suggests a cautious rehearsal lens without causal claims.",
                    "daily_highlights": [
                        {
                            "date": "2026-07-01",
                            "summary": "Opening day highlights placeholder and coverage status.",
                            "key_context": "coverage reviewed",
                            "agent_focus": "risk review",
                            "caveats": "scenario rehearsal only",
                        }
                    ],
                    "agent_interpretations": [
                        {
                            "agent_id": "macro_allocator",
                            "agent_name": "Macro Allocator",
                            "interpretation": "Reviews cross-asset context cautiously.",
                            "risk_focus": "coverage quality",
                            "caveats": "not financial advice",
                        }
                    ],
                    "asset_stress_indicators": [
                        {
                            "date": "2026-07-01",
                            "asset": "BTC",
                            "sentiment_stress_support": 62.5,
                            "label": "mid_support",
                            "rationale": "Mixed placeholder context with controlled liquidity.",
                            "caveats": ["scenario metric only"],
                        }
                    ],
                    "risk_themes": ["coverage uncertainty"],
                    "caveats": ["does not invent missing data"],
                    "disclaimer": "association only; scenario rehearsal only; not financial advice; not a trading signal.",
                }
            )
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Here is the JSON only:\n" + content
                        }
                    }
                ]
            }

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fake_post)
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "llm_api_key": request_secret,
            "llm_timeout_seconds": 123,
            "llm_max_output_tokens": 6000,
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    report = response.json()
    output_text = (tmp_path / f"{report['scenario_id']}.json").read_text(encoding="utf-8")
    assert calls[0][0] == "http://llm.local/v1/chat/completions"
    assert calls[0][1]["Authorization"] == f"Bearer {request_secret}"
    assert calls[0][2]["max_tokens"] == 6000
    assert calls[0][3] == 123
    assert request_secret not in output_text
    assert report["llm_report"]["status"] == "completed"
    assert report["llm_report"]["provenance"]["network_call_performed"] is True
    assert report["llm_report"]["provenance"]["output_validation_status"] == "valid_json"
    assert report["llm_report"]["provenance"]["safety_check_status"] == "passed"
    assert report["llm_report"]["daily_highlights"][0]["date"] == "2026-07-01"
    assert report["llm_report"]["daily_highlights"][0]["key_context"] == [
        "coverage reviewed"
    ]
    assert report["llm_report"]["agent_interpretations"][0]["risk_focus"] == [
        "coverage quality"
    ]
    assert report["llm_report"]["asset_stress_indicators"][0]["asset"] == "BTC"
    assert (
        report["llm_report"]["asset_stress_indicators"][0]["sentiment_stress_support"]
        == 62.5
    )
    assert "Asset stress support indicators" in report["markdown_report"]


def test_llm_chunk_endpoint_merges_and_saves_report(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    request_secret = "chunk-request-secret"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "executive_summary": "Chunked association-only reading.",
                                    "scenario_reading": "This chunk reviews only the supplied dates.",
                                    "daily_highlights": [
                                        {
                                            "date": "2026-07-01",
                                            "summary": "Chunk day one reviewed.",
                                            "key_context": ["chunk coverage"],
                                            "agent_focus": ["agent attention"],
                                            "caveats": ["scenario rehearsal only"],
                                        }
                                    ],
                                    "agent_interpretations": [],
                                    "asset_stress_indicators": [
                                        {
                                            "date": "2026-07-01",
                                            "asset": "ETH",
                                            "sentiment_stress_support": 48,
                                            "label": "mid_support",
                                            "rationale": "Chunk context remains mixed.",
                                            "caveats": ["visualization only"],
                                        }
                                    ],
                                    "risk_themes": ["chunked context"],
                                    "caveats": ["does not invent missing data"],
                                    "disclaimer": "association only; scenario rehearsal only; not financial advice; not a trading signal.",
                                }
                            )
                        }
                    }
                ]
            }

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fake_post)
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/llm-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "llm_api_key": request_secret,
            "llm_timeout_seconds": 77,
            "llm_max_output_tokens": 3000,
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-03",
            "chunk_index": 1,
            "total_chunks": 2,
        },
    )

    assert chunk_response.status_code == 200
    body = chunk_response.json()
    saved_text = (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")
    assert body["llm_status"] == "completed"
    assert body["completed"] is False
    assert body["report"]["llm_report"]["status"] == "completed"
    assert "#### 2026-07-01 to 2026-07-03" in body["report"]["llm_report"]["scenario_reading"]
    assert "\nThis chunk reviews only the supplied dates." in body["report"]["llm_report"]["scenario_reading"]
    assert body["report"]["llm_report"]["daily_highlights"][0]["date"] == "2026-07-01"
    assert body["report"]["llm_report"]["asset_stress_indicators"][0]["asset"] == "ETH"
    assert body["report"]["provenance"]["llm"]["chunked_generation"] is True
    assert calls[0][2]["max_tokens"] == 3000
    assert calls[0][3] == 77
    assert request_secret not in saved_text
    assert "## LLM Scenario Report" in body["report"]["markdown_report"]


def test_openai_compatible_invalid_json_marks_invalid_output(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ASTRO_ABM_ENABLE_REAL_LLM", "1")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", lambda *args, **kwargs: Response())
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    llm_report = response.json()["llm_report"]
    assert llm_report["status"] == "invalid_output"
    assert llm_report["raw_text_preview"] == "not json"


def test_openai_compatible_safety_failure_fails_safe(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ASTRO_ABM_ENABLE_REAL_LLM", "1")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "executive_summary": "You should buy BTC.",
                                    "scenario_reading": "Unsafe output.",
                                    "daily_highlights": [],
                                    "agent_interpretations": [],
                                    "risk_themes": [],
                                    "caveats": [],
                                    "disclaimer": "association only; scenario rehearsal only; not financial advice; not a trading signal.",
                                }
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", lambda *args, **kwargs: Response())
    client = TestClient(app)
    payload = scenario_payload()
    payload.update(
        {
            "llm_provider": "openai_compatible",
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
        }
    )

    response = client.post("/scenarios", json=payload)

    assert response.status_code == 200
    llm_report = response.json()["llm_report"]
    assert llm_report["status"] == "safety_review_failed"
    assert llm_report["provenance"]["safety_check_status"] == "failed"
    assert "buy BTC" not in llm_report["executive_summary"]


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
    assert mock_response.json()["status"] == "ok"
    assert configured_response.status_code == 200
    assert configured_response.json()["dry_run"] is True
    assert configured_response.json()["reachable"] is False
    assert configured_response.json()["status"] == "disabled"


def test_llm_test_openai_compatible_enabled_uses_mocked_network(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fake_post)
    client = TestClient(app)

    response = client.post(
        "/llm/test",
        json={
            "provider": "openai_compatible",
            "real_enabled": True,
            "base_url": "http://localhost:11434/v1",
            "model": "local-model",
            "api_key": "secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["reachable"] is True
    assert response.json()["dry_run"] is False
    assert response.json()["status"] == "ok"
    assert calls[0][1]["Authorization"] == "Bearer secret"


def _write_minimal_research_context(root: Path) -> None:
    ts = pd.Timestamp("2026-07-01T00:00:00Z")
    astro_dir = root / "parquet/astro_daily_1926_2025"
    stress_dir = root / "parquet/financial_stress"
    market_dir = root / "parquet/market_daily"
    macro_dir = root / "parquet/macro_daily"
    for directory in (astro_dir, stress_dir, market_dir, macro_dir):
        directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts": [ts],
            "active_retrograde_count": [4],
            "station_cluster_count_7d": [2],
            "major_aspect_cluster_count_7d": [3],
            "moon_phase_name": ["FullMoonZone"],
        }
    ).to_parquet(astro_dir / "astro_daily_features.parquet", index=False)
    pd.DataFrame(
        {
            "ts": [ts],
            "stress_regime": ["stress"],
            "vol_stress_score": [0.9],
            "cross_asset_stress_score": [0.8],
            "component_count": [4],
        }
    ).to_parquet(stress_dir / "financial_stress_daily.parquet", index=False)
    pd.DataFrame(
        {
            "ts": [ts, ts],
            "asset": ["BTC", "ETH"],
            "realized_vol_20d": [0.12, 0.16],
            "is_extreme_absret_95": [True, False],
        }
    ).to_parquet(market_dir / "market_daily_features.parquet", index=False)
    pd.DataFrame(
        {
            "ts": [ts],
            "series_id": ["VIXCLS"],
            "value": [24.0],
        }
    ).to_parquet(macro_dir / "macro_daily_observations.parquet", index=False)
