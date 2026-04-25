from datetime import UTC, datetime

from astro_abm.models import MarketBar


class RecordingWriter:
    def __init__(self):
        self.rows = None

    def write(self, rows):
        self.rows = list(rows)


def test_run_live_etl_wires_live_sources_into_market_and_fact_writers():
    from astro_abm.etl.live import run_live_etl

    run_ts = datetime(2024, 4, 15, 15, 37, tzinfo=UTC)
    bucket_ts = datetime(2024, 4, 15, 15, 0, tzinfo=UTC)
    market_writer = RecordingWriter()
    fact_writer = RecordingWriter()

    class FakeBinanceClient:
        def fetch_recent_hourly_bars(self, symbol, limit):
            assert symbol == "BTCUSDT"
            assert limit == 2
            return [
                MarketBar(
                    symbol=symbol,
                    ts=bucket_ts,
                    open=1.0,
                    high=2.0,
                    low=0.5,
                    close=1.5,
                    volume=100.0,
                    source="binance",
                    venue="binance",
                    market_type="spot",
                    asset_class="crypto",
                )
            ]

    class FakeTradfiProvider:
        def fetch_hourly_bars(self, symbol, start, end):
            assert symbol == "SPY"
            return [
                MarketBar(
                    symbol=symbol,
                    ts=bucket_ts,
                    open=500.0,
                    high=501.0,
                    low=499.0,
                    close=500.5,
                    volume=1000.0,
                    source="polygon",
                    venue="polygon",
                    market_type="etf",
                    asset_class="tradfi",
                )
            ]

    class FakeSpaceWeatherClient:
        def fetch_plasma(self):
            return [{"time_tag": bucket_ts, "speed": 421.4}]

        def fetch_magnetometer(self):
            return [{"time_tag": bucket_ts, "bz_gsm": -3.2}]

        def fetch_xray_flux(self):
            return [{"time_tag": bucket_ts, "flux": 2.2e-08}]

        def fetch_hourly_kp(self):
            return [{"ts": bucket_ts, "kp_index": 4.67}]

    class FakeEphemerisCalculator:
        def compute_features(self, dt):
            assert dt == bucket_ts
            return {"moon_phase_pct": 72.5, "moon_is_waxing": True}

    class FakeSocialSentimentClient:
        def fetch_normalized_rows(self, symbol, hours_back):
            assert symbol == "BTC"
            assert hours_back == 24
            return [
                {
                    "symbol": "BTC",
                    "ts": bucket_ts,
                    "social_volume": 28124.0,
                    "sentiment_score": 0.73,
                }
            ]

    result = run_live_etl(
        run_ts=run_ts,
        crypto_symbols=("BTCUSDT",),
        tradfi_symbols=("SPY",),
        social_symbols=("BTC",),
        binance_client=FakeBinanceClient(),
        tradfi_provider=FakeTradfiProvider(),
        space_weather_client=FakeSpaceWeatherClient(),
        ephemeris_calculator=FakeEphemerisCalculator(),
        social_sentiment_client=FakeSocialSentimentClient(),
        market_bar_writer=market_writer,
        fact_writer=fact_writer,
    )

    assert result.run_ts == bucket_ts
    assert result.market_bars_written == 2
    assert result.fact_rows_written == 8
    assert result.skipped == ()
    assert [bar.symbol for bar in market_writer.rows] == ["BTCUSDT", "SPY"]
    assert {row["metric_name"] for row in fact_writer.rows} == {
        "moon_phase_pct",
        "moon_is_waxing",
        "solar_wind_speed",
        "imf_bz",
        "xray_flux",
        "kp_index",
        "social_volume",
        "sentiment_score",
    }


def test_run_live_etl_skips_missing_optional_live_providers():
    from astro_abm.etl.live import run_live_etl

    class FakeSpaceWeatherClient:
        def fetch_plasma(self):
            return []

        def fetch_magnetometer(self):
            return []

        def fetch_xray_flux(self):
            return []

        def fetch_hourly_kp(self):
            return []

    class FakeEphemerisCalculator:
        def compute_features(self, dt):
            return {"moon_phase_pct": 50.0}

    result = run_live_etl(
        run_ts=datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
        crypto_symbols=(),
        tradfi_symbols=("SPY",),
        social_symbols=("BTC",),
        space_weather_client=FakeSpaceWeatherClient(),
        ephemeris_calculator=FakeEphemerisCalculator(),
        market_bar_writer=RecordingWriter(),
        fact_writer=RecordingWriter(),
    )

    assert result.market_bars_written == 0
    assert result.fact_rows_written == 1
    assert result.skipped == (
        "tradfi:no_provider",
        "space_weather:no_complete_snapshot",
        "social:no_provider",
    )


def test_run_live_etl_records_optional_provider_errors_without_aborting():
    from astro_abm.etl.live import run_live_etl

    class FakeTradfiProvider:
        def fetch_hourly_bars(self, **kwargs):
            raise RuntimeError("tradfi unavailable")

    class FakeSpaceWeatherClient:
        def fetch_plasma(self):
            return []

        def fetch_magnetometer(self):
            return []

        def fetch_xray_flux(self):
            return []

        def fetch_hourly_kp(self):
            return []

    class FakeEphemerisCalculator:
        def compute_features(self, dt):
            return {"moon_phase_pct": 50.0}

    class FakeSocialSentimentClient:
        def fetch_normalized_rows(self, **kwargs):
            raise RuntimeError("plan unavailable")

    fact_writer = RecordingWriter()

    result = run_live_etl(
        run_ts=datetime(2024, 4, 15, 15, 0, tzinfo=UTC),
        crypto_symbols=(),
        tradfi_symbols=("SPY",),
        social_symbols=("BTC",),
        tradfi_provider=FakeTradfiProvider(),
        space_weather_client=FakeSpaceWeatherClient(),
        ephemeris_calculator=FakeEphemerisCalculator(),
        social_sentiment_client=FakeSocialSentimentClient(),
        market_bar_writer=RecordingWriter(),
        fact_writer=fact_writer,
    )

    assert result.fact_rows_written == 1
    assert result.skipped == (
        "tradfi:error:RuntimeError",
        "space_weather:no_complete_snapshot",
        "social:error:RuntimeError",
    )
    assert fact_writer.rows[0]["metric_name"] == "moon_phase_pct"


def test_run_live_etl_uses_askgrok_feature_rows_when_provider_supports_them():
    from astro_abm.etl.live import run_live_etl

    bucket_ts = datetime(2024, 4, 15, 15, 0, tzinfo=UTC)

    class FakeSpaceWeatherClient:
        def fetch_plasma(self):
            return []

        def fetch_magnetometer(self):
            return []

        def fetch_xray_flux(self):
            return []

        def fetch_hourly_kp(self):
            return []

    class FakeEphemerisCalculator:
        def compute_features(self, dt):
            return {"moon_phase_pct": 50.0}

    class FakeAskGrokClient:
        def fetch_feature_rows(self, start_utc, end_utc, assets):
            assert start_utc == bucket_ts
            assert end_utc == datetime(2024, 4, 15, 16, 0, tzinfo=UTC)
            assert assets == ["BTC", "ETH"]
            return [
                {
                    "ts": start_utc,
                    "entity_type": "social_sentiment",
                    "entity_id": "BTC,ETH",
                    "source": "ASKGROK_WEB",
                    "interval": "1h",
                    "asset_class": "crypto",
                    "metric_name": "askgrok_sentiment_score",
                    "metric_value": -0.25,
                    "observed_ts": end_utc,
                    "available_ts": end_utc,
                }
            ]

    fact_writer = RecordingWriter()
    result = run_live_etl(
        run_ts=bucket_ts,
        crypto_symbols=(),
        tradfi_symbols=(),
        social_symbols=("BTC", "ETH"),
        space_weather_client=FakeSpaceWeatherClient(),
        ephemeris_calculator=FakeEphemerisCalculator(),
        social_sentiment_client=FakeAskGrokClient(),
        market_bar_writer=RecordingWriter(),
        fact_writer=fact_writer,
    )

    assert result.fact_rows_written == 2
    assert result.skipped == ("space_weather:no_complete_snapshot",)
    assert fact_writer.rows[1]["metric_name"] == "askgrok_sentiment_score"
