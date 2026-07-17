from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from astro_abm_api.models.report import (
    DailyDataCoverage,
    DailyResearchSignals,
    DailyRetrogradeBodyContext,
    DailyRetrogradeContext,
)


RESEARCH_OUTPUT_ROOT_ENV = "ASTRO_ABM_RESEARCH_OUTPUT_ROOT"
EPHEMERIS_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)
RETROGRADE_BODIES = (
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)
MAJOR_ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}


@dataclass(frozen=True)
class DailyResearchContext:
    coverage: DailyDataCoverage
    signals: DailyResearchSignals
    retrograde_context: DailyRetrogradeContext


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
        if astro is None:
            astro = self._computed_ephemeris_row(current_date)
        astro_source = (
            "computed_ephemeris"
            if astro and astro.get("_computed_ephemeris")
            else "local_snapshot"
        )
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
            if astro_source == "computed_ephemeris":
                notes.append("computed Swiss Ephemeris daily astro context used for astro activity tags")
            else:
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
            if astro_source == "computed_ephemeris" and available_count == 1:
                coverage.source = "computed_ephemeris"
            elif astro_source == "computed_ephemeris":
                coverage.source = "mixed_computed_research"
            else:
                coverage.source = "local_research_snapshot"
        coverage.notes = notes + self._coverage_notes(coverage)

        data_quality = "placeholder_fallback"
        if astro_source == "computed_ephemeris" and available_count == 1:
            data_quality = "computed_ephemeris_available"
        elif available_count == 4:
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
            retrograde_context=self._retrograde_context_for_date(current_date, astro),
        )

    def _retrograde_context_for_date(
        self,
        current_date: date,
        astro_row: dict[str, Any] | None,
    ) -> DailyRetrogradeContext:
        computed = self._computed_ephemeris_row(current_date)
        details = computed.get("_ephemeris_details", {}) if computed else {}
        positions = {
            str(item.get("body")): item
            for item in details.get("bodies", [])
            if isinstance(item, dict) and item.get("body")
        }
        cycles = _cycles_with_computed_fallback(current_date, self._retrograde_cycles())
        bodies = [
            self._retrograde_body_context(
                current_date,
                body=body,
                astro_row=astro_row,
                position=positions.get(body),
                cycles=cycles,
            )
            for body in RETROGRADE_BODIES
        ]
        has_station_cycles = any(item.cycle_id or item.nearest_station_ts for item in bodies)
        has_positions = all(item.lon_speed_deg_day is not None for item in bodies)
        if has_positions and has_station_cycles:
            source = "retrograde_cycles_and_computed_ephemeris"
            quality = "station_timing_with_computed_position"
        elif has_positions:
            source = "computed_ephemeris"
            quality = "computed_position_only"
        elif has_station_cycles:
            source = "local_retrograde_cycles"
            quality = "canonical_station_only"
        else:
            source = "unavailable"
            quality = "missing"
        notes = [
            "Retrograde context is astronomical timing context only and does not imply market causality.",
        ]
        if not has_station_cycles:
            notes.append(
                "Canonical station-cycle coverage was unavailable; station and cycle fields remain empty."
            )
        if not has_positions:
            notes.append(
                "Swiss Ephemeris position calculation was unavailable; no position values were invented."
            )
        return DailyRetrogradeContext(
            bodies=bodies,
            source=source,
            data_quality=quality,
            notes=notes,
        )

    def _retrograde_body_context(
        self,
        current_date: date,
        *,
        body: str,
        astro_row: dict[str, Any] | None,
        position: dict[str, Any] | None,
        cycles: list[dict[str, Any]],
    ) -> DailyRetrogradeBodyContext:
        body_key = body.lower()
        speed = _float_value(position.get("lon_speed_deg_day")) if position else None
        is_retrograde = bool(position.get("is_retrograde")) if position else None
        phase = _clean_symbol(astro_row.get(f"{body_key}_phase")) if astro_row else None
        cycle_id = _clean_symbol(astro_row.get(f"{body_key}_cycle_id")) if astro_row else None
        matching_cycle = _cycle_for_day(current_date, body, cycles, cycle_id=cycle_id)
        if phase is None and matching_cycle is not None:
            phase = _phase_from_cycle(current_date, matching_cycle)
            cycle_id = _clean_symbol(matching_cycle.get("cycle_id"))
        if phase is None:
            phase = "retrograde" if is_retrograde else "direct" if is_retrograde is not None else "unknown"

        station_events = _station_events_for_body(body, cycles)
        previous = [event for event in station_events if event[0].date() <= current_date]
        upcoming = [event for event in station_events if event[0].date() >= current_date]
        nearest = min(
            station_events,
            key=lambda event: abs((event[0].date() - current_date).days),
            default=None,
        )
        days_since = (current_date - previous[-1][0].date()).days if previous else None
        days_until = (upcoming[0][0].date() - current_date).days if upcoming else None
        source_parts: list[str] = []
        uses_computed_station = bool(
            matching_cycle and matching_cycle.get("_computed_station_cycle")
        ) or any(
            str(cycle.get("body")) == body and cycle.get("_computed_station_cycle")
            for cycle in cycles
        )
        if position:
            source_parts.append("computed_swiss_ephemeris")
        if matching_cycle or nearest:
            source_parts.append(
                "computed_station_cycles"
                if uses_computed_station
                else "astro_retrograde_cycles"
            )
        source = "+".join(source_parts) or "unavailable"
        quality = (
            "computed_station_and_position"
            if position and uses_computed_station
            else "canonical_station_computed_position"
            if position and (matching_cycle or nearest)
            else "computed_position_only"
            if position
            else "computed_station_only"
            if uses_computed_station
            else "canonical_station_only"
            if matching_cycle or nearest
            else "missing"
        )
        notes: list[str] = []
        if matching_cycle is None and is_retrograde:
            notes.append(
                "Position speed indicates retrograde motion, but no canonical cycle covers this date."
            )
        return DailyRetrogradeBodyContext(
            body=body,
            phase=phase,
            is_retrograde=is_retrograde,
            lon_speed_deg_day=speed,
            nearest_station_type=nearest[1] if nearest else None,
            nearest_station_ts=nearest[0] if nearest else None,
            days_to_station_nearest=(
                abs((nearest[0].date() - current_date).days) if nearest else None
            ),
            days_since_station=days_since,
            days_until_station=days_until,
            cycle_id=cycle_id,
            source=source,
            data_quality=quality,
            notes=notes,
        )

    def _retrograde_cycles(self) -> list[dict[str, Any]]:
        table_name = "astro_retrograde_cycles"
        if table_name in self._tables:
            cached = self._tables[table_name]
            return cached if isinstance(cached, list) else []
        path = self._retrograde_cycles_path()
        if path is None:
            self._tables[table_name] = []
            return []
        try:
            import pandas as pd

            frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            rows = frame.to_dict("records")
        except Exception:
            rows = []
        self._tables[table_name] = rows
        return rows

    def _retrograde_cycles_path(self) -> Path | None:
        candidates = (
            self.output_root / "parquet/astro_daily_1926_2025/astro_retrograde_cycles.parquet",
            self.output_root / "parquet/astro_daily_1926_2025/astro_retrograde_cycles.csv",
            self.output_root / "parquet/astro_daily/astro_retrograde_cycles.parquet",
            self.output_root / "parquet/astro_daily/astro_retrograde_cycles.csv",
        )
        for path in candidates:
            if path.exists() and path.stat().st_size > 0:
                return path
        return None

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

    def _computed_ephemeris_row(self, current_date: date) -> dict[str, Any] | None:
        """Compute a light-weight daily astro row when snapshots do not cover a date.

        This is intentionally limited to deterministic ephemeris-derived context.
        It never fetches external data and it does not try to synthesize observed
        market, macro, or financial-stress data.
        """
        cache_key = f"computed_astro:{current_date.isoformat()}"
        cached = self._tables.get(cache_key)
        if isinstance(cached, dict):
            return cached
        if cached is False:
            return None
        try:
            row = compute_daily_ephemeris_context(current_date)
        except Exception:
            self._tables[cache_key] = False
            return None
        self._tables[cache_key] = row
        return row

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


def _as_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text or text == "nan":
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _station_events_for_body(
    body: str,
    cycles: list[dict[str, Any]],
) -> list[tuple[datetime, str]]:
    events: dict[tuple[datetime, str], None] = {}
    for cycle in cycles:
        if str(cycle.get("body")) != body:
            continue
        station_in = _as_utc_datetime(cycle.get("station_in_ts"))
        station_out = _as_utc_datetime(cycle.get("station_out_ts"))
        if station_in:
            events[(station_in, "direct_to_retrograde")] = None
        if station_out:
            events[(station_out, "retrograde_to_direct")] = None
    return sorted(events, key=lambda event: event[0])


def _cycle_for_day(
    current_date: date,
    body: str,
    cycles: list[dict[str, Any]],
    *,
    cycle_id: str | None,
) -> dict[str, Any] | None:
    body_cycles = [cycle for cycle in cycles if str(cycle.get("body")) == body]
    if cycle_id:
        exact = next(
            (cycle for cycle in body_cycles if str(cycle.get("cycle_id")) == cycle_id),
            None,
        )
        if exact is not None:
            return exact
    for cycle in body_cycles:
        window_start = _as_utc_datetime(cycle.get("pre_window_start_ts"))
        window_end = _as_utc_datetime(cycle.get("post_window_end_ts"))
        if window_start and window_end and window_start.date() <= current_date <= window_end.date():
            return cycle
    return None


def _phase_from_cycle(current_date: date, cycle: dict[str, Any]) -> str:
    station_in = _as_utc_datetime(cycle.get("station_in_ts"))
    station_out = _as_utc_datetime(cycle.get("station_out_ts"))
    pre_start = _as_utc_datetime(cycle.get("pre_window_start_ts"))
    post_end = _as_utc_datetime(cycle.get("post_window_end_ts"))
    if station_in is None or station_out is None:
        return "unknown"
    station_phase_days = int(_float_value(cycle.get("station_phase_days")) or 7)
    station_in_date = station_in.date()
    station_out_date = station_out.date()
    if station_in_date <= current_date <= station_in_date + timedelta(days=station_phase_days):
        return "retrograde_entry"
    if station_out_date - timedelta(days=station_phase_days) <= current_date <= station_out_date:
        return "retrograde_exit"
    if station_in_date < current_date < station_out_date:
        return "retrograde_core"
    if pre_start and pre_start.date() <= current_date < station_in_date:
        return "pre_station"
    if post_end and station_out_date < current_date <= post_end.date():
        return "post_station"
    return "direct"


def _cycles_with_computed_fallback(
    current_date: date,
    cycles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    supplemented = list(cycles)
    computed: list[dict[str, Any]] | None = None
    for body in RETROGRADE_BODIES:
        events = _station_events_for_body(body, cycles)
        nearest_distance = min(
            (abs((event[0].date() - current_date).days) for event in events),
            default=10_000,
        )
        if nearest_distance <= 400:
            continue
        if computed is None:
            computed = list(_computed_retrograde_cycles(current_date.year))
        supplemented.extend(
            cycle for cycle in computed if str(cycle.get("body")) == body
        )
    return supplemented


@lru_cache(maxsize=12)
def _computed_retrograde_cycles(anchor_year: int) -> tuple[dict[str, Any], ...]:
    import swisseph as swe

    body_ids = {
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO,
    }
    start = datetime(anchor_year - 1, 1, 1, tzinfo=UTC)
    end = datetime(anchor_year + 2, 1, 1, tzinfo=UTC)
    rows: list[dict[str, Any]] = []
    for body in RETROGRADE_BODIES:
        events: list[tuple[datetime, str]] = []
        left = start
        left_speed = _swe_longitude_speed(swe, body_ids[body], left)
        while left < end:
            right = min(left + timedelta(days=1), end)
            right_speed = _swe_longitude_speed(swe, body_ids[body], right)
            if _speed_sign_changed(left_speed, right_speed):
                exact = _refine_swe_station(
                    swe,
                    body_ids[body],
                    left,
                    right,
                    left_speed,
                    tolerance_seconds=60,
                )
                station_type = (
                    "direct_to_retrograde"
                    if left_speed >= 0 and right_speed < 0
                    else "retrograde_to_direct"
                )
                events.append((exact, station_type))
            left = right
            left_speed = right_speed

        pending_in: datetime | None = None
        for exact, station_type in events:
            if station_type == "direct_to_retrograde":
                pending_in = exact
                continue
            if pending_in is None or pending_in >= exact:
                continue
            rows.append(
                {
                    "body": body,
                    "cycle_id": f"{body}_{pending_in:%Y%m%d}_{exact:%Y%m%d}",
                    "station_in_ts": pending_in,
                    "station_out_ts": exact,
                    "pre_window_start_ts": pending_in - timedelta(days=14),
                    "post_window_end_ts": exact + timedelta(days=14),
                    "station_phase_days": 7,
                    "_computed_station_cycle": True,
                }
            )
            pending_in = None
    return tuple(rows)


def _swe_longitude_speed(swe: Any, body_id: int, timestamp: datetime) -> float:
    _jd_et, jd_ut = swe.utc_to_jd(
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second,
        swe.GREG_CAL,
    )
    values, _ = swe.calc_ut(jd_ut, body_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return float(values[3])


def _speed_sign_changed(left: float, right: float) -> bool:
    return left == 0 or right == 0 or (left < 0 < right) or (right < 0 < left)


def _refine_swe_station(
    swe: Any,
    body_id: int,
    left: datetime,
    right: datetime,
    left_speed: float,
    *,
    tolerance_seconds: int,
) -> datetime:
    while (right - left).total_seconds() > tolerance_seconds:
        midpoint = left + (right - left) / 2
        midpoint_speed = _swe_longitude_speed(swe, body_id, midpoint)
        if _speed_sign_changed(left_speed, midpoint_speed):
            right = midpoint
        else:
            left = midpoint
            left_speed = midpoint_speed
    return left + (right - left) / 2


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


def compute_daily_ephemeris_context(current_date: date) -> dict[str, Any]:
    details = compute_daily_ephemeris_details(current_date)
    return {
        "ts": details["sample_time_utc"],
        "active_retrograde_count": len(details["active_retrograde_bodies"]),
        "station_cluster_count_7d": len(details["near_station_bodies"]),
        "major_aspect_cluster_count_7d": len(details["major_aspects"]),
        "moon_phase_name": details["moon_phase"]["name"],
        "_computed_ephemeris": True,
        "_ephemeris_details": details,
    }


def compute_daily_ephemeris_details(current_date: date) -> dict[str, Any]:
    import swisseph as swe

    body_ids = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO,
    }
    ts = datetime(
        current_date.year,
        current_date.month,
        current_date.day,
        tzinfo=UTC,
    )
    _jd_et, jd_ut = swe.utc_to_jd(
        ts.year,
        ts.month,
        ts.day,
        ts.hour,
        ts.minute,
        0,
        swe.GREG_CAL,
    )
    positions: dict[str, dict[str, float | bool]] = {}
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    for body in EPHEMERIS_BODIES:
        body_id = body_ids[body]
        xx, _ = swe.calc_ut(jd_ut, body_id, flags)
        lon = float(xx[0]) % 360
        speed = float(xx[3])
        positions[body] = {
            "lon_deg": round(lon, 4),
            "lon_speed_deg_day": round(speed, 6),
            "is_retrograde": speed < 0,
        }

    sun_lon = float(positions["Sun"]["lon_deg"])
    moon_lon = float(positions["Moon"]["lon_deg"])
    elongation = (moon_lon - sun_lon) % 360
    active_retrograde_bodies = [
        body for body in RETROGRADE_BODIES if bool(positions[body]["is_retrograde"])
    ]
    near_station_bodies = [
        body
        for body in RETROGRADE_BODIES
        if abs(float(positions[body]["lon_speed_deg_day"])) <= _station_speed_threshold(body)
    ]
    return {
        "source": "computed_swiss_ephemeris",
        "sample_time_utc": ts.isoformat().replace("+00:00", "Z"),
        "coordinate_system": "geocentric_tropical_ecliptic",
        "bodies": [
            {
                "body": body,
                "lon_deg": positions[body]["lon_deg"],
                "lon_speed_deg_day": positions[body]["lon_speed_deg_day"],
                "is_retrograde": positions[body]["is_retrograde"],
            }
            for body in EPHEMERIS_BODIES
        ],
        "moon_phase": {
            "name": _computed_moon_phase_name(sun_lon, moon_lon),
            "elongation_deg": round(elongation, 4),
        },
        "active_retrograde_bodies": active_retrograde_bodies,
        "near_station_bodies": near_station_bodies,
        "major_aspects": _computed_major_aspects(positions),
        "notes": [
            "Computed locally with Swiss Ephemeris at UTC midnight.",
            "This is astronomy/ephemeris context only, not observed market data.",
        ],
    }


def _station_speed_threshold(body: str) -> float:
    return {
        "Mercury": 0.18,
        "Venus": 0.08,
        "Mars": 0.06,
        "Jupiter": 0.025,
        "Saturn": 0.018,
        "Uranus": 0.01,
        "Neptune": 0.006,
        "Pluto": 0.006,
    }.get(body, 0.02)


def _computed_major_aspect_count(positions: dict[str, dict[str, float | bool]]) -> int:
    return len(_computed_major_aspects(positions))


def _computed_major_aspects(
    positions: dict[str, dict[str, float | bool]],
) -> list[dict[str, Any]]:
    bodies = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
    aspects: list[dict[str, Any]] = []
    for index, left in enumerate(bodies):
        for right in bodies[index + 1 :]:
            distance = _angular_distance(
                float(positions[left]["lon_deg"]),
                float(positions[right]["lon_deg"]),
            )
            for aspect_name, aspect_deg in MAJOR_ASPECTS.items():
                orb = abs(distance - aspect_deg)
                if orb <= 2.0:
                    aspects.append(
                        {
                            "body_a": left,
                            "body_b": right,
                            "aspect_name": aspect_name,
                            "aspect_deg": aspect_deg,
                            "angle_deg": round(distance, 4),
                            "orb_deg": round(orb, 4),
                        }
                    )
    return sorted(aspects, key=lambda item: (float(item["orb_deg"]), item["body_a"], item["body_b"]))[:12]


def _computed_moon_phase_name(sun_lon: float, moon_lon: float) -> str:
    elongation = (moon_lon - sun_lon) % 360
    if elongation < 45 or elongation >= 315:
        return "NewMoonZone"
    if elongation < 135:
        return "FirstQuarterZone"
    if elongation < 225:
        return "FullMoonZone"
    return "LastQuarterZone"


def _angular_distance(left: float, right: float) -> float:
    diff = abs((left - right) % 360)
    return min(diff, 360 - diff)
