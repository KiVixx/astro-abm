from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from dotenv import load_dotenv

from market_daily.providers.fred import FREDProvider


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
LBMA_GOLD_PM_URL = "https://prices.lbma.org.uk/json/gold_pm.json"
LBMA_GOLD_AM_URL = "https://prices.lbma.org.uk/json/gold_am.json"

ASSET_OUTPUTS = {
    "SPX": Path("astro_research/data/local/equity/spx_daily.csv"),
    "DXY": Path("astro_research/data/local/fx/dxy_daily.csv"),
    "Gold": Path("astro_research/data/local/commodities/gold_daily.csv"),
    "CreditProxy": Path("astro_research/data/local/credit/hy_oas_daily.csv"),
}

TRACKED_PROVENANCE_PATH = Path("astro_research/data/local/LOCAL_DATA_PROVENANCE.json")
LOCAL_PROVENANCE_PATH = Path("astro_research/data/local/LOCAL_DATA_PROVENANCE.local.json")

YAHOO_SYMBOLS = {
    "SPX": "^GSPC",
    "DXY": "DX-Y.NYB",
}


@dataclass(frozen=True)
class LocalDataFetchResult:
    asset: str
    output_path: Path
    rows: int
    coverage_start: str | None
    coverage_end: str | None
    source: str
    warning: str = ""


def fetch_local_research_data(
    *,
    root: str | Path,
    assets: tuple[str, ...],
    start: date,
    end: date,
    fred_api_key_env: str = "FRED_API_KEY",
    provenance_mode: str = "local",
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> tuple[LocalDataFetchResult, ...]:
    root_path = Path(root)
    if provenance_mode not in {"local", "tracked", "none"}:
        raise ValueError(f"Unsupported provenance mode: {provenance_mode}")
    session = session or requests.Session()
    results: list[LocalDataFetchResult] = []
    for asset in assets:
        if asset not in ASSET_OUTPUTS:
            raise ValueError(f"Unsupported local research asset: {asset}")
        output_path = root_path / ASSET_OUTPUTS[asset]
        if dry_run:
            results.append(
                LocalDataFetchResult(
                    asset=asset,
                    output_path=output_path,
                    rows=0,
                    coverage_start=None,
                    coverage_end=None,
                    source=_source_name(asset),
                    warning="dry-run; file not written",
                )
            )
            continue

        if asset in YAHOO_SYMBOLS:
            frame = fetch_yahoo_chart(YAHOO_SYMBOLS[asset], start=start, end=end, session=session)
        elif asset == "Gold":
            frame = fetch_lbma_gold(start=start, end=end, session=session)
        elif asset == "CreditProxy":
            frame = fetch_credit_proxy(start=start, end=end, fred_api_key_env=fred_api_key_env)
        else:
            raise ValueError(f"Unsupported local research asset: {asset}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
        results.append(_result(asset=asset, output_path=output_path, frame=frame))

    if not dry_run and provenance_mode != "none":
        update_local_data_provenance(root_path, results, path=provenance_path_for_mode(provenance_mode))
    return tuple(results)


def fetch_yahoo_chart(symbol: str, *, start: date, end: date, session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
    period2 = int(datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC).timestamp())
    response = session.get(
        YAHOO_CHART_URL.format(symbol=quote(symbol, safe="")),
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result", [])
    if not result:
        error = payload.get("chart", {}).get("error") or "empty Yahoo chart response"
        raise RuntimeError(f"Yahoo chart fetch failed for {symbol}: {error}")
    return yahoo_chart_to_price_frame(result[0], start=start, end=end)


def yahoo_chart_to_price_frame(chart: dict, *, start: date, end: date) -> pd.DataFrame:
    timestamps = chart.get("timestamp") or []
    quote_rows = (chart.get("indicators", {}).get("quote") or [{}])[0]
    adjclose_rows = (chart.get("indicators", {}).get("adjclose") or [{}])[0]
    rows = []
    for index, timestamp in enumerate(timestamps):
        row_date = pd.Timestamp(timestamp, unit="s", tz="UTC").date()
        if row_date < start or row_date > end:
            continue
        close = _list_get(quote_rows.get("close"), index)
        adj_close = _list_get(adjclose_rows.get("adjclose"), index, default=close)
        if close is None and adj_close is None:
            continue
        rows.append(
            {
                "date": row_date.isoformat(),
                "open": _list_get(quote_rows.get("open"), index, default=close),
                "high": _list_get(quote_rows.get("high"), index, default=close),
                "low": _list_get(quote_rows.get("low"), index, default=close),
                "close": close if close is not None else adj_close,
                "adj_close": adj_close if adj_close is not None else close,
                "volume": _list_get(quote_rows.get("volume"), index, default=0) or 0,
            }
        )
    return _price_frame(rows)


def fetch_lbma_gold(*, start: date, end: date, session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    pm_response = session.get(LBMA_GOLD_PM_URL, timeout=60)
    pm_response.raise_for_status()
    am_response = session.get(LBMA_GOLD_AM_URL, timeout=60)
    am_response.raise_for_status()
    return lbma_gold_to_price_frame(pm_response.json(), am_response.json(), start=start, end=end)


def lbma_gold_to_price_frame(pm_payload: list[dict], am_payload: list[dict], *, start: date, end: date) -> pd.DataFrame:
    pm = _lbma_usd_by_date(pm_payload)
    am = _lbma_usd_by_date(am_payload)
    rows = []
    for row_date in sorted(set(pm) | set(am)):
        if row_date < start or row_date > end:
            continue
        price = pm.get(row_date)
        if price is None:
            price = am.get(row_date)
        if price is None:
            continue
        rows.append(
            {
                "date": row_date.isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "adj_close": price,
                "volume": 0,
            }
        )
    return _price_frame(rows)


def fetch_credit_proxy(*, start: date, end: date, fred_api_key_env: str = "FRED_API_KEY") -> pd.DataFrame:
    load_dotenv(dotenv_path=Path.cwd() / ".env")
    if not os.getenv(fred_api_key_env):
        raise RuntimeError(f"{fred_api_key_env} is required to build CreditProxy from FRED AAA/BAA.")
    provider = FREDProvider(provider_config={"api_key_env": fred_api_key_env})
    aaa = provider.fetch_observations(series_id="AAA", start=start, end=end)
    baa = provider.fetch_observations(series_id="BAA", start=start, end=end)
    return credit_proxy_from_observations(aaa=aaa, baa=baa, start=start, end=end)


def credit_proxy_from_observations(*, aaa: pd.DataFrame, baa: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if aaa.empty or baa.empty:
        return pd.DataFrame(columns=["date", "value"])
    aaa_series = _series_by_ts(aaa, "aaa")
    baa_series = _series_by_ts(baa, "baa")
    merged = pd.concat([aaa_series, baa_series], axis=1).sort_index()
    merged["value"] = merged["baa"] - merged["aaa"]
    business_days = pd.date_range(start, end, freq="B", tz="UTC")
    daily = merged[["value"]].reindex(business_days).ffill()
    daily = daily.dropna(subset=["value"]).reset_index(names="ts")
    return pd.DataFrame({"date": daily["ts"].dt.date.astype(str), "value": daily["value"].astype(float)})


def provenance_path_for_mode(mode: str) -> Path:
    if mode == "local":
        return LOCAL_PROVENANCE_PATH
    if mode == "tracked":
        return TRACKED_PROVENANCE_PATH
    raise ValueError(f"Unsupported provenance mode: {mode}")


def update_local_data_provenance(
    root: Path,
    results: tuple[LocalDataFetchResult, ...],
    *,
    path: str | Path = TRACKED_PROVENANCE_PATH,
) -> Path:
    path = root / Path(path)
    if path.exists():
        payload = json.loads(path.read_text())
    elif (root / TRACKED_PROVENANCE_PATH).exists():
        payload = json.loads((root / TRACKED_PROVENANCE_PATH).read_text())
    else:
        payload = {
            "schema_version": "local_data_provenance_v1",
            "recorded_at": _now(),
            "scope": "Local long-history research inputs for astro_research daily event studies.",
            "series": [],
        }
    series = payload.setdefault("series", [])
    by_asset = {str(item.get("asset")): item for item in series}
    for result in results:
        key = "HY_OAS_PROXY" if result.asset == "CreditProxy" else result.asset
        item = by_asset.get(key)
        if item is None:
            item = _default_provenance_record(result.asset)
            series.append(item)
        item.update(
            {
                "retrieved_at": _now(),
                "retrieved_at_basis": "Generated by scripts/fetch_local_research_data.py.",
                "coverage_start": result.coverage_start,
                "coverage_end": result.coverage_end,
                "rows": result.rows,
                "local_path": str(ASSET_OUTPUTS[result.asset]),
            }
        )
    payload["recorded_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return path


def _default_provenance_record(asset: str) -> dict[str, object]:
    if asset == "CreditProxy":
        return {
            "asset": "HY_OAS_PROXY",
            "series_id": "BAMLH0A0HYM2",
            "source": "FRED Moody's BAA minus AAA corporate yield spread",
            "provider": "Federal Reserve Economic Data (FRED)",
            "provider_family": "FRED",
            "original_symbol_or_series": "BAA minus AAA corporate yield spread",
            "retrieval_method": "Generated from FRED monthly BAA and AAA corporate yield series, then business-day forward-filled",
            "original_frequency": "monthly",
            "transformed_frequency": "business_daily",
            "fill_method": "business_daily_forward_fill",
            "license_note": "Research-local credit stress proxy; not true ICE/BofA HY OAS.",
            "redistribution_allowed": False,
            "publication_grade": False,
            "is_canonical": False,
            "is_proxy": True,
            "is_provisional": True,
            "proxy_type": "BAA_MINUS_AAA",
            "not_equivalent_to": "ICE_BofA_HY_OAS",
            "caveats": ["Credit proxy only; disclose BAA-AAA transformation in reports."],
        }
    if asset == "Gold":
        return {
            "asset": "Gold",
            "series_id": "GOLD_EXTENDED",
            "source": "LBMA gold PM USD JSON with AM USD fallback for missing PM dates",
            "provider": "LBMA / ICE Benchmark Administration",
            "provider_family": "LBMA_ICE",
            "original_symbol_or_series": "LBMA Gold Price PM USD; AM USD fallback",
            "retrieval_method": "Generated from LBMA gold PM JSON with AM JSON fallback",
            "original_frequency": "daily_fixing",
            "transformed_frequency": "business_daily",
            "fill_method": "AM_USD_fallback_when_PM_missing",
            "license_note": "Research-local LBMA historical gold price JSON; verify LBMA/ICE licensing before publication.",
            "redistribution_allowed": False,
            "publication_grade": False,
            "is_canonical": True,
            "is_proxy": False,
            "is_provisional": True,
            "caveats": ["Local research use only; do not redistribute generated CSV."],
        }
    symbol = YAHOO_SYMBOLS[asset]
    return {
        "asset": asset,
        "series_id": "SP500" if asset == "SPX" else "DXY_EXTENDED",
        "source": "Yahoo Finance chart endpoint",
        "provider": "Yahoo Finance",
        "provider_family": "Yahoo",
        "original_symbol_or_series": symbol,
        "retrieval_method": "Generated from Yahoo Finance chart endpoint",
        "original_frequency": "daily_market_session",
        "transformed_frequency": "business_daily",
        "fill_method": "none",
        "license_note": "Research-local Yahoo Finance chart endpoint export; verify redistribution rights before publication.",
        "redistribution_allowed": False,
        "publication_grade": False,
        "is_canonical": True,
        "is_proxy": False,
        "is_provisional": True,
        "caveats": ["Local research use only; do not redistribute generated CSV."],
    }


def _result(*, asset: str, output_path: Path, frame: pd.DataFrame) -> LocalDataFetchResult:
    coverage_start = str(frame["date"].min()) if not frame.empty and "date" in frame.columns else None
    coverage_end = str(frame["date"].max()) if not frame.empty and "date" in frame.columns else None
    return LocalDataFetchResult(
        asset=asset,
        output_path=output_path,
        rows=len(frame),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        source=_source_name(asset),
    )


def _source_name(asset: str) -> str:
    if asset in YAHOO_SYMBOLS:
        return f"Yahoo Finance chart endpoint:{YAHOO_SYMBOLS[asset]}"
    if asset == "Gold":
        return "LBMA gold PM JSON with AM fallback"
    if asset == "CreditProxy":
        return "FRED BAA minus AAA"
    return asset


def _lbma_usd_by_date(payload: list[dict]) -> dict[date, float]:
    values = {}
    for item in payload:
        raw_date = item.get("d")
        raw_values = item.get("v") or []
        if not raw_date or not raw_values:
            continue
        usd = raw_values[0]
        if usd is None:
            continue
        values[date.fromisoformat(raw_date)] = float(usd)
    return values


def _series_by_ts(frame: pd.DataFrame, name: str) -> pd.Series:
    working = frame.copy()
    working["ts"] = pd.to_datetime(working["ts"], utc=True).dt.normalize()
    return pd.Series(pd.to_numeric(working["value"], errors="coerce").values, index=working["ts"], name=name).dropna()


def _price_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "adj_close", "volume"])
    if frame.empty:
        return frame
    frame = frame.dropna(subset=["close"]).drop_duplicates(["date"], keep="last")
    return frame.sort_values("date").reset_index(drop=True)


def _list_get(values, index: int, default=None):
    if values is None or index >= len(values):
        return default
    value = values[index]
    return default if value is None else value


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
