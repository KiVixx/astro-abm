from datetime import UTC, datetime

from astro_daily.aspects import active_major_aspects, scan_aspect_events
from astro_daily.aspect_profiles import parse_aspect_pairs, resolve_aspect_pairs
from astro_daily.aspect_chunks import AspectBuildTask, aspect_chunk_complete, build_aspect_chunks
from astro_daily.ephemeris_backend import PositionRecord
from astro_daily.moon_phase import scan_moon_phase_events


class LinearLongitudeBackend:
    def __init__(self):
        self.start = datetime(2020, 1, 1, tzinfo=UTC)

    def get_position(self, body, ts):
        elapsed_days = (ts - self.start).total_seconds() / 86400.0
        if body == "Sun":
            lon = 0.0
        elif body == "Moon":
            lon = elapsed_days * 30.0
        elif body == "Mars":
            lon = elapsed_days * 20.0
        else:
            lon = 180.0
        return PositionRecord(
            ts=ts,
            body=body,
            lon_deg=lon % 360.0,
            lat_deg=0.0,
            distance_au=1.0,
            lon_speed_deg_day=30.0 if body == "Moon" else 20.0 if body == "Mars" else 0.0,
            lat_speed_deg_day=0.0,
            distance_speed_au_day=0.0,
            right_ascension_deg=lon % 360.0,
            declination_deg=0.0,
        )


def test_scan_moon_phase_events_finds_exact_quarter():
    events = scan_moon_phase_events(
        backend=LinearLongitudeBackend(),
        start_ts=datetime(2020, 1, 1, tzinfo=UTC),
        end_ts=datetime(2020, 1, 6, tzinfo=UTC),
        step_hours=12,
    )

    assert any(event.phase_name == "FirstQuarter" for event in events)


def test_scan_aspect_events_finds_exact_major_aspect():
    events = scan_aspect_events(
        backend=LinearLongitudeBackend(),
        bodies=("Sun", "Mars"),
        major_aspects={"sextile": 60},
        start_ts=datetime(2020, 1, 1, tzinfo=UTC),
        end_ts=datetime(2020, 1, 5, tzinfo=UTC),
        step_hours=12,
    )

    assert len(events) == 1
    assert events[0].aspect_name == "sextile"


def test_active_major_aspects_uses_configured_orbs():
    backend = LinearLongitudeBackend()
    positions = {
        "Sun": backend.get_position("Sun", datetime(2020, 1, 1, tzinfo=UTC)),
        "Mars": backend.get_position("Mars", datetime(2020, 1, 4, tzinfo=UTC)),
    }

    active = active_major_aspects(
        positions,
        bodies=("Sun", "Mars"),
        major_aspects={"sextile": 60},
        orbs={"sextile": 2},
    )

    assert active == [("Sun", "Mars", "sextile")]


def test_aspect_pair_parser_normalizes_separators_and_order():
    assert parse_aspect_pairs("Mars-Saturn,Jupiter/Saturn,Venus_Mercury") == (
        ("Mars", "Saturn"),
        ("Jupiter", "Saturn"),
        ("Mercury", "Venus"),
    )


def test_include_moon_aspects_filter():
    without_moon = resolve_aspect_pairs(profile="lunar_short_term", include_moon_aspects=False)
    with_moon = resolve_aspect_pairs(profile="lunar_short_term", include_moon_aspects=True)

    assert all("Moon" not in pair for pair in without_moon)
    assert any("Moon" in pair for pair in with_moon)


def test_aspect_event_id_is_deterministic():
    first = scan_aspect_events(
        backend=LinearLongitudeBackend(),
        bodies=("Sun", "Mars"),
        major_aspects={"sextile": 60},
        start_ts=datetime(2020, 1, 1, tzinfo=UTC),
        end_ts=datetime(2020, 1, 5, tzinfo=UTC),
        step_hours=12,
    )
    second = scan_aspect_events(
        backend=LinearLongitudeBackend(),
        bodies=("Mars", "Sun"),
        major_aspects={"sextile": 60},
        start_ts=datetime(2020, 1, 1, tzinfo=UTC),
        end_ts=datetime(2020, 1, 5, tzinfo=UTC),
        step_hours=12,
    )

    assert [(event.body_a, event.body_b, event.exact_ts) for event in first] == [
        (event.body_a, event.body_b, event.exact_ts) for event in second
    ]


def test_skip_existing_and_resume_checkpoint(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
dataset:
  dataset_id: test
  calc_version: v1
  target_start: "2020-01-01"
  target_end: "2020-01-01"
bodies:
  position_bodies:
    - Sun
    - Mars
  retrograde_bodies:
retrograde:
  station_scan_step_hours: 6
  station_refine_tolerance_seconds: 60
  station_phase_days: 7
  pre_post_window_days: 14
  event_study_window_days: 30
aspects:
  major_aspects:
    sextile: 60
clusters:
  station_cluster_windows_days:
    - 3
  aspect_cluster_windows_days:
    - 3
  weighted_pressure:
    half_life_days: 3
declination:
  fallback_oob_threshold_deg: 23.4367
""".strip()
    )
    task = AspectBuildTask(2020, ("Sun", "Mars"), datetime(2020, 1, 1, tzinfo=UTC).date(), datetime(2020, 1, 5, tzinfo=UTC).date())
    output = tmp_path / "out"

    first = build_aspect_chunks(config_path=config, output_dir=output, tasks=[task], resume=True)
    second = build_aspect_chunks(config_path=config, output_dir=output, tasks=[task], skip_existing=True, resume=True)

    assert first[0]["status"] == "built"
    assert second[0]["status"] == "skipped"
    assert aspect_chunk_complete(output, task)
    assert (output / "_checkpoints" / "aspect_build.json").exists()
