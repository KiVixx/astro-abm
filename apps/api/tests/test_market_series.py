from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from astro_abm_api.main import app
from astro_abm_api.services.daily_research_context import DailyResearchContextProvider


def _register(client: TestClient, username: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": "correct-horse-battery-staple",
            "display_name": username,
        },
    )
    assert response.status_code == 201
    return str(response.json()["csrf_token"])


def _create_payload(symbol: str = "TSLA") -> dict[str, object]:
    return {
        "symbol": symbol,
        "label": "Tesla" if symbol == "TSLA" else symbol,
        "asset_type": "equity",
        "provider": "yahoo",
        "provider_symbol": symbol,
        "currency": "USD",
        "market_timezone": "America/New_York",
        "visibility": "private",
        "maintenance_enabled": True,
    }


def _write_tsla(root: Path) -> None:
    path = root / "equity" / "tsla_daily.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": ["2026-07-20", "2026-07-21"],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "adj_close": [101, 102],
            "volume": [1000, 1200],
        }
    ).to_csv(path, index=False)


def test_market_series_requires_login_and_csrf() -> None:
    client = TestClient(app)
    assert client.post("/market-series", json=_create_payload()).status_code == 401

    _register(client, "market-owner")
    assert client.post("/market-series", json=_create_payload()).status_code == 403


def test_tsla_adoption_appears_in_assets(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "market-data"
    monkeypatch.setenv("ASTRO_ABM_MARKET_SERIES_DATA_ROOT", str(data_root))
    _write_tsla(data_root)
    client = TestClient(app)
    csrf = _register(client, "tsla-owner")

    created = client.post(
        "/market-series",
        json=_create_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "active"
    assert body["row_count"] == 2
    assert "data_path" not in body
    assert "owner_id" not in body

    assets = client.get("/assets").json()
    tsla = next(item for item in assets if item["asset"] == "TSLA")
    assert tsla["supported"] is True
    assert tsla["market_daily_supported"] is True


def test_market_series_owner_isolation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "market-data"
    monkeypatch.setenv("ASTRO_ABM_MARKET_SERIES_DATA_ROOT", str(data_root))
    _write_tsla(data_root)
    owner = TestClient(app)
    owner_csrf = _register(owner, "owner-one")
    created = owner.post(
        "/market-series",
        json=_create_payload(),
        headers={"X-CSRF-Token": owner_csrf},
    ).json()

    other = TestClient(app)
    other_csrf = _register(other, "owner-two")
    response = other.patch(
        f"/market-series/{created['series_id']}",
        json={"enabled": False},
        headers={"X-CSRF-Token": other_csrf},
    )
    assert response.status_code == 404


def test_invalid_symbol_and_provider_are_rejected() -> None:
    client = TestClient(app)
    csrf = _register(client, "validation-owner")

    traversal = client.post(
        "/market-series",
        json={**_create_payload(), "symbol": "../../TSLA"},
        headers={"X-CSRF-Token": csrf},
    )
    provider = client.post(
        "/market-series",
        json={**_create_payload(), "provider": "https://example.com"},
        headers={"X-CSRF-Token": csrf},
    )

    assert traversal.status_code == 422
    assert provider.status_code == 422


def test_custom_series_daily_context_reports_available_and_future_coverage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "market-data"
    monkeypatch.setenv("ASTRO_ABM_MARKET_SERIES_DATA_ROOT", str(data_root))
    _write_tsla(data_root)
    client = TestClient(app)
    csrf = _register(client, "context-owner")
    response = client.post(
        "/market-series",
        json=_create_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201

    provider = DailyResearchContextProvider(output_root=tmp_path / "empty-output")
    historical = provider.context_for_date(
        pd.Timestamp("2026-07-21").date(),
        assets=["TSLA"],
        fallback_stress_regime="watchful",
        fallback_volatility_regime="normal",
        fallback_liquidity_regime="selective",
        fallback_astro_activity="medium",
    )
    future = provider.context_for_date(
        pd.Timestamp("2026-07-23").date(),
        assets=["TSLA"],
        fallback_stress_regime="watchful",
        fallback_volatility_regime="normal",
        fallback_liquidity_regime="selective",
        fallback_astro_activity="medium",
    )

    assert historical.asset_market_status == {"TSLA": "available"}
    assert historical.asset_market_source == {"TSLA": "custom_market_series"}
    assert future.asset_market_status == {"TSLA": "future_placeholder"}
    assert future.asset_market_source == {"TSLA": "custom_market_series"}
