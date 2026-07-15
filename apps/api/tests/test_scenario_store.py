from pathlib import Path

import pytest

from astro_abm_api.services import scenario_store


def test_atomic_write_replaces_complete_file_and_cleans_temporary(tmp_path: Path) -> None:
    target = tmp_path / "scenario.json"
    target.write_text("old", encoding="utf-8")

    scenario_store._atomic_write_text(target, "new-complete-json")

    assert target.read_text(encoding="utf-8") == "new-complete-json"
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
