from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from astro_abm.features.ephemeris import EPHEMERIS_FEATURE_METRICS
from astro_abm.features.price_action import PRICE_ACTION_METRICS
from astro_abm.features.regime import REGIME_FEATURE_METRICS, REGIME_LABEL_METRICS
from astro_abm.market_data.binance_historical import normalize_symbols
from astro_abm.storage.questdb import QuestDBMarketBarWriter


DEFAULT_FEATURE_METRICS = tuple(PRICE_ACTION_METRICS) + tuple(REGIME_FEATURE_METRICS) + tuple(EPHEMERIS_FEATURE_METRICS)
DEFAULT_LABEL_METRICS = tuple(REGIME_LABEL_METRICS)
DEFAULT_TARGET = "future_return_24h"


def load_training_dataset(
    *,
    symbols: Sequence[str],
    start_utc: datetime,
    end_utc: datetime,
    validation_start: datetime | None = None,
    test_start: datetime | None = None,
    target: str = DEFAULT_TARGET,
    drop_missing_target: bool = True,
    connection_factory: Callable | None = None,
) -> pd.DataFrame:
    if end_utc <= start_utc:
        raise ValueError("end_utc must be after start_utc.")
    symbol_list = normalize_symbols(symbols)
    if not symbol_list:
        raise ValueError("symbols must contain at least one symbol.")

    connection_factory = connection_factory or QuestDBMarketBarWriter._build_default_connection
    price_frames = []
    fact_frames = []
    for symbol in symbol_list:
        price_frames.append(_load_price_frame(connection_factory, symbol=symbol, start_utc=start_utc, end_utc=end_utc))
        fact_frames.append(_load_fact_frame(connection_factory, symbol=symbol, start_utc=start_utc, end_utc=end_utc))

    price = pd.concat(price_frames, ignore_index=True) if price_frames else _empty_price_frame()
    facts = pd.concat(fact_frames, ignore_index=True) if fact_frames else _empty_fact_frame()
    return build_training_dataset(
        price,
        facts,
        validation_start=validation_start,
        test_start=test_start,
        target=target,
        drop_missing_target=drop_missing_target,
    )


def build_training_dataset(
    price_frame: pd.DataFrame,
    fact_frame: pd.DataFrame,
    *,
    validation_start: datetime | None = None,
    test_start: datetime | None = None,
    target: str = DEFAULT_TARGET,
    drop_missing_target: bool = True,
) -> pd.DataFrame:
    if price_frame.empty:
        return price_frame.copy()

    price = _normalize_price_frame(price_frame)
    facts = _normalize_fact_frame(fact_frame)
    facts = _expand_global_facts(facts, symbols=tuple(sorted(price["symbol"].dropna().unique())))
    if facts.empty:
        wide_facts = pd.DataFrame(columns=["ts", "symbol"])
    else:
        wide_facts = (
            facts.pivot_table(
                index=["ts", "symbol"],
                columns="metric_name",
                values="metric_value",
                aggfunc="last",
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )

    dataset = price.merge(wide_facts, on=["ts", "symbol"], how="left").sort_values(["symbol", "ts"]).reset_index(drop=True)
    if validation_start is not None or test_start is not None:
        dataset = assign_time_splits(dataset, validation_start=validation_start, test_start=test_start)

    if drop_missing_target:
        if target not in dataset.columns:
            raise ValueError(f"target metric is missing from dataset: {target}")
        dataset = dataset[dataset[target].notna()].reset_index(drop=True)
    return dataset


def assign_time_splits(
    frame: pd.DataFrame,
    *,
    validation_start: datetime | None,
    test_start: datetime | None,
) -> pd.DataFrame:
    if validation_start is None and test_start is None:
        return frame.copy()
    if validation_start is not None and test_start is not None and test_start <= validation_start:
        raise ValueError("test_start must be after validation_start.")

    result = frame.copy()
    ts = pd.to_datetime(result["ts"], utc=True)
    result["split"] = "train"
    if validation_start is not None:
        result.loc[ts >= pd.Timestamp(validation_start), "split"] = "validation"
    if test_start is not None:
        result.loc[ts >= pd.Timestamp(test_start), "split"] = "test"
    return result


def summarize_training_dataset(frame: pd.DataFrame, *, target: str = DEFAULT_TARGET) -> dict:
    if frame.empty:
        return {
            "rows": 0,
            "symbols": (),
            "min_ts": None,
            "max_ts": None,
            "feature_count": 0,
            "label_count": 0,
            "target": target,
            "target_non_null": 0,
            "split_counts": (),
        }
    feature_columns = [column for column in DEFAULT_FEATURE_METRICS if column in frame.columns]
    label_columns = [column for column in DEFAULT_LABEL_METRICS if column in frame.columns]
    split_counts = ()
    if "split" in frame.columns:
        split_counts = tuple((str(split), int(count)) for split, count in frame["split"].value_counts(sort=False).items())
    return {
        "rows": int(len(frame)),
        "symbols": tuple(sorted(str(symbol) for symbol in frame["symbol"].dropna().unique())),
        "min_ts": pd.to_datetime(frame["ts"], utc=True).min().to_pydatetime(),
        "max_ts": pd.to_datetime(frame["ts"], utc=True).max().to_pydatetime(),
        "feature_count": len(feature_columns),
        "label_count": len(label_columns),
        "target": target,
        "target_non_null": int(frame[target].notna().sum()) if target in frame.columns else 0,
        "split_counts": split_counts,
    }


def compute_direction_baselines(frame: pd.DataFrame, *, target: str = DEFAULT_TARGET) -> tuple[dict, ...]:
    if frame.empty or target not in frame.columns:
        return ()

    scored = frame[frame[target].notna()].copy()
    if scored.empty:
        return ()
    if "split" not in scored.columns:
        scored["split"] = "all"

    train = scored[scored["split"] == "train"]
    train_target = train[target] if not train.empty else scored[target]
    majority_up = bool((train_target > 0).mean() >= 0.5)
    rules = [("majority_direction", pd.Series(majority_up, index=scored.index), pd.Series(True, index=scored.index))]

    for column, name in (
        ("price_return_1h", "momentum_1h"),
        ("regime_return_24h", "momentum_24h"),
        ("regime_funding_rate", "funding_positive"),
    ):
        if column in scored.columns:
            values = pd.to_numeric(scored[column], errors="coerce")
            rules.append((name, values > 0, values.notna()))

    rows: list[dict] = []
    actual_up = scored[target] > 0
    for split in scored["split"].drop_duplicates():
        split_mask = scored["split"] == split
        for name, predictions, valid_source in rules:
            valid = split_mask & valid_source
            observations = int(valid.sum())
            if observations == 0:
                continue
            accuracy = float((predictions[valid] == actual_up[valid]).mean())
            rows.append({"split": str(split), "rule": name, "observations": observations, "direction_accuracy": accuracy})
    return tuple(rows)


def format_training_dataset_report(summary: dict, baselines: Sequence[dict]) -> str:
    lines = [
        "Training Dataset Report",
        f"Rows: {summary['rows']}",
        f"Symbols: {', '.join(summary['symbols']) if summary['symbols'] else '-'}",
        f"Range: {_format_ts(summary['min_ts'])} -> {_format_ts(summary['max_ts'])}",
        f"Feature columns: {summary['feature_count']}",
        f"Label columns: {summary['label_count']}",
        f"Target: {summary['target']} non_null={summary['target_non_null']}",
    ]
    if summary.get("split_counts"):
        lines.append("Splits:")
        lines.extend(f"  - {split}: {count}" for split, count in summary["split_counts"])
    if baselines:
        lines.append("Direction Baselines:")
        lines.extend(
            f"  - {row['split']}/{row['rule']}: accuracy={row['direction_accuracy']:.4f} n={row['observations']}"
            for row in baselines
        )
    return "\n".join(lines)


def export_training_dataset(frame: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def _load_price_frame(connection_factory: Callable, *, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    sql = """
    SELECT
        ts, symbol, open, high, low, close, volume, quote_volume, trade_count,
        data_quality, is_proxy_data, is_imputed, volume_scale_ratio
    FROM v_market_ohlcv_ml_1h
    WHERE symbol = %s
      AND ts >= %s
      AND ts < %s
    ORDER BY ts
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, start_utc, end_utc))
            return pd.DataFrame(cursor.fetchall(), columns=_empty_price_frame().columns)


def _load_fact_frame(connection_factory: Callable, *, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    metric_names = _sql_string_list(tuple(DEFAULT_FEATURE_METRICS) + tuple(DEFAULT_LABEL_METRICS))
    sql = f"""
    SELECT ts, %s AS symbol, metric_name, metric_value
    FROM abm_hourly_facts
    WHERE (entity_id = %s OR entity_id = 'GLOBAL')
      AND source IN ('price_action', 'regime_features', 'regime_labels', 'pyswisseph')
      AND metric_name IN ({metric_names})
      AND ts >= %s
      AND ts < %s
    ORDER BY ts
    """.strip()
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (symbol, symbol, start_utc, end_utc))
            return pd.DataFrame(cursor.fetchall(), columns=_empty_fact_frame().columns)


def _normalize_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    price = frame.copy()
    price["ts"] = pd.to_datetime(price["ts"], utc=True).dt.floor("h")
    price["symbol"] = price["symbol"].astype(str).str.upper()
    price = price.drop_duplicates(subset=["ts", "symbol"], keep="last")
    return price


def _normalize_fact_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return _empty_fact_frame()
    facts = frame.copy()
    facts["ts"] = pd.to_datetime(facts["ts"], utc=True).dt.floor("h")
    facts["symbol"] = facts["symbol"].astype(str).str.upper()
    facts["metric_value"] = pd.to_numeric(facts["metric_value"], errors="coerce")
    return facts.drop_duplicates(subset=["ts", "symbol", "metric_name"], keep="last")


def _expand_global_facts(frame: pd.DataFrame, *, symbols: Sequence[str]) -> pd.DataFrame:
    if frame.empty or "GLOBAL" not in set(frame["symbol"]):
        return frame
    specific = frame[frame["symbol"] != "GLOBAL"]
    global_rows = frame[frame["symbol"] == "GLOBAL"].drop(columns=["symbol"])
    expanded = []
    for symbol in symbols:
        copy = global_rows.copy()
        copy["symbol"] = symbol
        expanded.append(copy)
    if not expanded:
        return specific
    return pd.concat([specific, *expanded], ignore_index=True)


def _empty_price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ts",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
            "data_quality",
            "is_proxy_data",
            "is_imputed",
            "volume_scale_ratio",
        ]
    )


def _empty_fact_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["ts", "symbol", "metric_name", "metric_value"])


def _sql_string_list(values: Sequence[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _format_ts(value) -> str:
    if value is None:
        return "-"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a 1h ML training dataset with price, regime features, and labels.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Comma-separated Binance symbols.")
    parser.add_argument("--start", default="2020-09-01T00:00:00Z", help="UTC start timestamp.")
    parser.add_argument("--end", default=datetime.now(UTC).isoformat(), help="UTC end timestamp.")
    parser.add_argument("--validation-start", default="2024-01-01T00:00:00Z", help="UTC validation split start.")
    parser.add_argument("--test-start", default="2025-01-01T00:00:00Z", help="UTC test split start.")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="Label column used for filtering and baseline scoring.")
    parser.add_argument("--keep-unlabeled", action="store_true", help="Keep rows with missing target label.")
    parser.add_argument("--output", default=None, help="Optional CSV output path.")
    args = parser.parse_args(argv)

    frame = load_training_dataset(
        symbols=normalize_symbols(args.symbols.split(",")),
        start_utc=_parse_utc(args.start),
        end_utc=_parse_utc(args.end),
        validation_start=_parse_utc(args.validation_start) if args.validation_start else None,
        test_start=_parse_utc(args.test_start) if args.test_start else None,
        target=args.target,
        drop_missing_target=not args.keep_unlabeled,
    )
    if args.output:
        export_training_dataset(frame, Path(args.output))

    summary = summarize_training_dataset(frame, target=args.target)
    baselines = compute_direction_baselines(frame, target=args.target)
    print(format_training_dataset_report(summary, baselines))
    if args.output:
        print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
