from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from astro_abm_api.models.report import DailyDataCoverage, DailyResearchSignals


RESEARCH_OUTPUT_ROOT_ENV = "ASTRO_ABM_RESEARCH_OUTPUT_ROOT"


@dataclass(frozen=True)
class DailyResearchContext:
    coverage: DailyDataCoverage
    signals: DailyResearchSignals


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_research_output_root() -> Path:
    configured = os.getenv(RESEARCH_OUTPUT_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return repo_root() / "astro_research" / "output"


class DailyResearchContextProvider:
    """Read local daily research context without mutating stores or fetching data."""

    def __init__(self, output_root: Path | str | None = None) -> None:
        self.output_root = (
            Path(output_root).expanduser().resolve()
            if output_root
            else default_research_output_root()
        )
        self._tables: dict[str, Any | None] = {}
        self._table_status: dict[str, str] = {}

    def context_for_date(
        self,
        current_date: date,
        *,
        assets: list[str],
        fallback_stress_regime: str,
        fallback_volatility_regime: str,
        fallback_liquidity_regime: str,
        fallback_astro_activity: str,
    ) -> DailyResearchContext:
        astro = self._row_for_day("astro_daily", current_date)
        stress = self._row_for_day("financial_stress_daily", current_date)
        market = [
            row
            for row in self._rows_for_day("market_daily", current_date)
            if str(row.get("asset")) in set(assets)
        ]
        macro = self._rows_for_day("macro_daily", current_date)

        coverage = DailyDataCoverage(
            astro_daily=self._coverage_status("astro_daily", current_date, astro is not None),
            financial_stress_daily=self._coverage_status(
                "financial_stress_daily", current_date, stress is not None
            ),
            market_daily=self._coverage_status(
                "market_daily", current_date, bool(market), asset_filtered=True
            ),
            macro_daily=self._coverage_status("macro_daily", current_date, bool(macro)),
            source="placeholder_fallback",
            notes=[],
        )

        stress_regime = fallback_stress_regime
        volatility_regime = fallback_volatility_regime
        liquidity_regime = fallback_liquidity_regime
        astro_activity = fallback_astro_activity
        notes: list[str] = []

        if stress:
            stress_regime = _clean_symbol(stress.get("stress_regime")) or stress_regime
            volatility_regime = _volatility_regime_from_stress(stress, volatility_regime)
            liquidity_regime = _liquidity_regime_from_stress(stress, liquidity_regime)
            notes.append("financial_stress_daily local snapshot used for stress and volatility tags")

        if astro:
            astro_activity = _astro_activity_from_features(astro, astro_activity)
            notes.append("astro_daily_features local snapshot used for astro activity tags")

        if market:
            volatility_regime = _volatility_regime_from_market(market, volatility_regime)
            notes.append("market_daily_features local snapshot found for selected assets")

        if macro:
            notes.append("macro_daily_observations local snapshot found for this date")

        coverage_values = [
            coverage.astro_daily,
            coverage.financial_stress_daily,
            coverage.market_daily,
            coverage.macro_daily,
        ]
        available_count = coverage_values.count("available")
        if available_count:
            coverage.source = "local_research_snapshot"
        coverage.notes = notes + self._coverage_notes(coverage)

        data_quality = "placeholder_fallback"
        if available_count == 4:
            data_quality = "local_research_available"
        elif available_count:
            data_quality = "partial_local_research_available"

        return DailyResearchContext(
            coverage=coverage,
            signals=DailyResearchSignals(
                stress_regime=stress_regime,
                volatility_regime=volatility_regime,
                liquidity_regime=liquidity_regime,
                astro_activity=astro_activity,
                data_quality=data_quality,
            ),
        )

    def _coverage_notes(self, coverage: DailyDataCoverage) -> list[str]:
        notes: list[str] = []
        for label, status in (
            ("astro_daily", coverage.astro_daily),
            ("financial_stress_daily", coverage.financial_stress_daily),
            ("market_daily", coverage.market_daily),
            ("macro_daily", coverage.macro_daily),
        ):
            if status == "missing":
                notes.append(f"{label} missing for this date; placeholder tag retained")
            elif status == "future_placeholder":
                notes.append(f"{label} does not cover this future date; placeholder tag retained")
            elif status == "unknown":
                notes.append(f"{label} availability unknown; placeholder tag retained")
        if not notes:
            notes.append("local research context is read-only and used for association tags only")
        return notes

    def _row_for_day(self, table_name: str, current_date: date) -> dict[str, Any] | None:
        rows = self._rows_for_day(table_name, current_date)
        return rows[0] if rows else None

    def _rows_for_day(self, table_name: str, current_date: date) -> list[dict[str, Any]]:
        frame = self._load_table(table_name)
        if frame is None or frame.empty or "date_key" not in frame.columns:
            return []
        rows = frame[frame["date_key"] == current_date.isoformat()]
        return rows.to_dict("records")

    def _coverage_status(
        self,
        table_name: str,
        current_date: date,
        has_exact_row: bool,
        *,
        asset_filtered: bool = False,
    ) -> str:
        if has_exact_row:
            return "available"
        status = self._table_status.get(table_name, "missing")
        if status != "available":
            return status
        frame = self._load_table(table_name)
        if frame is None or frame.empty or "date_key" not in frame.columns:
            return "unknown"
        min_date = str(frame["date_key"].min())
        max_date = str(frame["date_key"].max())
        if current_date.isoformat() > max_date:
            return "future_placeholder"
        if current_date.isoformat() < min_date:
            return "missing"
        if asset_filtered:
            return "missing"
        return "missing"

    def _load_table(self, table_name: str):
        if table_name in self._tables:
            return self._tables[table_name]
        try:
            frame = self._read_table(table_name)
        except Exception:
            self._table_status[table_name] = "unknown"
            self._tables[table_name] = None
            return None
        if frame is None or frame.empty:
            self._table_status[table_name] = "missing"
            self._tables[table_name] = None
            return None
        frame = frame.copy()
        if "ts" not in frame.columns:
            self._table_status[table_name] = "unknown"
            self._tables[table_name] = None
            return None
        try:
            import pandas as pd

            frame["date_key"] = pd.to_datetime(frame["ts"], utc=True).dt.date.astype(str)
        except Exception:
            self._table_status[table_name] = "unknown"
            self._tables[table_name] = None
            return None
        self._table_status[table_name] = "available"
        self._tables[table_name] = frame
        return frame

    def _read_table(self, table_name: str):
        path = self._table_path(table_name)
        if path is None:
            return None
        import pandas as pd

        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    def _table_path(self, table_name: str) -> Path | None:
        candidates = {
            "astro_daily": (
                self.output_root / "parquet/astro_daily_1926_2025/astro_daily_features.parquet",
                self.output_root / "parquet/astro_daily_1926_2025/astro_daily_features.csv",
                self.output_root / "parquet/astro_daily/astro_daily_features.parquet",
                self.output_root / "parquet/astro_daily/astro_daily_features.csv",
            ),
            "financial_stress_daily": (
                self.output_root / "parquet/financial_stress/financial_stress_daily.parquet",
                self.output_root / "parquet/financial_stress/financial_stress_daily.csv",
            ),
            "market_daily": (
                self.output_root / "parquet/market_daily/market_daily_features.parquet",
                self.output_root / "parquet/market_daily/market_daily_features.csv",
            ),
            "macro_daily": (
                self.output_root / "parquet/macro_daily/macro_daily_observations.parquet",
                self.output_root / "parquet/macro_daily/macro_daily_observations.csv",
            ),
        }
        for path in candidates[table_name]:
            if path.exists() and path.stat().st_size > 0:
                return path
        return None


def _clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "nan":
        return None
    return text


def _float_value(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _volatility_regime_from_stress(row: dict[str, Any], fallback: str) -> str:
    score = _float_value(row.get("vol_stress_score"))
    if score is None:
        return fallback
    if score >= 0.7:
        return "expanded"
    if score >= 0.35:
        return "normal"
    return "compressed"


def _liquidity_regime_from_stress(row: dict[str, Any], fallback: str) -> str:
    score = _float_value(row.get("cross_asset_stress_score"))
    if score is None:
        return fallback
    if score >= 0.7:
        return "thin"
    if score >= 0.35:
        return "selective"
    return "orderly"


def _volatility_regime_from_market(rows: list[dict[str, Any]], fallback: str) -> str:
    if any(bool(row.get("is_extreme_absret_95")) for row in rows):
        return "expanded"
    values = [_float_value(row.get("realized_vol_20d")) for row in rows]
    values = [value for value in values if value is not None]
    if values:
        return fallback if fallback != "unknown" else "normal"
    return fallback


def _astro_activity_from_features(row: dict[str, Any], fallback: str) -> str:
    active_retrograde = _float_value(row.get("active_retrograde_count")) or 0
    station_cluster = _float_value(row.get("station_cluster_count_7d")) or 0
    aspect_cluster = _float_value(row.get("major_aspect_cluster_count_7d")) or 0
    if active_retrograde >= 3 or station_cluster >= 2 or aspect_cluster >= 3:
        return "high"
    if active_retrograde >= 1 or station_cluster >= 1 or aspect_cluster >= 1:
        return "medium"
    return fallback if fallback != "unknown" else "low"
