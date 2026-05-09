def test_format_feature_summary_renders_active_counts():
    from astro_abm.analysis.feature_summary import format_feature_summary

    text = format_feature_summary(
        {
            "market_count": 10,
            "fact_count": 20,
            "etl_run_count": 2,
            "facts_by_source": [("noaa_swpc_recent", 4), ("price_action", 16)],
        }
    )

    assert "market_ohlcv_1h rows: 10" in text
    assert "etl_runs rows: 2" in text
    assert "noaa_swpc_recent: 4" in text
    assert "price_action: 16" in text
    assert "ASKGROK" not in text
