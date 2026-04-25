from datetime import datetime


def test_format_feature_summary_renders_counts_and_recent_sentiment():
    from astro_abm.analysis.feature_summary import format_feature_summary

    text = format_feature_summary(
        {
            "market_count": 10,
            "fact_count": 20,
            "etl_run_count": 2,
            "facts_by_source": [("ASKGROK_WEB", 8), ("noaa_swpc", 4)],
            "askgrok_sentiment": [(datetime(2024, 4, 15, 15, 0), "BTC", -0.25)],
        }
    )

    assert "market_ohlcv_1h rows: 10" in text
    assert "etl_runs rows: 2" in text
    assert "ASKGROK_WEB: 8" in text
    assert "BTC: -0.25" in text
