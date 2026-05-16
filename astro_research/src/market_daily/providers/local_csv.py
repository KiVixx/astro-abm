from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from market_daily.config import AssetConfig
from market_daily.normalize import BAR_COLUMNS
from market_daily.normalize import normalize_market_bars
from market_daily.providers.base import MarketDailyProvider


class LocalCSVProvider(MarketDailyProvider):
    source = "local_csv"

    def __init__(self, *, root: str | Path | None = None):
        self.root = Path(root) if root else Path.cwd()
        self.warnings: list[str] = []

    def fetch_daily_bars(self, *, asset: AssetConfig, start: date, end: date) -> pd.DataFrame:
        if not asset.path:
            return self._empty_bars(f"{asset.asset}: local_csv path missing")
        path = self._resolve(asset.path)
        if not path.exists():
            return self._empty_bars(f"{asset.asset}: local_csv missing file: {path}")
        raw = pd.read_csv(path)
        validation = validate_price_schema(raw)
        warnings = [f"{asset.asset}: {warning}" for warning in validation]
        if any(warning.startswith("missing required") for warning in validation):
            return self._empty_bars(*warnings)
        duplicate_count = _duplicate_date_count(raw)
        if duplicate_count:
            warnings.append(f"{asset.asset}: duplicate date rows={duplicate_count}")
        frame = normalize_market_bars(
            raw,
            asset=asset.asset,
            source=self.source,
            currency=asset.currency,
            market_timezone=asset.timezone,
            data_version="",
            source_note=f"local_csv:{path}",
        )
        if duplicate_count:
            frame = frame.drop_duplicates(["ts", "asset", "source"], keep="last")
        mask = (frame["ts"].dt.date >= start) & (frame["ts"].dt.date <= end)
        output = frame.loc[mask].reset_index(drop=True)
        if len(output) < 30:
            warnings.append(f"{asset.asset}: insufficient local_csv coverage rows={len(output)}")
        output.attrs["warnings"] = warnings
        self.warnings.extend(warnings)
        return output

    def fetch_indicator_observations(
        self,
        *,
        series_id: str,
        path: str,
        start: date,
        end: date,
        source: str = "local_csv",
        source_note_prefix: str = "local_csv",
    ) -> pd.DataFrame:
        target = self._resolve(path)
        if not target.exists():
            return self._empty_indicator(f"{series_id}: local_csv missing file: {target}")
        raw = pd.read_csv(target)
        validation = validate_indicator_schema(raw)
        warnings = [f"{series_id}: {warning}" for warning in validation]
        if any(warning.startswith("missing required") for warning in validation):
            return self._empty_indicator(*warnings)
        duplicate_count = _duplicate_date_count(raw)
        if duplicate_count:
            warnings.append(f"{series_id}: duplicate date rows={duplicate_count}")
        working = raw.copy()
        working.columns = [str(column).lower().strip() for column in working.columns]
        if "date" in working.columns and "ts" not in working.columns:
            working = working.rename(columns={"date": "ts"})
        working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
        working["value"] = pd.to_numeric(working["value"], errors="coerce")
        working = working.dropna(subset=["value"]).drop_duplicates(["ts"], keep="last")
        mask = (working["ts"].dt.date >= start) & (working["ts"].dt.date <= end)
        output = working.loc[mask, ["ts", "value"]].copy()
        output["series_id"] = series_id
        output["source"] = source
        output["source_note"] = f"{source_note_prefix}:{target}"
        if len(output) < 30:
            warnings.append(f"{series_id}: insufficient local_csv coverage rows={len(output)}")
        output.attrs["warnings"] = warnings
        self.warnings.extend(warnings)
        return output[["ts", "series_id", "source", "value", "source_note"]].reset_index(drop=True)

    def _resolve(self, path: str) -> Path:
        target = Path(path)
        return target if target.is_absolute() else self.root / target

    def _empty_bars(self, *warnings: str) -> pd.DataFrame:
        self.warnings.extend(warnings)
        frame = pd.DataFrame(columns=BAR_COLUMNS)
        frame.attrs["warnings"] = list(warnings)
        return frame

    def _empty_indicator(self, *warnings: str) -> pd.DataFrame:
        self.warnings.extend(warnings)
        frame = pd.DataFrame(columns=["ts", "series_id", "source", "value", "source_note"])
        frame.attrs["warnings"] = list(warnings)
        return frame


def validate_price_schema(frame: pd.DataFrame) -> list[str]:
    columns = {str(column).lower().strip() for column in frame.columns}
    warnings = []
    if "ts" not in columns and "date" not in columns:
        warnings.append("missing required date/ts column")
    if "close" not in columns and "adj_close" not in columns:
        warnings.append("missing required close/adj_close column")
    return warnings


def validate_indicator_schema(frame: pd.DataFrame) -> list[str]:
    columns = {str(column).lower().strip() for column in frame.columns}
    warnings = []
    if "ts" not in columns and "date" not in columns:
        warnings.append("missing required date/ts column")
    if "value" not in columns:
        warnings.append("missing required value column")
    return warnings


def _duplicate_date_count(frame: pd.DataFrame) -> int:
    working = frame.copy()
    working.columns = [str(column).lower().strip() for column in working.columns]
    date_column = "ts" if "ts" in working.columns else "date" if "date" in working.columns else None
    if date_column is None:
        return 0
    dates = pd.to_datetime(working[date_column], errors="coerce").dt.normalize()
    return int(dates.duplicated().sum())
