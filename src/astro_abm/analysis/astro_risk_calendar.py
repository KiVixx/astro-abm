from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from astro_abm.analysis.training_dataset import _sql_string_list
from astro_abm.storage.questdb import QuestDBMarketBarWriter


DEFAULT_SIGNAL_SPLIT = "test"
DEFAULT_MIN_LIFT = 1.5
DEFAULT_MIN_SIGNAL_OBSERVATIONS = 100


def load_signal_frame(
    path: Path,
    *,
    split: str = DEFAULT_SIGNAL_SPLIT,
    min_lift: float = DEFAULT_MIN_LIFT,
    min_signal_observations: int = DEFAULT_MIN_SIGNAL_OBSERVATIONS,
    top_signals: int | None = 25,
) -> pd.DataFrame:
    signals = pd.read_csv(path)
    required = {"split", "feature", "tail", "threshold", "lift", "observations_signal"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"signal CSV is missing columns: {', '.join(sorted(missing))}")

    signals["lift"] = pd.to_numeric(signals["lift"], errors="coerce")
    signals["threshold"] = pd.to_numeric(signals["threshold"], errors="coerce")
    signals["observations_signal"] = pd.to_numeric(signals["observations_signal"], errors="coerce")
    filtered = signals[
        (signals["split"].astype(str) == split)
        & (signals["lift"] >= min_lift)
        & (signals["observations_signal"] >= min_signal_observations)
        & (signals["threshold"].notna())
    ].copy()
    filtered = filtered.sort_values(["lift", "event_rate_signal", "observations_signal"], ascending=False)
    if top_signals is not None:
        filtered = filtered.head(top_signals)
    return filtered.reset_index(drop=True)


def build_astro_risk_calendar(
    ephemeris_frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    *,
    frequency: str = "daily",
) -> pd.DataFrame:
    if frequency not in {"hourly", "daily"}:
        raise ValueError("frequency must be hourly or daily.")
    hourly = score_ephemeris_risk(ephemeris_frame, signal_frame)
    if frequency == "hourly" or hourly.empty:
        return hourly
    return _daily_calendar(hourly)


def score_ephemeris_risk(ephemeris_frame: pd.DataFrame, signal_frame: pd.DataFrame) -> pd.DataFrame:
    if ephemeris_frame.empty:
        return pd.DataFrame(columns=["ts", "risk_score", "risk_score_0_100", "active_signal_count", "active_signals"])
    if signal_frame.empty:
        result = ephemeris_frame[["ts"]].copy()
        result["risk_score"] = 0.0
        result["risk_score_0_100"] = 0.0
        result["active_signal_count"] = 0
        result["active_signals"] = ""
        return result

    frame = ephemeris_frame.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    raw_scores = pd.Series(0.0, index=frame.index)
    active_counts = pd.Series(0, index=frame.index)
    active_names: list[list[str]] = [[] for _ in range(len(frame))]

    for signal in signal_frame.to_dict(orient="records"):
        feature = str(signal["feature"])
        if feature not in frame.columns:
            continue
        values = pd.to_numeric(frame[feature], errors="coerce")
        tail = str(signal["tail"])
        threshold = float(signal["threshold"])
        if tail == "high":
            active = values >= threshold
        elif tail == "low":
            active = values <= threshold
        elif tail == "true":
            active = values >= 0.5
        else:
            continue

        lift = float(signal["lift"])
        weight = max(0.0, math.log(lift)) if math.isfinite(lift) and lift > 0 else 0.0
        raw_scores = raw_scores + active.fillna(False).astype(float) * weight
        active_counts = active_counts + active.fillna(False).astype(int)
        label = f"{feature}:{tail}"
        for index in active[active.fillna(False)].index:
            active_names[index].append(label)

    result = pd.DataFrame(
        {
            "ts": frame["ts"],
            "risk_score": raw_scores,
            "active_signal_count": active_counts,
            "active_signals": [", ".join(names[:8]) for names in active_names],
        }
    )
    max_score = float(result["risk_score"].max())
    result["risk_score_0_100"] = (result["risk_score"] / max_score * 100.0) if max_score > 0 else 0.0
    return result[["ts", "risk_score", "risk_score_0_100", "active_signal_count", "active_signals"]]


def load_future_ephemeris_frame(
    *,
    start_utc: datetime,
    end_utc: datetime,
    metrics: Sequence[str],
    connection_factory: Callable | None = None,
) -> pd.DataFrame:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    metric_list = tuple(dict.fromkeys(metrics))
    if not metric_list:
        return pd.DataFrame(columns=["ts"])
    metric_names = _sql_string_list(metric_list)
    sql = f"""
    SELECT ts, metric_name, metric_value
    FROM abm_hourly_facts
    WHERE source = 'pyswisseph'
      AND entity_id = 'GLOBAL'
      AND metric_name IN ({metric_names})
      AND ts >= %s
      AND ts < %s
    ORDER BY ts
    """.strip()
    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (start_utc, end_utc))
            facts = pd.DataFrame(cursor.fetchall(), columns=["ts", "metric_name", "metric_value"])
    return pivot_ephemeris_facts(facts)


def pivot_ephemeris_facts(facts: pd.DataFrame) -> pd.DataFrame:
    if facts.empty:
        return pd.DataFrame(columns=["ts"])
    normalized = facts.copy()
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True).dt.floor("h")
    normalized["metric_value"] = pd.to_numeric(normalized["metric_value"], errors="coerce")
    return (
        normalized.pivot_table(index="ts", columns="metric_name", values="metric_value", aggfunc="last")
        .reset_index()
        .rename_axis(None, axis=1)
        .sort_values("ts")
        .reset_index(drop=True)
    )


def format_astro_risk_calendar_report(calendar: pd.DataFrame, signal_frame: pd.DataFrame, *, top: int = 15) -> str:
    lines = [
        "Astro Risk Calendar Report",
        f"Rows: {len(calendar)}",
        f"Signals used: {len(signal_frame)}",
    ]
    if not calendar.empty:
        lines.append(f"Range: {_format_ts(calendar['ts'].min())} -> {_format_ts(calendar['ts'].max())}")
        lines.append("Top risk windows:")
        top_rows = calendar.sort_values(["risk_score_0_100", "active_signal_count"], ascending=False).head(top)
        for row in top_rows.to_dict(orient="records"):
            lines.append(
                "  - "
                f"{_format_ts(row['ts'])}: "
                f"risk={row['risk_score_0_100']:.1f} "
                f"active={int(row['active_signal_count'])} "
                f"signals={row['active_signals'] or '-'}"
            )
    return "\n".join(lines)


def export_calendar(calendar: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    calendar.to_csv(output_path, index=False)
    return output_path


def _daily_calendar(hourly: pd.DataFrame) -> pd.DataFrame:
    daily = hourly.copy()
    daily["date"] = pd.to_datetime(daily["ts"], utc=True).dt.floor("D")
    idx = daily.groupby("date")["risk_score_0_100"].idxmax()
    selected = daily.loc[idx].copy().sort_values("date")
    selected["ts"] = selected["date"]
    selected = selected.drop(columns=["date"])
    return selected.reset_index(drop=True)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _default_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(minute=0, second=0, microsecond=0)


def _format_ts(value) -> str:
    if value is None:
        return "-"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")


def main(argv: Sequence[str] | None = None) -> int:
    default_start = _default_start()
    parser = argparse.ArgumentParser(description="Build a future astro volatility risk calendar from alpha-scan signal rows.")
    parser.add_argument("--signals", required=True, help="CSV produced by astro-abm-astro-volatility-alpha --output.")
    parser.add_argument("--start", default=default_start.isoformat(), help="UTC start timestamp.")
    parser.add_argument("--end", default=(default_start + timedelta(days=365)).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--split", default=DEFAULT_SIGNAL_SPLIT, help="Signal split to use, usually test.")
    parser.add_argument("--min-lift", type=float, default=DEFAULT_MIN_LIFT, help="Minimum signal lift to include.")
    parser.add_argument("--min-signal-observations", type=int, default=DEFAULT_MIN_SIGNAL_OBSERVATIONS)
    parser.add_argument("--top-signals", type=int, default=25, help="Maximum number of historical signal rules to apply.")
    parser.add_argument("--frequency", choices=("hourly", "daily"), default="daily", help="Output calendar frequency.")
    parser.add_argument("--top", type=int, default=15, help="Number of top risk windows to print.")
    parser.add_argument("--output", default=None, help="Optional CSV output path.")
    args = parser.parse_args(argv)

    signals = load_signal_frame(
        Path(args.signals),
        split=args.split,
        min_lift=args.min_lift,
        min_signal_observations=args.min_signal_observations,
        top_signals=args.top_signals,
    )
    ephemeris = load_future_ephemeris_frame(
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        metrics=tuple(signals["feature"].dropna().astype(str).unique()),
    )
    calendar = build_astro_risk_calendar(ephemeris, signals, frequency=args.frequency)
    print(format_astro_risk_calendar_report(calendar, signals, top=args.top))
    if args.output:
        export_calendar(calendar, Path(args.output))
        print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
