from pathlib import Path
import logging
import stat

import pytest

from astro_abm_api.services import scenario_store


def test_atomic_write_replaces_complete_file_and_cleans_temporary(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)

    scenario_store._atomic_write_text(target, "new-complete-json")

    assert target.read_text(encoding="utf-8") == "new-complete-json"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert list(tmp_path.glob(".scenario.json.*.tmp")) == []


def test_atomic_write_preserves_previous_file_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "scenario.json"
    target.write_text("old-valid-json", encoding="utf-8")

    def fail_replace(_source, _target) -> None:
        raise OSError("simulated replace interruption")

    monkeypatch.setattr(scenario_store.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace interruption"):
        scenario_store._atomic_write_text(target, "new-but-not-committed")

    assert target.read_text(encoding="utf-8") == "old-valid-json"
    assert list(tmp_path.glob(".scenario.json.*.tmp")) == []


def test_list_summaries_logs_safe_diagnostic_for_invalid_json(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "broken_report.json"
    invalid.write_text('{"secret": "must-not-appear"', encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=scenario_store.__name__):
        summaries = scenario_store.ScenarioStore(tmp_path).list_summaries()

    assert summaries == []
    assert "broken_report.json" in caplog.text
    assert "invalid_json" in caplog.text
    assert "must-not-appear" not in caplog.text


def test_list_summaries_does_not_log_invalid_report_values(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "legacy_report.json"
    invalid.write_text('{"title": "private-title-not-for-logs"}', encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=scenario_store.__name__):
        summaries = scenario_store.ScenarioStore(tmp_path).list_summaries()

    assert summaries == []
    assert "legacy_report.json" in caplog.text
    assert "invalid_report_schema" in caplog.text
    assert "private-title-not-for-logs" not in caplog.text
