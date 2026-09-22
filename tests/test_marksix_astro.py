from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from datetime import date

from astro_abm import marksix
from astro_abm import marksix_astro


class _FakeEphemeris:
    def get_position(self, _body: str, ts):
        return SimpleNamespace(lon_speed_deg_day=-1.0 if ts.day % 2 == 0 else 1.0)


def _seed(path: Path) -> None:
    draws = []
    for index, draw_date in enumerate(["2002-07-04", "2002-07-05", "2002-07-06", "2002-07-07"]):
        numbers = (1, 2, 3, 4, 5, 6) if index % 2 == 0 else (7, 8, 9, 10, 11, 12)
        draws.append(marksix.MarkSixDraw(
            draw_id=f"2002{index + 1:03d}N", draw_date=draw_date, draw_year=2002,
            draw_number=index + 1, numbers=numbers, extra_number=49,
        ))
    with marksix._connect(path) as connection:
        marksix._upsert(connection, draws)
        connection.commit()


def test_retrograde_number_analysis_separates_condition_and_baseline(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "marksix.sqlite3"
    _seed(path)
    monkeypatch.setattr(marksix_astro, "SwissEphemerisBackend", _FakeEphemeris)

    result = marksix_astro.analyze_retrograde_numbers(path=path)

    assert result["total_draws"] == 4
    assert result["condition_draws"] == 2
    assert result["baseline_draws"] == 2
    number_one = result["numbers"][0]
    assert number_one["condition_rate"] == 1.0
    assert number_one["baseline_rate"] == 0.0
    assert len(result["numbers"]) == 49
    assert all(0 <= item["q_value_fdr"] <= 1 for item in result["numbers"])


def test_current_rule_era_excludes_older_draws(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "marksix.sqlite3"
    _seed(path)
    with marksix._connect(path) as connection:
        marksix._upsert(connection, [marksix.MarkSixDraw(
            draw_id="2001001N", draw_date="2001-01-01", draw_year=2001, draw_number=1,
            numbers=(1, 2, 3, 4, 5, 6), extra_number=7,
        )])
        connection.commit()
    monkeypatch.setattr(marksix_astro, "SwissEphemerisBackend", _FakeEphemeris)

    result = marksix_astro.analyze_retrograde_numbers(path=path)
    assert result["total_draws"] == 4


def test_motion_phase_calendar_distinguishes_station_and_core_windows() -> None:
    class Backend:
        def get_position(self, _body: str, ts):
            retrograde = date(2026, 1, 10) <= ts.date() < date(2026, 1, 30)
            return SimpleNamespace(lon_speed_deg_day=-1.0 if retrograde else 1.0)

    phases = marksix_astro._motion_phase_calendar(
        body="Mercury", start=date(2026, 1, 1), end=date(2026, 2, 10), backend=Backend(),
    )
    assert phases["2026-01-05"][1] == "pre_station"
    assert phases["2026-01-10"][1] == "retrograde_entry"
    assert phases["2026-01-20"][1] == "retrograde_core"
    assert phases["2026-01-26"][1] == "retrograde_exit"
    assert phases["2026-02-05"][1] == "post_station"


def test_moon_phase_zones_wrap_and_classify_quarters() -> None:
    assert marksix_astro._moon_phase_label(359) == "new_moon_zone"
    assert marksix_astro._moon_phase_label(90) == "first_quarter_zone"
    assert marksix_astro._moon_phase_label(180) == "full_moon_zone"
    assert marksix_astro._moon_phase_label(270) == "last_quarter_zone"


def test_moon_phase_number_analysis(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "marksix.sqlite3"
    _seed(path)

    class MoonBackend:
        def get_position(self, body: str, ts):
            angle = {4: 0, 5: 90, 6: 180, 7: 270}[ts.day]
            return SimpleNamespace(lon_deg=angle if body == "Moon" else 0.0)

    monkeypatch.setattr(marksix_astro, "SwissEphemerisBackend", MoonBackend)
    result = marksix_astro.analyze_moon_phase_numbers(
        condition="full_moon_zone", path=path,
    )
    assert result["context_type"] == "moon_phase"
    assert result["condition_draws"] == 1
    assert result["numbers"][0]["condition_rate"] == 1.0


def test_planetary_snapshot_includes_all_llm_selectable_bodies(monkeypatch) -> None:
    class SnapshotBackend:
        def get_position(self, body: str, _ts):
            body_index = marksix_astro.SNAPSHOT_BODIES.index(body) if body in marksix_astro.SNAPSHOT_BODIES else 0
            return SimpleNamespace(
                lon_deg=float(body_index * 20),
                lon_speed_deg_day=-0.5 if body == "Mercury" else 0.5,
            )

    monkeypatch.setattr(marksix_astro, "SwissEphemerisBackend", SnapshotBackend)
    snapshot = marksix_astro.planetary_snapshot(date(2026, 9, 24))

    assert [row["body"] for row in snapshot["planets"]] == list(marksix_astro.SNAPSHOT_BODIES)
    assert [row["body"] for row in snapshot["luminaries"]] == ["Sun", "Moon"]
    assert next(row for row in snapshot["planets"] if row["body"] == "Mercury")["is_retrograde"] is True
    assert snapshot["moon_phase_zone"] in {
        "new_moon_zone", "waxing_crescent", "first_quarter_zone", "waxing_gibbous",
        "full_moon_zone", "waning_gibbous", "last_quarter_zone", "waning_crescent",
    }
