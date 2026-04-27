from datetime import UTC, datetime


class FakeSwe:
    GREG_CAL = 1
    FLG_SWIEPH = 2
    FLG_SPEED = 4
    SUN = 0
    MOON = 1
    MERCURY = 2
    VENUS = 3
    MARS = 4
    JUPITER = 5
    SATURN = 6

    @staticmethod
    def utc_to_jd(year, month, day, hour, minute, seconds, cal):
        return 2460000.5, 2460000.25

    @staticmethod
    def calc_ut(jd_ut, body, flags):
        lookup = {
            FakeSwe.SUN: [100.0, 0.0, 1.0, 0.98, 0.0, 0.0],
            FakeSwe.MOON: [190.0, 0.0, 0.25, 12.5, 0.0, 0.0],
            FakeSwe.MERCURY: [130.0, 0.0, 0.4, 1.2, 0.0, 0.0],
            FakeSwe.VENUS: [160.0, 0.0, 0.7, 1.1, 0.0, 0.0],
            FakeSwe.MARS: [250.0, 0.0, 1.5, 0.7, 0.0, 0.0],
            FakeSwe.JUPITER: [10.0, 0.0, 5.0, 0.2, 0.0, 0.0],
            FakeSwe.SATURN: [310.0, 0.0, 9.0, 0.1, 0.0, 0.0],
        }
        return lookup[body], flags

    @staticmethod
    def degnorm(value):
        return value % 360.0

    @staticmethod
    def difdeg2n(a, b):
        return ((a - b + 180.0) % 360.0) - 180.0


def test_ephemeris_calculator_computes_moon_phase_percentage_from_longitudes():
    from astro_abm.features.ephemeris import EphemerisCalculator

    calculator = EphemerisCalculator(swe=FakeSwe)
    features = calculator.compute_features(datetime(2026, 4, 15, 12, 0, tzinfo=UTC))

    assert round(features["moon_phase_pct"], 4) == 50.0
    assert features["moon_is_waxing"] is True


def test_ephemeris_calculator_returns_relative_angular_features():
    from astro_abm.features.ephemeris import EphemerisCalculator

    calculator = EphemerisCalculator(swe=FakeSwe)
    features = calculator.compute_features(datetime(2026, 4, 15, 12, 0, tzinfo=UTC))

    assert features["sun_moon_angle_abs"] == 90.0
    assert features["sun_moon_angle_signed"] == 90.0
    assert features["mars_jupiter_angle_abs"] == 120.0
    assert features["mars_jupiter_angle_signed"] == -120.0


def test_build_ephemeris_feature_rows_produces_global_hourly_fact_rows():
    from astro_abm.features.ephemeris import build_ephemeris_feature_rows

    ts = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    rows = build_ephemeris_feature_rows(
        ts=ts,
        features={
            "moon_phase_pct": 58.6824,
            "moon_is_waxing": True,
            "sun_moon_angle_abs": 90.0,
            "mars_jupiter_angle_abs": 120.0,
        },
    )

    assert len(rows) == 4
    assert all(row["entity_type"] == "ephemeris" for row in rows)
    assert all(row["entity_id"] == "GLOBAL" for row in rows)
    assert rows[0]["source"] == "pyswisseph"
    assert rows[0]["quality_flag"] == "deterministic"
    assert rows[0]["metric_name"] == "moon_phase_pct"
    assert rows[1]["metric_name"] == "moon_is_waxing"
    assert rows[1]["metric_value"] == 1.0
