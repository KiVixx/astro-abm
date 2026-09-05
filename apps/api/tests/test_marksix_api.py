from __future__ import annotations

from fastapi.testclient import TestClient

from astro_abm.marksix import MarkSixDraw, _connect, _upsert
from astro_abm import marksix_astro
from types import SimpleNamespace
from astro_abm_api.main import app


def _seed_draw() -> None:
    with _connect() as connection:
        _upsert(connection, [
            MarkSixDraw(
                draw_id="2026001N", draw_date="2026-01-02", draw_year=2026,
                draw_number=1, numbers=(1, 2, 3, 4, 5, 6), extra_number=7,
                source="hkjc_official", source_is_official=True,
            )
        ])
        connection.commit()


def test_marksix_status_draws_and_frequencies() -> None:
    _seed_draw()
    client = TestClient(app)
    status = client.get("/marksix/status")
    assert status.status_code == 200
    assert status.json()["total_draws"] == 1
    draws = client.get("/marksix/draws?limit=1")
    assert draws.status_code == 200
    assert draws.json()[0]["numbers"] == [1, 2, 3, 4, 5, 6]
    frequencies = client.get("/marksix/frequencies")
    assert frequencies.status_code == 200
    assert frequencies.json()[0]["main_count"] == 1


def test_marksix_worldline_is_bounded_and_disclaimed() -> None:
    _seed_draw()
    client = TestClient(app)
    response = client.post("/marksix/worldlines", json={
        "horizon_draws": 3, "worldline_count": 2, "seed": "api-test", "language": "zh-Hant",
    })
    assert response.status_code == 200
    body = response.json()
    assert len(body["worldlines"]) == 2
    assert len(body["worldlines"][0]["draws"]) == 3
    assert "機率相同" in body["worldlines"][0]["disclaimer"]


def test_marksix_worldline_rejects_unbounded_request() -> None:
    response = TestClient(app).post("/marksix/worldlines", json={
        "horizon_draws": 30, "worldline_count": 20,
    })
    assert response.status_code == 422


def test_marksix_astro_research_endpoint(monkeypatch) -> None:
    _seed_draw()
    monkeypatch.setattr(
        marksix_astro,
        "SwissEphemerisBackend",
        lambda: SimpleNamespace(get_position=lambda body, ts: SimpleNamespace(lon_speed_deg_day=-1.0)),
    )
    response = TestClient(app).get("/marksix/astro-research?body=Mercury&condition=retrograde")
    assert response.status_code == 200
    payload = response.json()
    assert payload["body"] == "Mercury"
    assert len(payload["numbers"]) == 49


def test_marksix_astro_research_rejects_unknown_body() -> None:
    response = TestClient(app).get("/marksix/astro-research?body=Earth")
    assert response.status_code == 400
