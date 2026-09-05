from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_accounts_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRO_ABM_ACCOUNTS_DB_PATH", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv(
        "ASTRO_ABM_MARKET_SERIES_DB_PATH",
        str(tmp_path / "market-series.sqlite3"),
    )
    monkeypatch.setenv(
        "ASTRO_ABM_MARKET_SERIES_DATA_ROOT",
        str(tmp_path / "market-data"),
    )
    monkeypatch.setenv("ASTRO_ABM_ENV", "development")
    monkeypatch.setenv("ASTRO_ABM_MARKSIX_DB_PATH", str(tmp_path / "marksix.sqlite3"))
