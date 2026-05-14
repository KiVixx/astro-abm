from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

import pandas as pd

from astro_abm.analysis.training_dataset import load_training_dataset
from astro_abm.features.ephemeris import EPHEMERIS_FEATURE_METRICS
from astro_abm.market_data.binance_historical import normalize_symbols


DEFAULT_TARGET = "future_abs_return_24h"
DEFAULT_EVENT_MODE = "rolling_quantile"
DEFAULT_EVENT_WINDOW_HOURS = 24 * 365
DEFAULT_EVENT_MIN_PERIODS = 24 * 90


@dataclass(frozen=True)
class AstroVolatilityAlphaReport:
    rows: int
    symbols: tuple[str, ...]
    min_ts: datetime | None
    max_ts: datetime | None
    target: str
    event_mode: str
    event_quantile: float
    event_window_hours: int
    event_min_periods: int
    feature_quantile: float
    thresholds: tuple[tuple[str, float], ...]
    results: tuple[dict, ...]


def build_astro_volatility_alpha_report(
    frame: pd.DataFrame,
    *,
    target: str = DEFAULT_TARGET,
    event_mode: str = DEFAULT_EVENT_MODE,
    event_quantile: float = 0.9,
    event_window_hours: int = DEFAULT_EVENT_WINDOW_HOURS,
    event_min_periods: int = DEFAULT_EVENT_MIN_PERIODS,
    feature_quantile: float = 0.9,
    min_observations: int = 100,
) -> AstroVolatilityAlphaReport:
    if event_mode not in {"fixed_train_quantile", "rolling_quantile"}:
        raise ValueError("event_mode must be fixed_train_quantile or rolling_quantile.")
    if not 0.0 < event_quantile < 1.0:
        raise ValueError("event_quantile must be between 0 and 1.")
    if event_window_hours <= 0:
        raise ValueError("event_window_hours must be greater than 0.")
    if event_min_periods <= 0:
        raise ValueError("event_min_periods must be greater than 0.")
    if not 0.5 <= feature_quantile < 1.0:
        raise ValueError("feature_quantile must be between 0.5 and 1.")
    if target not in frame.columns:
        raise ValueError(f"target metric is missing from frame: {target}")

    data = _normalize_frame(frame, target=target)
    if data.empty:
        return AstroVolatilityAlphaReport(
            rows=0,
            symbols=(),
            min_ts=None,
            max_ts=None,
            target=target,
            event_mode=event_mode,
            event_quantile=event_quantile,
            event_window_hours=event_window_hours,
            event_min_periods=event_min_periods,
            feature_quantile=feature_quantile,
            thresholds=(),
            results=(),
        )

    if event_mode == "fixed_train_quantile":
        train = data[data["split"] == "train"]
        threshold_source = train if not train.empty else data
        thresholds = _target_thresholds(threshold_source, target=target, quantile=event_quantile)
        data["event_threshold"] = data["symbol"].map(thresholds)
        if "GLOBAL" in thresholds:
            data["event_threshold"] = data["event_threshold"].fillna(thresholds["GLOBAL"])
    else:
        data["event_threshold"] = _rolling_event_thresholds(
            data,
            target=target,
            quantile=event_quantile,
            window_hours=event_window_hours,
            min_periods=event_min_periods,
        )
        thresholds = _latest_thresholds(data)

    data = data[data["event_threshold"].notna()].copy()
    data["large_vol_event"] = data[target] >= data["event_threshold"]
    if data.empty:
        return AstroVolatilityAlphaReport(
            rows=0,
            symbols=(),
            min_ts=None,
            max_ts=None,
            target=target,
            event_mode=event_mode,
            event_quantile=event_quantile,
            event_window_hours=event_window_hours,
            event_min_periods=event_min_periods,
            feature_quantile=feature_quantile,
            thresholds=tuple(sorted(thresholds.items())),
            results=(),
        )

    rows: list[dict] = []
    for feature in EPHEMERIS_FEATURE_METRICS:
        if feature not in data.columns:
            continue
        feature_values = pd.to_numeric(data[feature], errors="coerce")
        if feature_values.notna().sum() < min_observations:
            continue
        rows.extend(
            _score_feature(
                data,
                feature=feature,
                target=target,
                feature_values=feature_values,
                feature_quantile=feature_quantile,
                min_observations=min_observations,
            )
        )

    ordered = sorted(
        rows,
        key=lambda row: (
            _split_rank(row["split"]),
            row["lift"] if pd.notna(row["lift"]) else -1.0,
            row["event_rate_signal"],
            row["observations_signal"],
        ),
        reverse=True,
    )
    return AstroVolatilityAlphaReport(
        rows=int(len(data)),
        symbols=tuple(sorted(str(symbol) for symbol in data["symbol"].dropna().unique())),
        min_ts=pd.to_datetime(data["ts"], utc=True).min().to_pydatetime(),
        max_ts=pd.to_datetime(data["ts"], utc=True).max().to_pydatetime(),
        target=target,
        event_mode=event_mode,
        event_quantile=event_quantile,
        event_window_hours=event_window_hours,
        event_min_periods=event_min_periods,
        feature_quantile=feature_quantile,
        thresholds=tuple(sorted(thresholds.items())),
        results=tuple(ordered),
    )


def format_astro_volatility_alpha_report(report: AstroVolatilityAlphaReport, *, top: int = 20) -> str:
    lines = [
        "Astro Volatility Alpha Report",
        f"Rows: {report.rows}",
        f"Symbols: {', '.join(report.symbols) if report.symbols else '-'}",
        f"Range: {_format_ts(report.min_ts)} -> {_format_ts(report.max_ts)}",
        f"Target: {report.target}",
        f"Large-vol event: {report.event_mode} q{report.event_quantile:.2f}",
        f"Feature tails: q{report.feature_quantile:.2f} high / q{1 - report.feature_quantile:.2f} low",
    ]
    if report.event_mode == "rolling_quantile":
        lines.append(
            f"Rolling event window: {report.event_window_hours}h "
            f"min_periods={report.event_min_periods}"
        )
    if report.thresholds:
        threshold_label = "Latest event thresholds:" if report.event_mode == "rolling_quantile" else "Event thresholds:"
        lines.append(threshold_label)
        lines.extend(f"  - {symbol}: {threshold:.6f}" for symbol, threshold in report.thresholds)
    if not report.results:
        lines.append("No astro feature signals met the observation threshold.")
        return "\n".join(lines)

    lines.append("Top astro volatility signals:")
    for row in report.results[:top]:
        lines.append(
            "  - "
            f"{row['split']}/{row['feature']}:{row['tail']} "
            f"lift={row['lift']:.3f} "
            f"event_rate={row['event_rate_signal']:.3f} "
            f"base={row['event_rate_base']:.3f} "
            f"coverage={row['coverage']:.3f} "
            f"n={row['observations_signal']} "
            f"spearman={row['spearman']:.3f}"
        )
    return "\n".join(lines)


def export_signal_results(report: AstroVolatilityAlphaReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report.results).to_csv(output_path, index=False)
    return output_path


def _normalize_frame(frame: pd.DataFrame, *, target: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    data = frame.copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data["symbol"] = data["symbol"].astype(str).str.upper()
    data[target] = pd.to_numeric(data[target], errors="coerce")
    if "split" not in data.columns:
        data["split"] = "all"
    data = data[data[target].notna()].sort_values(["symbol", "ts"]).reset_index(drop=True)
    return data


def _target_thresholds(frame: pd.DataFrame, *, target: str, quantile: float) -> dict[str, float]:
    thresholds = (
        frame.groupby("symbol")[target]
        .quantile(quantile)
        .dropna()
        .astype(float)
        .to_dict()
    )
    if not thresholds and frame[target].notna().any():
        thresholds["GLOBAL"] = float(frame[target].quantile(quantile))
    return thresholds


def _rolling_event_thresholds(
    frame: pd.DataFrame,
    *,
    target: str,
    quantile: float,
    window_hours: int,
    min_periods: int,
) -> pd.Series:
    return frame.groupby("symbol", group_keys=False)[target].transform(
        lambda series: series.shift(1).rolling(window_hours, min_periods=min_periods).quantile(quantile)
    )


def _latest_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for symbol, group in frame.groupby("symbol"):
        values = group["event_threshold"].dropna()
        if not values.empty:
            thresholds[str(symbol)] = float(values.iloc[-1])
    return thresholds


def _score_feature(
    frame: pd.DataFrame,
    *,
    feature: str,
    target: str,
    feature_values: pd.Series,
    feature_quantile: float,
    min_observations: int,
) -> list[dict]:
    train = frame[frame["split"] == "train"]
    train_values = pd.to_numeric(train[feature], errors="coerce") if not train.empty else feature_values
    unique_values = train_values.dropna().unique()
    if len(unique_values) <= 1:
        return []

    if set(pd.Series(unique_values).dropna().astype(float).unique()).issubset({0.0, 1.0}):
        tails = [("true", 0.5, lambda values: values >= 0.5)]
    else:
        high_threshold = float(train_values.quantile(feature_quantile))
        low_threshold = float(train_values.quantile(1 - feature_quantile))
        tails = [
            ("high", high_threshold, lambda values, threshold=high_threshold: values >= threshold),
            ("low", low_threshold, lambda values, threshold=low_threshold: values <= threshold),
        ]

    rows = []
    for tail, threshold, selector in tails:
        signal = selector(feature_values)
        for split in _split_order(frame):
            split_mask = frame["split"] == split
            valid = split_mask & feature_values.notna()
            if int(valid.sum()) < min_observations:
                continue
            signal_mask = valid & signal
            observations_signal = int(signal_mask.sum())
            if observations_signal < min_observations:
                continue
            event_base = frame.loc[valid, "large_vol_event"].astype(float)
            event_signal = frame.loc[signal_mask, "large_vol_event"].astype(float)
            event_rate_base = float(event_base.mean())
            event_rate_signal = float(event_signal.mean())
            lift = event_rate_signal / event_rate_base if event_rate_base > 0 else float("nan")
            target_base = float(frame.loc[valid, target].mean())
            target_signal = float(frame.loc[signal_mask, target].mean())
            rows.append(
                {
                    "split": split,
                    "feature": feature,
                    "tail": tail,
                    "threshold": threshold,
                    "observations": int(valid.sum()),
                    "observations_signal": observations_signal,
                    "coverage": observations_signal / int(valid.sum()),
                    "event_rate_base": event_rate_base,
                    "event_rate_signal": event_rate_signal,
                    "lift": lift,
                    "target_mean_base": target_base,
                    "target_mean_signal": target_signal,
                    "target_mean_lift": target_signal / target_base if target_base > 0 else float("nan"),
                    "spearman": _spearman(feature_values[valid], frame.loc[valid, target]),
                }
            )
    return rows


def _split_order(frame: pd.DataFrame) -> tuple[str, ...]:
    preferred = ["train", "validation", "test", "all"]
    present = [split for split in preferred if split in set(frame["split"])]
    extras = sorted(set(frame["split"]) - set(preferred))
    return tuple(present + extras)


def _split_rank(split: str) -> int:
    return {"test": 4, "validation": 3, "all": 2, "train": 1}.get(split, 0)


def _spearman(left: pd.Series, right: pd.Series) -> float:
    data = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(data) < 3:
        return float("nan")
    return float(data["left"].rank().corr(data["right"].rank()))


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _format_ts(value) -> str:
    if value is None:
        return "-"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score future-computable astro features against large future volatility events.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated Binance symbols.")
    parser.add_argument("--start", default="2020-09-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--validation-start", default="2024-01-01T00:00:00Z", help="UTC validation split start.")
    parser.add_argument("--test-start", default="2025-01-01T00:00:00Z", help="UTC test split start.")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="Future volatility target column.")
    parser.add_argument(
        "--event-mode",
        choices=("rolling_quantile", "fixed_train_quantile"),
        default=DEFAULT_EVENT_MODE,
        help="How to define large-vol events.",
    )
    parser.add_argument("--event-quantile", type=float, default=0.9, help="Quantile used as large-vol event threshold.")
    parser.add_argument("--event-window-hours", type=int, default=DEFAULT_EVENT_WINDOW_HOURS, help="Rolling window for event threshold.")
    parser.add_argument("--event-min-periods", type=int, default=DEFAULT_EVENT_MIN_PERIODS, help="Minimum observations for rolling threshold.")
    parser.add_argument("--feature-quantile", type=float, default=0.9, help="Astro feature tail quantile to test.")
    parser.add_argument("--min-observations", type=int, default=100, help="Minimum signal observations per split.")
    parser.add_argument("--top", type=int, default=20, help="Number of rows to print.")
    parser.add_argument("--output", default=None, help="Optional CSV output path for all signal rows.")
    args = parser.parse_args(argv)

    frame = load_training_dataset(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        validation_start=_parse_utc(args.validation_start) if args.validation_start else None,
        test_start=_parse_utc(args.test_start) if args.test_start else None,
        target=args.target,
        drop_missing_target=True,
    )
    report = build_astro_volatility_alpha_report(
        frame,
        target=args.target,
        event_mode=args.event_mode,
        event_quantile=args.event_quantile,
        event_window_hours=args.event_window_hours,
        event_min_periods=args.event_min_periods,
        feature_quantile=args.feature_quantile,
        min_observations=args.min_observations,
    )
    print(format_astro_volatility_alpha_report(report, top=args.top))
    if args.output:
        export_signal_results(report, Path(args.output))
        print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
