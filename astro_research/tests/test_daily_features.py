from datetime import UTC, date, datetime

from astro_daily.build import build_astro_daily_dataset
from astro_daily.config import AstroDailyConfig, ClusterConfig, DatasetConfig, RetrogradeConfig
from astro_daily.ephemeris_backend import PositionRecord


class FakeDailyBackend:
    def get_speed(self, body, ts):
        if body == "Mercury":
            if ts < datetime(2020, 1, 3, tzinfo=UTC):
                return 1.0
            if ts < datetime(2020, 1, 7, tzinfo=UTC):
                return -1.0
            return 1.0
        return 1.0

    def get_position(self, body, ts):
        bodies = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        index = bodies.index(body)
        return PositionRecord(
            ts=ts,
            body=body,
            lon_deg=(index * 30 + ts.day) % 360,
            lat_deg=0.0,
            distance_au=1.0 + index,
            lon_speed_deg_day=self.get_speed(body, ts),
            lat_speed_deg_day=0.0,
            distance_speed_au_day=0.0,
            right_ascension_deg=(index * 30 + ts.day) % 360,
            declination_deg=0.0,
        )


def test_build_daily_dataset_produces_one_feature_row_per_day():
    config = AstroDailyConfig(
        dataset=DatasetConfig(
            dataset_id="test_daily",
            calc_version="v1",
            timezone="UTC",
            daily_sample_time_utc="00:00:00",
            target_start=date(2020, 1, 1),
            target_end=date(2020, 1, 10),
            buffer_days=3,
        ),
        position_bodies=("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"),
        retrograde_bodies=("Mercury",),
        aspect_bodies=(),
        major_aspects={},
        aspect_orbs_deg={},
        retrograde=RetrogradeConfig(
            station_scan_step_hours=6,
            station_refine_tolerance_seconds=60,
            station_phase_days=1,
            pre_post_window_days=2,
            event_study_window_days=7,
        ),
        clusters=ClusterConfig(
            station_cluster_windows_days=(3, 7, 14),
            aspect_cluster_windows_days=(3, 7, 14),
            weighted_pressure_half_life_days=3,
        ),
        oob_threshold_deg=23.4367,
    )

    dataset = build_astro_daily_dataset(config, backend=FakeDailyBackend())

    assert len(dataset.daily_features) == 10
    assert len(dataset.positions) == 100
    assert len(dataset.retrograde_cycles) == 1
    assert dataset.daily_features[3]["mercury_is_retrograde"] is True
    assert dataset.daily_features[0]["station_cluster_count_7d"] >= 1
