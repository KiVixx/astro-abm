from datetime import UTC, datetime


def test_parse_noaa_table_feed_returns_typed_rows():
    from astro_abm.features.space_weather import parse_noaa_table_feed

    payload = [
        ["time_tag", "density", "speed", "temperature"],
        ["2026-04-15 12:05:00.000", "5.12", "421.4", "82034"],
    ]

    rows = parse_noaa_table_feed(payload)

    assert rows == [
        {
            "time_tag": datetime(2026, 4, 15, 12, 5, tzinfo=UTC),
            "density": 5.12,
            "speed": 421.4,
            "temperature": 82034.0,
        }
    ]


def test_parse_xray_feed_filters_to_primary_channel():
    from astro_abm.features.space_weather import parse_xray_flux_feed

    payload = [
        {
            "time_tag": "2026-04-15T12:10:00Z",
            "energy": "0.05-0.4nm",
            "flux": 1.5e-08,
        },
        {
            "time_tag": "2026-04-15T12:10:00Z",
            "energy": "0.1-0.8nm",
            "flux": 2.2e-08,
        },
        {
            "time_tag": "2026-04-15T12:11:00Z",
            "energy": "0.1-0.8nm",
            "flux": None,
        },
    ]

    rows = parse_xray_flux_feed(payload)

    assert rows == [
        {
            "time_tag": datetime(2026, 4, 15, 12, 10, tzinfo=UTC),
            "energy": "0.1-0.8nm",
            "flux": 2.2e-08,
        }
    ]


def test_expand_kp_to_hourly_repeats_each_three_hour_value_across_bucket_hours():
    from astro_abm.features.space_weather import expand_kp_index_to_hourly

    payload = [
        {"time_tag": "2026-04-15T00:00:00Z", "kp_index": 2.33},
        {"time_tag": "2026-04-15T01:00:00Z", "kp_index": None},
        {"time_tag": "2026-04-15T03:00:00Z", "kp_index": 4.67},
    ]

    rows = expand_kp_index_to_hourly(payload)

    assert rows == [
        {"ts": datetime(2026, 4, 15, 0, 0, tzinfo=UTC), "kp_index": 2.33},
        {"ts": datetime(2026, 4, 15, 1, 0, tzinfo=UTC), "kp_index": 2.33},
        {"ts": datetime(2026, 4, 15, 2, 0, tzinfo=UTC), "kp_index": 2.33},
        {"ts": datetime(2026, 4, 15, 3, 0, tzinfo=UTC), "kp_index": 4.67},
        {"ts": datetime(2026, 4, 15, 4, 0, tzinfo=UTC), "kp_index": 4.67},
        {"ts": datetime(2026, 4, 15, 5, 0, tzinfo=UTC), "kp_index": 4.67},
    ]


def test_build_space_weather_feature_rows_shapes_aligned_hourly_facts():
    from astro_abm.features.space_weather import build_space_weather_feature_rows

    ts = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    rows = build_space_weather_feature_rows(
        ts=ts,
        solar_wind_speed=421.4,
        imf_bz=-3.2,
        xray_flux=2.2e-08,
        kp_index=4.67,
        observed_ts=ts,
        available_ts=datetime(2026, 4, 15, 12, 5, tzinfo=UTC),
    )

    assert len(rows) == 4
    assert rows[0]["entity_type"] == "space_weather"
    assert rows[0]["entity_id"] == "GLOBAL"
    assert rows[0]["source"] == "noaa_swpc_recent"
    assert rows[0]["quality_flag"] == "provisional"
    assert rows[0]["metric_name"] == "solar_wind_speed"
    assert rows[1]["metric_name"] == "imf_bz"
    assert rows[2]["metric_name"] == "xray_flux"
    assert rows[3]["metric_name"] == "kp_index"


def test_space_weather_client_retries_and_tolerates_trailing_payload_text():
    from astro_abm.features.space_weather import SpaceWeatherClient

    class FakeResponse:
        text = '["header"] extra diagnostic text'

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, url, timeout):
            self.calls += 1
            if self.calls == 1:
                return type(
                    "BadResponse",
                    (),
                    {
                        "text": "not json",
                        "raise_for_status": lambda self: None,
                    },
                )()
            return FakeResponse()

    session = FakeSession()

    payload = SpaceWeatherClient(session=session, max_attempts=2, retry_sleep_seconds=0).fetch_json("plasma")

    assert payload == ["header"]
    assert session.calls == 2
