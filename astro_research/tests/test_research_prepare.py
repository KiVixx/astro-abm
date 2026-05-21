from __future__ import annotations

from pathlib import Path

from research.prepare import LOCAL_DATA_FILES, prepare_research


def test_public_mode_uses_fred_only_market_path(tmp_path: Path):
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        return 0

    result = prepare_research(root=tmp_path, mode="public", end="2021-12-31", runner=runner)

    assert result.status == "completed"
    assert result.report_markdown_path.exists()
    market_calls = [call for call in calls if "scripts/build_market_daily.py" in call]
    assert len(market_calls) == 1
    assert "--source" in market_calls[0]
    assert "fred" in market_calls[0]
    assert not any("scripts/build_astro_daily.py" in call and "--aspect-profile" in call for call in calls)
    assert any("scripts/build_research_duckdb.py" in call for call in calls)


def test_local_full_missing_local_data_warns_but_continues(tmp_path: Path):
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        return 0

    result = prepare_research(root=tmp_path, mode="local-full", end="2021-12-31", runner=runner)

    assert result.status == "completed_with_warnings"
    assert any("missing optional long-history local CSV" in warning for warning in result.warnings)
    market_call = next(call for call in calls if "scripts/build_market_daily.py" in call)
    assert "--source" not in market_call


def test_local_full_strict_missing_local_data_fails_without_commands(tmp_path: Path):
    calls: list[list[str]] = []

    result = prepare_research(
        root=tmp_path,
        mode="local-full",
        strict_local_data=True,
        runner=lambda command: calls.append(list(command)) or 0,
    )

    assert result.status == "failed"
    assert calls == []


def test_formal_mode_adds_aspects_events_and_hypotheses(tmp_path: Path):
    for rel_path in LOCAL_DATA_FILES.values():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("date,close\n2020-01-01,100\n")
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        return 0

    result = prepare_research(root=tmp_path, mode="formal", workers=3, end="2021-12-31", runner=runner)

    assert result.status == "completed"
    aspect_call = next(call for call in calls if "scripts/build_astro_daily.py" in call and "--aspect-profile" in call)
    assert "--workers" in aspect_call
    assert "3" in aspect_call
    assert any("scripts/build_research_events.py" in call for call in calls)
    assert any("scripts/register_hypotheses.py" in call for call in calls)
    assert not any("scripts/run_research_batch.py" in call for call in calls)


def test_formal_mode_can_run_exploratory_batch(tmp_path: Path):
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        return 0

    result = prepare_research(root=tmp_path, mode="formal", run_batch=True, end="2021-12-31", runner=runner)

    assert result.status == "completed_with_warnings"
    batch_call = next(call for call in calls if "scripts/run_research_batch.py" in call)
    assert "astro_research/configs/research_batch_exploratory_v1.yaml" in batch_call
    validation_call = next(call for call in calls if "scripts/validate_research_layer.py" in call)
    assert any("exploratory_formal_batch_v1_1926_2025/results.parquet" in item for item in validation_call)


def test_dry_run_writes_plan_without_executing_commands(tmp_path: Path):
    calls: list[list[str]] = []

    result = prepare_research(root=tmp_path, mode="public", dry_run=True, runner=lambda command: calls.append(list(command)) or 0)

    assert result.status == "completed"
    assert calls == []
    assert all(step.status in {"completed", "skipped"} for step in result.steps)
    assert result.report_json_path.exists()
