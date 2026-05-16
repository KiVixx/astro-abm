from __future__ import annotations

from datetime import date

from market_daily.providers.fred import FREDProvider
from research.macro_daily import build_macro_daily


def test_fred_missing_api_key_graceful_skip(monkeypatch, tmp_path):
    monkeypatch.delenv("MISSING_FRED_API_KEY_FOR_TEST", raising=False)
    provider = FREDProvider(provider_config={"api_key_env": "MISSING_FRED_API_KEY_FOR_TEST"})

    assert provider.available is False

    config = tmp_path / "macro.yaml"
    config.write_text(
        '''dataset:
  data_version: "test"
provider:
  source: "fred"
  api_key_env: "MISSING_FRED_API_KEY_FOR_TEST"
series:
  VIXCLS:
    units: "index"
    original_frequency: "daily"
    fill_method: "none"
'''
    )
    result = build_macro_daily(config, start=date(2020, 1, 1), end=date(2020, 1, 3))
    assert result.observations.empty
    assert result.warnings


def test_fred_zero_row_diagnostics(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"observations": [{"date": "2020-01-01", "value": "."}]}

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setenv("FRED_API_KEY_FOR_ZERO_ROW_TEST", "x")
    monkeypatch.setattr("market_daily.providers.fred.requests.get", fake_get)
    provider = FREDProvider(provider_config={"api_key_env": "FRED_API_KEY_FOR_ZERO_ROW_TEST"})

    frame = provider.fetch_observations(series_id="BAMLH0A0HYM2", start=date(2020, 1, 1), end=date(2020, 1, 2))
    diagnostics = provider.diagnostics_frame()

    assert frame.empty
    assert diagnostics.loc[0, "row_count"] == 0
    assert diagnostics.loc[0, "error_message"] == "zero_rows"
    assert "api_key" not in diagnostics.loc[0, "request_params"]


def test_local_csv_fallback_missing_file_graceful_skip(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSING_FRED_API_KEY_FOR_FALLBACK_TEST", raising=False)
    config = tmp_path / "macro.yaml"
    config.write_text(
        '''dataset:
  data_version: "test"
provider:
  source: "fred"
  api_key_env: "MISSING_FRED_API_KEY_FOR_FALLBACK_TEST"
series:
  BAMLH0A0HYM2:
    units: "percent"
    original_frequency: "daily"
    fill_method: "none"
    fallback_source: "local_csv"
    fallback_path: "missing.csv"
'''
    )

    result = build_macro_daily(config, start=date(2020, 1, 1), end=date(2020, 1, 3))

    assert result.observations.empty
    assert any("fallback local_csv missing" in warning for warning in result.warnings)
