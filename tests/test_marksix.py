from __future__ import annotations

import gzip
from pathlib import Path

from astro_abm import marksix


CSV = b"""draw_id,draw_year,draw_number_in_year,draw_date,has_results,is_snowball_draw,draw_type_name,ball_1,ball_2,ball_3,ball_4,ball_5,ball_6,extra_ball,total_sales,jackpot_amount,first_prize_dividend
2026001N,2026,1,2026-01-02,true,false,Normal,1,2,3,4,5,6,7,1000,200,50
"""


def test_parse_gzip_history_csv() -> None:
    draws = marksix.parse_history_csv(gzip.compress(CSV))
    assert len(draws) == 1
    assert draws[0].numbers == (1, 2, 3, 4, 5, 6)
    assert draws[0].extra_number == 7


def test_parse_legacy_history_without_inventing_dates() -> None:
    html = (
        "<table><tr>" + "".join(
            f"<td><b><font>{value}</font></b></td>"
            for value in [1976, 1, 3, 13, 14, 16, 22, 28, 34]
        ) + "</tr></table>"
    ).encode("big5")
    draws = marksix.parse_legacy_history_html(html, expected_year=1976)
    assert len(draws) == 1
    assert draws[0].draw_date is None
    assert draws[0].numbers == (3, 13, 14, 16, 22, 28)


def test_sync_is_idempotent_and_official_overrides(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "marksix.sqlite3"
    historical = marksix.parse_history_csv(CSV)
    official = marksix.MarkSixDraw(
        draw_id="2026001N", draw_date="2026-01-02", draw_year=2026,
        draw_number=1, numbers=(1, 2, 3, 4, 5, 6), extra_number=7,
        source="hkjc_official", source_url=marksix.OFFICIAL_PAGE,
        source_is_official=True,
    )
    monkeypatch.setattr(marksix, "fetch_history", lambda: historical)
    monkeypatch.setattr(marksix, "fetch_legacy_history", lambda: [])
    monkeypatch.setattr(marksix, "fetch_official_latest", lambda: [official])

    marksix.sync_marksix(full_history=True, path=path)
    marksix.sync_marksix(full_history=True, path=path)

    status = marksix.database_status(path)
    assert status["total_draws"] == 1
    assert status["official_verified_draws"] == 1
    assert marksix.list_draws(path=path)[0]["source"] == "hkjc_official"


def test_worldline_numbers_are_valid_and_seeded() -> None:
    first = marksix.generate_worldlines(horizon_draws=3, worldline_count=2, seed="fixed")
    second = marksix.generate_worldlines(horizon_draws=3, worldline_count=2, seed="fixed")
    assert first == second
    for worldline in first:
        for draw in worldline["draws"]:
            values = [*draw["numbers"], draw["extra_number"]]
            assert len(values) == len(set(values)) == 7
            assert all(1 <= value <= 49 for value in values)
