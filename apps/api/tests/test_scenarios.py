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
from astro_abm_api.services.llm_client import (
    diagnose_llm_request_error,
    diagnose_llm_json,
    safety_check_text,
    safety_violation_codes,
)
from astro_abm_api.services.llm_context import build_llm_context
from astro_abm_api.services.llm_prompts import build_messages
from astro_abm_api.services.worldline_llm_prompts import (
    build_worldline_messages,
    build_worldline_retry_messages,
)


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


def assert_worldline_state_continuity(days: list[dict[str, object]]) -> None:
    for previous_day, current_day in zip(days, days[1:]):
        assert current_day["world_state_before"] == previous_day["world_state_after"]


def test_safety_checker_allows_benign_horizon_language() -> None:
    benign_text = (
        "Long-Term Holder reviews a long-term horizon with a longer-term view. "
        "A short-horizon participant watches a short window for scenario rehearsal only."
    )

    assert safety_check_text(benign_text)


@pytest.mark.parametrize(
    "safe_text",
    [
        "不得提供買入、賣出、做多、做空等交易建議。",
        "這不是買入或賣出建議，也不構成做多或做空訊號。",
        "本報告不提供目標價，也不保證任何情境一定會漲或一定會跌。",
        "請避免把模擬結果解讀成買入訊號。",
    ],
)
def test_safety_checker_allows_traditional_chinese_safety_disclaimers(
    safe_text: str,
) -> None:
    assert safety_check_text(safe_text)


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "go long",
        "enter long",
        "long BTC",
        "go short",
        "short ETH",
        "buy BTC",
        "sell ETH",
        "price target",
        "must buy",
        "must sell",
        "買入",
        "賣出",
        "做多",
        "做空",
        "目標價",
        "保證",
        "一定會漲",
        "一定會跌",
        "建議立即買入 BTC",
        "可以考慮賣出 ETH",
        "這是做多訊號",
        "BTC 的目標價是 100000",
        "保證 BTC 一定會漲",
        "不建議買入 BTC，但建議賣出 ETH",
    ],
)
def test_safety_checker_rejects_explicit_trading_instruction_phrases(
    unsafe_text: str,
) -> None:
    assert not safety_check_text(unsafe_text)


def test_safety_checker_reports_categories_without_retaining_input() -> None:
    unsafe_text = "You must buy BTC because it will rise."

    codes = safety_violation_codes(unsafe_text)

    assert codes == ["trading_instruction", "guaranteed_direction"]
    assert unsafe_text not in json.dumps(codes)


def test_llm_json_diagnostics_identify_truncation_without_retaining_content() -> None:
    raw_text = '{"days": [{"date": "2026-07-01"}'

    diagnostics = diagnose_llm_json(raw_text)

    assert diagnostics["response_char_count"] == len(raw_text)
    assert diagnostics["parse_error_type"] == "truncated_json"
    assert diagnostics["probable_truncation"] is True
    assert "raw_text" not in diagnostics
    assert raw_text not in json.dumps(diagnostics)


def test_llm_json_parser_accepts_complete_object_with_surrounding_text() -> None:
    raw_text = 'Result follows:\n```json\n{"days": [], "summary": "ok"}\n```\nDone.'

    from astro_abm_api.services.llm_client import parse_llm_json

    parsed = parse_llm_json(raw_text)
    diagnostics = diagnose_llm_json(raw_text)

    assert parsed == {"days": [], "summary": "ok"}
    assert diagnostics["parse_error_type"] is None
    assert diagnostics["leading_text_ignored"] is True
    assert diagnostics["trailing_text_ignored"] is True
    assert raw_text not in json.dumps(diagnostics)


def test_llm_request_diagnostics_classify_timeout_without_retaining_details() -> None:
    secret_detail = "https://llm.example/v1?api_key=secret-value"

    diagnostics = diagnose_llm_request_error(requests.Timeout(secret_detail))

    assert diagnostics == {
        "error_category": "timeout",
        "failure_kind": "request_timeout",
        "recommended_action": "retry_later",
        "exception_type": "Timeout",
        "retryable": True,
        "http_status": None,
    }
    assert secret_detail not in json.dumps(diagnostics)


@pytest.mark.parametrize(
    ("status", "failure_kind", "recommended_action", "retryable"),
    [
        (401, "authentication_failed", "check_credentials", False),
        (403, "permission_denied", "check_permissions", False),
        (404, "endpoint_or_model_not_found", "check_endpoint_or_model", False),
        (422, "request_rejected", "check_request_settings", False),
        (429, "rate_limited", "wait_and_retry", True),
        (503, "upstream_unavailable", "retry_later", True),
    ],
)
def test_llm_request_diagnostics_classify_http_failures(
    status: int,
    failure_kind: str,
    recommended_action: str,
    retryable: bool,
) -> None:
    response = requests.Response()
    response.status_code = status
    error = requests.HTTPError("sensitive provider response", response=response)

    diagnostics = diagnose_llm_request_error(error)

    assert diagnostics == {
        "error_category": "http_error",
        "failure_kind": failure_kind,
        "recommended_action": recommended_action,
        "exception_type": "HTTPError",
        "retryable": retryable,
        "http_status": status,
    }
    assert "sensitive provider response" not in json.dumps(diagnostics)


def test_llm_request_diagnostics_classify_unreachable_endpoint() -> None:
    diagnostics = diagnose_llm_request_error(
        requests.ConnectionError("https://secret-endpoint.example/v1")
    )

    assert diagnostics["failure_kind"] == "endpoint_unreachable"
    assert diagnostics["recommended_action"] == "check_endpoint"
    assert diagnostics["retryable"] is True
    assert "secret-endpoint" not in json.dumps(diagnostics)


def test_scenario_llm_prompt_uses_traditional_chinese_instructions_for_zh_hant() -> None:
    messages = build_messages(
        {
            "language": "zh-Hant",
            "title": "測試情境",
            "daily_timeline": [],
            "user_prompt": {"text": "Focus on liquidity, but keep it concise."},
        }
    )

    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "你是情境推演系統的分析員" in system
    assert "所有面向使用者閱讀的 string value 必須使用繁體中文" in system
    assert "JSON key 必須完全保留指定 schema 的英文 key" in system
    assert "You are an analyst for a scenario rehearsal system" not in system
    assert user.startswith("請根據這份精簡 JSON context")
    assert "使用者補充指引" in user


def test_worldline_llm_prompt_uses_traditional_chinese_instructions_for_zh_hant() -> None:
    messages = build_worldline_messages(
        {
            "language": "zh-Hant",
            "title": "測試世界線",
            "agents": [],
            "daily_timeline": [],
            "user_prompt": {"text": "Focus on liquidity, but keep it concise."},
        }
    )

    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "你正在模擬一條市場情境世界線" in system
    assert "所有面向使用者閱讀的 string value 必須使用繁體中文" in system
    assert "所有因果語言都必須明確框定為「此世界線內部的模擬因果」" in system
    assert "You are simulating a market scenario worldline" not in system
    assert user.startswith("請根據這份精簡 JSON context")
    assert "使用者補充指引" in user


def test_worldline_retry_prompt_uses_report_language_without_raw_output() -> None:
    base = build_worldline_messages({"language": "zh-Hant", "daily_timeline": []})

    retried = build_worldline_retry_messages(
        base,
        language="zh-Hant",
        output_validation_status="invalid_json",
        safety_check_status="not_run",
        next_attempt=2,
    )

    assert len(retried) == 3
    assert "上一次回應無法解析為完整 JSON" in retried[-1]["content"]
    assert "原始回應" not in retried[-1]["content"]
    assert build_worldline_retry_messages(
        base,
        language="zh-Hant",
        output_validation_status="request_failed",
        safety_check_status="not_run",
        next_attempt=2,
    ) == base


def test_llm_prompts_keep_english_instructions_for_english_reports() -> None:
    scenario_messages = build_messages({"language": "en", "daily_timeline": []})
    worldline_messages = build_worldline_messages({"language": "en", "daily_timeline": []})

    assert "All user-facing string values must be English" in scenario_messages[0]["content"]
    assert "All user-facing string values must be English" in worldline_messages[0]["content"]
    assert scenario_messages[1]["content"].startswith("Build a cautious scenario narrative")
    assert worldline_messages[1]["content"].startswith("Generate the simulated worldline chunk")


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
    assert report["worldline_simulation"]["continuity_status"] == "consistent"
    assert report["worldline_simulation"]["generation_config"]["worldline_provider"] == "deterministic_mock"
    assert report["worldline_simulation"]["horizon_days"] == len(report["daily_timeline"])
    assert len(report["worldline_simulation"]["days"]) == len(report["daily_timeline"])
    first_worldline_day = report["worldline_simulation"]["days"][0]
    assert first_worldline_day["date"] == "2026-07-01"
    assert first_worldline_day["generation_source"] == "deterministic_mock"
    assert first_worldline_day["chunk_status"] == "mock_completed"
    assert first_worldline_day["quality_notes"]
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


def test_worldline_chunk_disabled_returns_dry_run_without_network(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    def fail_post(*args, **kwargs):
        raise AssertionError("network call should not be performed when real LLM is disabled")

    monkeypatch.setattr("astro_abm_api.services.worldline_llm_generator._call_openai_compatible", fail_post)
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": False,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-03",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 3,
        },
    )

    assert chunk_response.status_code == 200
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    assert chunk_response.json()["worldline_status"] == "dry_run"
    assert worldline["status"] == "dry_run"
    assert worldline["mode"] == "llm_chunk_v1"
    assert worldline["provenance"]["generation_mode"] == "dry_run"
    assert worldline["provenance"]["network_call_performed"] is False


def test_worldline_generation_config_snapshots_resolved_non_secret_env_settings(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ASTRO_ABM_LLM_BASE_URL", "http://env-llm.local/v1")
    monkeypatch.setenv("ASTRO_ABM_LLM_MODEL", "env-model")
    monkeypatch.setenv("ASTRO_ABM_LLM_API_KEY", "env-secret")
    monkeypatch.setenv("ASTRO_ABM_LLM_TIMEOUT_SECONDS", "91")
    monkeypatch.setenv("ASTRO_ABM_LLM_MAX_OUTPUT_TOKENS", "4096")

    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    scenario_id = create_response.json()["scenario_id"]
    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": False,
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-03",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 3,
        },
    )

    assert chunk_response.status_code == 200
    config = chunk_response.json()["report"]["worldline_simulation"]["generation_config"]
    saved_text = (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")
    assert config["llm_base_url"] == "http://env-llm.local/v1"
    assert config["llm_model"] == "env-model"
    assert config["llm_timeout_seconds"] == 91
    assert config["llm_max_output_tokens"] == 4096
    assert config["credential_status"] == "redacted"
    assert "env-secret" not in saved_text


def test_worldline_chunk_mocked_network_generates_structured_events(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    request_secret = "worldline-secret"

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
                                    "summary": "LLM simulated worldline chunk from supplied context.",
                                    "days": [
                                        {
                                            "date": "2026-07-01",
                                            "agent_events": [
                                                {
                                                    "agent_id": "crypto_retail_fomo",
                                                    "what_happened": "Retail attention increased inside the simulated worldline.",
                                                    "why_it_happened": "The provided context combined watchful stress and narrative sensitivity.",
                                                    "impact_on_tomorrow": "Sets up more narrative review for tomorrow.",
                                                    "impact_scores": {
                                                        "sentiment_delta": 4,
                                                        "narrative_pressure_delta": 3,
                                                        "leverage_pressure_delta": 0,
                                                        "liquidity_pressure_delta": 0,
                                                        "volatility_pressure_delta": 1,
                                                        "stress_pressure_delta": 1,
                                                    },
                                                    "confidence": "low_llm_context_confidence",
                                                    "caveats": ["simulated worldline only"],
                                                },
                                                {
                                                    "agent_id": "unknown_agent",
                                                    "what_happened": "This should be ignored.",
                                                    "why_it_happened": "Unknown agent.",
                                                    "impact_on_tomorrow": "Ignored.",
                                                    "impact_scores": {},
                                                    "confidence": "low",
                                                    "caveats": [],
                                                },
                                            ],
                                            "causal_links": [
                                                {
                                                    "source": "retail_attention",
                                                    "target": "next_day_narrative_pressure",
                                                    "description": "A simulated link raises tomorrow's narrative pressure.",
                                                    "strength": "medium",
                                                    "caveats": ["simulated causal link only"],
                                                }
                                            ],
                                            "next_day_update": "Tomorrow starts with narrative pressure under review.",
                                            "world_state_after": {
                                                "sentiment_state": "watchful",
                                                "narrative_pressure": 1.5,
                                                "leverage_pressure": -0.2,
                                                "liquidity_pressure": 0.44,
                                                "volatility_pressure": 0.55,
                                                "stress_pressure": 0.66,
                                                "regime_label": "llm_chunk_watch",
                                                "notes": ["clamped by backend"],
                                            },
                                        }
                                    ],
                                    "caveats": ["does not invent external data"],
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
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "llm_api_key": request_secret,
            "llm_timeout_seconds": 88,
            "llm_max_output_tokens": 2500,
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    body = chunk_response.json()
    saved_text = (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")
    worldline = body["report"]["worldline_simulation"]
    first_day = worldline["days"][0]
    assert body["worldline_status"] == "completed"
    assert worldline["mode"] == "llm_chunk_v1"
    assert worldline["provenance"]["generation_mode"] == "llm_chunk_v1"
    assert worldline["provenance"]["chunk_size_days"] == 1
    assert worldline["provenance"]["chunk_count"] == 1
    assert worldline["provenance"]["failed_chunk_count"] == 0
    assert worldline["provenance"]["network_call_performed"] is True
    assert worldline["provenance"]["safety_check_status"] == "passed"
    assert worldline["provenance"]["llm_output_quality_notes"]
    assert worldline["provenance"]["chunk_history"][0]["status"] == "completed"
    assert first_day["generation_source"] == "llm_chunk"
    assert first_day["chunk_index"] == 1
    assert first_day["chunk_status"] == "completed"
    assert first_day["quality_notes"]
    assert first_day["agent_events"][0]["agent_id"] == "crypto_retail_fomo"
    assert len(first_day["agent_events"]) == 1
    assert first_day["agent_events"][0]["impact_scores"]["sentiment_delta"] == 2
    assert first_day["world_state_after"]["narrative_pressure"] == 1
    assert first_day["world_state_after"]["leverage_pressure"] == 0
    assert first_day["causal_links"][0]["source"] == "retail_attention"
    assert_worldline_state_continuity(worldline["days"])
    assert calls[0][0] == "http://llm.local/v1/chat/completions"
    assert calls[0][1]["Authorization"] == f"Bearer {request_secret}"
    assert calls[0][2]["max_tokens"] == 2500
    assert calls[0][3] == 88
    assert request_secret not in saved_text
    assert "Generation mode: llm_chunk_v1" in body["report"]["markdown_report"]


def test_worldline_regenerate_from_middle_chunk_rebuilds_downstream_only(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-06", "worldline_chunk_days": 3})
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]
    original_days = create_response.json()["worldline_simulation"]["days"]
    original_prefix = original_days[:3]

    response = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={"start_chunk_index": 1},
    )

    assert response.status_code == 200
    body = response.json()
    worldline = body["report"]["worldline_simulation"]
    assert body["rebuilt_chunk_count"] == 1
    assert body["continuity_status"] == "consistent"
    assert worldline["continuity_status"] == "consistent"
    assert worldline["days"][:3] == original_prefix
    assert {day["chunk_index"] for day in worldline["days"][3:]} == {2}
    assert all(day["chunk_status"] == "mock_completed" for day in worldline["days"][3:])
    assert worldline["last_regeneration"]["start_chunk_index"] == 1
    assert worldline["provenance"]["chunk_history"][-1]["upstream_state_hash"]
    assert worldline["provenance"]["chunk_history"][-1]["output_state_hash"]
    assert_worldline_state_continuity(worldline["days"])
    assert "Continuity status: consistent" in body["report"]["markdown_report"]


def test_worldline_regenerate_from_zero_rebuilds_all_chunks(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-06", "worldline_chunk_days": 3})
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    response = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={"start_chunk_index": 0},
    )

    assert response.status_code == 200
    body = response.json()
    worldline = body["report"]["worldline_simulation"]
    assert body["rebuilt_chunk_count"] == 2
    assert {day["chunk_index"] for day in worldline["days"]} == {1, 2}
    history = worldline["provenance"]["chunk_history"]
    assert history[0]["chunk_index"] == 1
    assert history[1]["chunk_index"] == 2
    assert history[1]["upstream_state_hash"] == history[0]["output_state_hash"]
    assert_worldline_state_continuity(worldline["days"])


def test_progressive_regeneration_marks_downstream_stale_until_final_chunk(
    monkeypatch, tmp_path: Path
) -> None:
    from astro_abm_api.services import worldline_regeneration

    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-06", "worldline_chunk_days": 3})
    created = client.post("/scenarios", json=payload).json()
    scenario_id = created["scenario_id"]
    original_downstream = created["worldline_simulation"]["days"][3:]
    original_regenerator = worldline_regeneration._regenerate_deterministic_chunk

    def regenerate_with_changed_anchor(*args, **kwargs):
        days = original_regenerator(*args, **kwargs)
        final_day = days[-1]
        changed_state = final_day.world_state_after.model_copy(
            update={
                "narrative_pressure": min(
                    1.0, final_day.world_state_after.narrative_pressure + 0.123
                )
            }
        )
        return [
            *days[:-1],
            final_day.model_copy(update={"world_state_after": changed_state}),
        ]

    monkeypatch.setattr(
        worldline_regeneration,
        "_regenerate_deterministic_chunk",
        regenerate_with_changed_anchor,
    )

    first = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={
            "start_chunk_index": 0,
            "regeneration_id": "interrupted_progressive_run",
            "progressive": True,
        },
    )

    assert first.status_code == 200
    first_worldline = first.json()["report"]["worldline_simulation"]
    assert first.json()["continuity_status"] == "rebuilding"
    assert first_worldline["continuity_status"] == "rebuilding"
    assert first_worldline["days"][3:] == original_downstream
    assert first_worldline["last_regeneration"]["pending_chunk_count"] == 1
    assert "Continuity status: rebuilding" in first.json()["report"]["markdown_report"]

    final = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={
            "start_chunk_index": 1,
            "regeneration_id": "interrupted_progressive_run",
            "progressive": True,
        },
    )

    assert final.status_code == 200
    final_worldline = final.json()["report"]["worldline_simulation"]
    assert final.json()["continuity_status"] == "consistent"
    assert final_worldline["continuity_status"] == "consistent"
    assert final_worldline["last_regeneration"]["pending_chunk_count"] == 0
    assert_worldline_state_continuity(final_worldline["days"])
    history = final_worldline["provenance"]["chunk_history"]
    assert history[1]["upstream_state_hash"] == history[0]["output_state_hash"]


def test_worldline_regeneration_preserves_safe_llm_attempt_diagnostics(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-01", "worldline_chunk_days": 1})
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    scenario_path = tmp_path / f"{scenario_id}.json"
    saved_report = json.loads(scenario_path.read_text(encoding="utf-8"))
    generation_config = saved_report["worldline_simulation"]["generation_config"]
    generation_config.update(
        {
            "worldline_provider": "llm",
            "worldline_chunk_days": 1,
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
        }
    )
    scenario_path.write_text(json.dumps(saved_report), encoding="utf-8")

    def fake_regenerate_llm_chunk(report, chunk, chunks, previous_state, config, api_key):
        from astro_abm_api.services.worldline_simulation import (
            generate_worldline_days_for_range,
        )

        days = generate_worldline_days_for_range(
            report,
            start_date=chunk.start_date,
            end_date=chunk.end_date,
            previous_state=previous_state,
            generation_source="llm_chunk",
            chunk_index=chunk.chunk_index,
            chunk_status="completed",
            quality_notes=[],
        )
        details = {
            "attempt_count": 2,
            "max_attempts": 3,
            "attempt_history": [
                {
                    "attempt": 1,
                    "output_validation_status": "invalid_json",
                    "safety_check_status": "not_run",
                    "response_diagnostics": {"parse_error_type": "truncated_json"},
                    "safety_violation_codes": [],
                },
                {
                    "attempt": 2,
                    "output_validation_status": "valid_json",
                    "safety_check_status": "passed",
                    "response_diagnostics": {"parse_error_type": None},
                    "safety_violation_codes": [],
                },
            ],
            "safety_violation_codes": [],
        }
        return days, "completed", "valid_json", "passed", True, [], details

    monkeypatch.setattr(
        "astro_abm_api.services.worldline_regeneration._regenerate_llm_chunk",
        fake_regenerate_llm_chunk,
    )

    response = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={"start_chunk_index": 0},
    )

    assert response.status_code == 200
    history = response.json()["report"]["worldline_simulation"]["provenance"][
        "chunk_history"
    ]
    assert history[0]["attempt_count"] == 2
    assert [item["attempt"] for item in history[0]["attempt_history"]] == [1, 2]
    assert "raw_text" not in json.dumps(history[0])


def test_worldline_regenerate_invalid_chunk_returns_400(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-06", "worldline_chunk_days": 3})
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    response = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={"start_chunk_index": 99},
    )

    assert response.status_code == 400
    assert "out of range" in response.json()["detail"]


def test_worldline_regenerate_missing_scenario_returns_404(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/scenarios/missing_scenario/worldline/regenerate-from",
        json={"start_chunk_index": 0},
    )

    assert response.status_code == 404


def test_worldline_regenerate_missing_generation_config_falls_back_safely(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    payload = scenario_payload()
    payload.update({"end_date": "2026-07-06", "worldline_chunk_days": 3})
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    scenario_path = tmp_path / f"{scenario_id}.json"
    legacy_report = json.loads(scenario_path.read_text(encoding="utf-8"))
    legacy_report["worldline_simulation"].pop("generation_config", None)
    legacy_report["worldline_simulation"].pop("last_regeneration", None)
    scenario_path.write_text(json.dumps(legacy_report), encoding="utf-8")

    response = client.post(
        f"/scenarios/{scenario_id}/worldline/regenerate-from",
        json={"start_chunk_index": 1},
    )

    assert response.status_code == 200
    worldline = response.json()["report"]["worldline_simulation"]
    assert worldline["generation_config"]["worldline_provider"] == "deterministic_mock"
    assert "Original generation preset was unavailable" in " ".join(worldline["caveats"])
    assert worldline["last_regeneration"]["preset_note"]


def test_worldline_chunk_retries_before_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    valid_payload = {
        "summary": "Recovered chunk.",
        "days": [
            {
                "date": "2026-07-01",
                "agent_events": [
                    {
                        "agent_id": "crypto_retail_fomo",
                        "what_happened": "Retail attention was reviewed inside the simulated worldline.",
                        "why_it_happened": "The supplied context remained bounded and scenario-internal.",
                        "impact_on_tomorrow": "Tomorrow starts with narrative pressure under review.",
                        "impact_scores": {
                            "sentiment_delta": 1,
                            "narrative_pressure_delta": 1,
                            "leverage_pressure_delta": 0,
                            "liquidity_pressure_delta": 0,
                            "volatility_pressure_delta": 1,
                            "stress_pressure_delta": 0,
                        },
                        "confidence": "low",
                        "caveats": ["simulated worldline only"],
                    }
                ],
                "causal_links": [],
                "next_day_update": "The next simulated day remains under review.",
                "world_state_after": {},
            }
        ],
        "caveats": [],
    }
    calls = 0
    request_payloads: list[dict[str, object]] = []
    retry_delays: list[float] = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            nonlocal calls
            calls += 1
            if calls < 3:
                return {"choices": [{"message": {"content": "not json"}}]}
            return {"choices": [{"message": {"content": json.dumps(valid_payload)}}]}

    def fake_post(*args, **kwargs):
        request_payloads.append(kwargs["json"])
        return Response()

    monkeypatch.setattr("astro_abm_api.services.llm_client.requests.post", fake_post)
    monkeypatch.setattr(
        "astro_abm_api.services.worldline_llm_generator.sleep",
        retry_delays.append,
        raising=False,
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "llm_call_delay_seconds": 0.25,
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    assert calls == 3
    assert chunk_response.json()["worldline_status"] == "completed"
    assert worldline["provenance"]["attempt_count"] == 3
    assert worldline["provenance"]["failed_chunk_count"] == 0
    assert worldline["provenance"]["chunk_history"][0]["attempt_count"] == 3
    attempt_history = worldline["provenance"]["chunk_history"][0]["attempt_history"]
    assert [item["attempt"] for item in attempt_history] == [1, 2, 3]
    assert [item["output_validation_status"] for item in attempt_history] == [
        "invalid_json",
        "invalid_json",
        "valid_json",
    ]
    assert attempt_history[-1]["safety_check_status"] == "passed"
    assert all("raw_text" not in json.dumps(item) for item in attempt_history)
    assert worldline["days"][0]["generation_source"] == "llm_chunk"
    assert "attempt 3" in " ".join(worldline["days"][0]["quality_notes"])
    assert len(request_payloads[0]["messages"]) == 2
    assert len(request_payloads[1]["messages"]) == 3
    retry_instruction = request_payloads[1]["messages"][-1]["content"]
    assert "Previous response failed JSON parsing" in retry_instruction
    assert "not json" not in retry_instruction
    assert retry_delays == [0.25, 0.25]


def test_worldline_chunk_invalid_json_falls_back_safely(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        lambda *args, **kwargs: Response(),
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    assert chunk_response.json()["worldline_status"] == "fallback"
    assert worldline["provenance"]["output_validation_status"] == "invalid_json"
    assert worldline["provenance"]["failed_chunk_count"] == 1
    assert worldline["provenance"]["attempt_count"] == 3
    assert worldline["provenance"]["chunk_history"][0]["attempt_count"] == 3
    attempt_history = worldline["provenance"]["chunk_history"][0]["attempt_history"]
    assert len(attempt_history) == 3
    assert all(item["output_validation_status"] == "invalid_json" for item in attempt_history)
    assert all(item["response_diagnostics"]["parse_error_type"] == "no_json_object" for item in attempt_history)
    assert all("raw_text" not in json.dumps(item) for item in attempt_history)
    diagnostics = worldline["provenance"]["chunk_history"][0]["response_diagnostics"]
    assert diagnostics["response_char_count"] == len("not json")
    assert diagnostics["parse_error_type"] == "no_json_object"
    assert diagnostics["probable_truncation"] is False
    assert "raw_text" not in diagnostics
    assert "not json" not in json.dumps(diagnostics)
    assert worldline["provenance"]["llm_output_quality_notes"]
    assert worldline["provenance"]["chunk_history"][0]["status"] == "fallback"
    assert worldline["days"][0]["generation_source"] == "fallback"
    assert worldline["days"][0]["chunk_status"] == "invalid_json"
    assert worldline["days"][0]["quality_notes"]
    assert worldline["days"][0]["agent_events"]
    assert_worldline_state_continuity(worldline["days"])


def test_worldline_chunk_timeout_records_safe_request_diagnostics(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    secret_detail = "https://llm.example/v1?api_key=secret-value"

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout(secret_detail)

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        raise_timeout,
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    response_text = json.dumps(chunk_response.json())
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    history = worldline["provenance"]["chunk_history"][0]["attempt_history"]
    assert len(history) == 3
    assert all(item["request_diagnostics"]["error_category"] == "timeout" for item in history)
    assert all(item["request_diagnostics"]["retryable"] is True for item in history)
    assert secret_detail not in response_text
    assert "secret-value" not in (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")


def test_worldline_chunk_does_not_retry_non_retryable_http_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    calls = 0
    sleeps: list[float] = []

    def raise_unauthorized(*args, **kwargs):
        nonlocal calls
        calls += 1
        response = requests.Response()
        response.status_code = 401
        raise requests.HTTPError("credential detail must not persist", response=response)

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        raise_unauthorized,
    )
    monkeypatch.setattr(
        "astro_abm_api.services.worldline_llm_generator.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
            "llm_call_delay_seconds": 9,
        },
    )

    assert chunk_response.status_code == 200
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    history = worldline["provenance"]["chunk_history"][0]["attempt_history"]
    assert calls == 1
    assert sleeps == []
    assert worldline["provenance"]["attempt_count"] == 1
    assert len(history) == 1
    assert history[0]["request_diagnostics"] == {
        "error_category": "http_error",
        "failure_kind": "authentication_failed",
        "recommended_action": "check_credentials",
        "exception_type": "HTTPError",
        "retryable": False,
        "http_status": 401,
    }
    saved = (tmp_path / f"{scenario_id}.json").read_text(encoding="utf-8")
    assert "credential detail" not in saved


def test_worldline_chunk_retries_retryable_http_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    calls = 0

    def raise_unavailable(*args, **kwargs):
        nonlocal calls
        calls += 1
        response = requests.Response()
        response.status_code = 503
        raise requests.HTTPError("temporary upstream failure", response=response)

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        raise_unavailable,
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    history = worldline["provenance"]["chunk_history"][0]["attempt_history"]
    assert calls == 3
    assert len(history) == 3
    assert all(item["request_diagnostics"]["retryable"] is True for item in history)


def test_worldline_chunk_stops_after_two_consecutive_failed_chunks(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))
    calls = 0

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            nonlocal calls
            calls += 1
            return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        lambda *args, **kwargs: Response(),
    )
    client = TestClient(app)
    payload = scenario_payload()
    payload["end_date"] = "2026-07-05"
    create_response = client.post("/scenarios", json=payload)
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    responses = []
    for chunk_index, chunk_date in enumerate(
        ("2026-07-01", "2026-07-02", "2026-07-03"), start=1
    ):
        responses.append(
            client.post(
                f"/scenarios/{scenario_id}/worldline-chunks",
                json={
                    "llm_provider": "openai_compatible",
                    "llm_real_enabled": True,
                    "llm_base_url": "http://llm.local/v1",
                    "llm_model": "test-model",
                    "language": "en",
                    "chunk_start_date": chunk_date,
                    "chunk_end_date": chunk_date,
                    "chunk_index": chunk_index,
                    "total_chunks": 5,
                    "worldline_chunk_days": 1,
                },
            )
        )

    assert all(response.status_code == 200 for response in responses)
    assert calls == 6
    assert responses[0].json()["worldline_status"] == "fallback"
    assert responses[0].json()["consecutive_failed_chunk_count"] == 1
    assert responses[0].json()["generation_halted"] is False
    assert responses[1].json()["worldline_status"] == "fallback"
    assert responses[1].json()["consecutive_failed_chunk_count"] == 2
    assert responses[1].json()["generation_halted"] is True
    halted_worldline = responses[1].json()["report"]["worldline_simulation"]
    halted_history = halted_worldline["provenance"]["chunk_history"]
    assert [item["status"] for item in halted_history] == [
        "fallback",
        "fallback",
        "skipped_after_halt",
        "skipped_after_halt",
        "skipped_after_halt",
    ]
    assert halted_worldline["provenance"]["failed_chunk_count"] == 2
    assert halted_worldline["provenance"]["skipped_chunk_count"] == 3
    assert all(
        item["network_call_performed"] is False and item["attempt_count"] == 0
        for item in halted_history[2:]
    )
    assert [day["chunk_status"] for day in halted_worldline["days"][2:]] == [
        "skipped_after_halt",
        "skipped_after_halt",
        "skipped_after_halt",
    ]
    assert_worldline_state_continuity(halted_worldline["days"])
    assert responses[2].json()["worldline_status"] == "halted"
    assert responses[2].json()["generation_halted"] is True
    worldline = responses[2].json()["report"]["worldline_simulation"]
    assert worldline["provenance"]["chunk_count"] == 5
    assert len(worldline["provenance"]["chunk_history"]) == 5
    assert "two consecutive chunks" in worldline["provenance"]["halt_reason"]
    assert "retry policy" in worldline["provenance"]["halt_reason"]
    assert "three attempts" not in worldline["provenance"]["halt_reason"]


def test_worldline_chunk_unsafe_output_falls_back_without_saving_phrase(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASTRO_ABM_SCENARIO_OUTPUT_DIR", str(tmp_path))

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
                                    "summary": "unsafe",
                                    "days": [
                                        {
                                            "date": "2026-07-01",
                                            "agent_events": [
                                                {
                                                    "agent_id": "crypto_retail_fomo",
                                                    "what_happened": "must buy BTC",
                                                    "why_it_happened": "unsafe",
                                                    "impact_on_tomorrow": "unsafe",
                                                    "impact_scores": {},
                                                    "confidence": "low",
                                                    "caveats": [],
                                                }
                                            ],
                                            "causal_links": [],
                                            "next_day_update": "unsafe",
                                            "world_state_after": {},
                                        }
                                    ],
                                    "caveats": [],
                                }
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        "astro_abm_api.services.llm_client.requests.post",
        lambda *args, **kwargs: Response(),
    )
    client = TestClient(app)
    create_response = client.post("/scenarios", json=scenario_payload())
    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    chunk_response = client.post(
        f"/scenarios/{scenario_id}/worldline-chunks",
        json={
            "llm_provider": "openai_compatible",
            "llm_real_enabled": True,
            "llm_base_url": "http://llm.local/v1",
            "llm_model": "test-model",
            "language": "en",
            "chunk_start_date": "2026-07-01",
            "chunk_end_date": "2026-07-01",
            "chunk_index": 1,
            "total_chunks": 1,
            "worldline_chunk_days": 1,
        },
    )

    assert chunk_response.status_code == 200
    response_text = json.dumps(chunk_response.json())
    worldline = chunk_response.json()["report"]["worldline_simulation"]
    assert chunk_response.json()["worldline_status"] == "fallback"
    assert worldline["provenance"]["safety_check_status"] == "failed"
    assert worldline["provenance"]["safety_violation_codes"] == ["trading_instruction"]
    assert worldline["provenance"]["chunk_history"][0]["attempt_history"][0][
        "safety_violation_codes"
    ] == ["trading_instruction"]
    assert "must buy BTC" not in response_text


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
