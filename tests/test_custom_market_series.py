from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from astro_abm.market_series import (
    MarketSeriesStore,
    refresh_market_series,
    run_custom_market_series_maintenance,
)


def _price_csv(path: Path, dates: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": dates,
            "open": [100 + index for index in range(len(dates))],
            "high": [101 + index for index in range(len(dates))],
            "low": [99 + index for index in range(len(dates))],
            "close": [100 + index for index in range(len(dates))],
            "adj_close": [100 + index for index in range(len(dates))],
            "volume": [1000] * len(dates),
        }
    ).to_csv(path, index=False)


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        timestamps = [
            int(pd.Timestamp("2026-07-21T20:00:00Z").timestamp()),
            int(pd.Timestamp("2026-07-22T20:00:00Z").timestamp()),
        ]
        return {
            "chart": {
                "error": None,
                "result": [
                    {
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [
                                {
                                    "open": [102.0, 103.0],
                                    "high": [104.0, 105.0],
                                    "low": [101.0, 102.0],
                                    "close": [103.0, 104.0],
                                    "volume": [1100, 1200],
                                }
                            ],
                            "adjclose": [{"adjclose": [103.0, 104.0]}],
                        },
                    }
                ],
            }
        }


class _Session:
    def get(self, *_args, **_kwargs) -> _Response:
        return _Response()


def test_existing_tsla_file_is_adopted_without_duplicate_copy(tmp_path: Path) -> None:
    _price_csv(
        tmp_path / "equity" / "tsla_daily.csv",
        ["2026-07-20", "2026-07-21"],
    )
    store = MarketSeriesStore(tmp_path / "registry.sqlite3", tmp_path)

    record = store.register(
        owner_id="user-one",
        symbol="TSLA",
        label="Tesla",
        asset_type="equity",
        provider="yahoo",
        provider_symbol="TSLA",
        currency="USD",
        market_timezone="America/New_York",
        visibility="private",
        maintenance_enabled=True,
    )

    assert record.status == "active"
    assert record.row_count == 2
    assert record.data_path == "equity/tsla_daily.csv"
    assert not (tmp_path / "market_series" / "yahoo").exists()


def test_incremental_refresh_deduplicates_overlap(tmp_path: Path) -> None:
    store = MarketSeriesStore(tmp_path / "registry.sqlite3", tmp_path)
    record = store.register(
        owner_id="user-one",
        symbol="NVDA",
        label="NVIDIA",
        asset_type="equity",
        provider="yahoo",
        provider_symbol="NVDA",
        currency="USD",
        market_timezone="America/New_York",
        visibility="private",
        maintenance_enabled=True,
    )
    _price_csv(
        store.data_path(record),
        ["2026-07-20", "2026-07-21"],
    )
    store.adopt_existing_if_available(record.series_id)

    result = refresh_market_series(
        store,
        record.series_id,
        end=date(2026, 7, 22),
        session=_Session(),
    )
    frame = pd.read_csv(store.data_path(store.get(record.series_id)))

    assert result.status == "active"
    assert result.fetched_rows == 2
    assert frame["date"].tolist() == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
    ]
    assert not frame["date"].duplicated().any()


def test_maintenance_isolates_failure_and_pauses_after_three_attempts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = MarketSeriesStore(tmp_path / "registry.sqlite3", tmp_path)
    record = store.register(
        owner_id="user-one",
        symbol="BAD",
        label="Unavailable",
        asset_type="equity",
        provider="yahoo",
        provider_symbol="BAD",
        currency="USD",
        market_timezone="America/New_York",
        visibility="private",
        maintenance_enabled=True,
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr("astro_abm.market_series._fetch_yahoo_daily", fail)
    for _ in range(3):
        run_custom_market_series_maintenance(
            store=store,
            end=date(2026, 7, 22),
            attempts=1,
        )

    failed = store.get(record.series_id)
    assert failed.status == "maintenance_failed"
    assert failed.consecutive_failures == 3
    assert store.list_for_maintenance() == []
