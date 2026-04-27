from datetime import UTC, datetime


def test_parse_omni2_hourly_line_extracts_space_weather_metrics():
    from astro_abm.features.nasa_omni import parse_omni2_hourly_line

    line = (
        "2024 106 09 71 9  80  12  10  1.5  2.2  3.1  4.2  5.3  6.4  7.5  8.6 "
        "-3.2 10.1 20.2 30.3 40.4 50.5 60.6 70.7 421.4 90.9 100.1 110.2 120.3 "
        "130.4 140.5 150.6 160.7 170.8 180.9 190.1 200.2 210.3 57"
    )

    row = parse_omni2_hourly_line(line)

    assert row == {
        "ts": datetime(2024, 4, 15, 9, tzinfo=UTC),
        "imf_bz": -3.2,
        "solar_wind_speed": 421.4,
        "kp_index": 5 + (2 / 3),
    }


def test_parse_omni2_hourly_line_treats_fill_values_as_missing():
    from astro_abm.features.nasa_omni import parse_omni2_hourly_line

    parts = ["2024", "106", "09"] + ["0"] * 36
    parts[16] = "999.9"
    parts[24] = "9999."
    parts[38] = "99"

    row = parse_omni2_hourly_line(" ".join(parts))

    assert row["imf_bz"] is None
    assert row["solar_wind_speed"] is None
    assert row["kp_index"] is None


def test_build_omni_space_weather_feature_rows_shapes_available_metrics_only():
    from astro_abm.features.nasa_omni import build_omni_space_weather_feature_rows

    rows = build_omni_space_weather_feature_rows(
        [
            {
                "ts": datetime(2024, 4, 15, 9, tzinfo=UTC),
                "solar_wind_speed": 421.4,
                "imf_bz": -3.2,
                "kp_index": None,
            }
        ],
        start_utc=datetime(2024, 4, 15, 0, tzinfo=UTC),
        end_utc=datetime(2024, 4, 16, 0, tzinfo=UTC),
    )

    by_metric = {row["metric_name"]: row for row in rows}

    assert set(by_metric) == {"solar_wind_speed", "imf_bz"}
    assert by_metric["solar_wind_speed"]["source"] == "nasa_omni"
    assert by_metric["solar_wind_speed"]["entity_type"] == "space_weather"
    assert by_metric["imf_bz"]["metric_value"] == -3.2
