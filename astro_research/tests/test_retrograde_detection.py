from datetime import UTC, date, datetime, timedelta

from astro_daily.retrograde import (
    STATION_IN,
    STATION_OUT,
    StationEvent,
    daily_retrograde_state,
    pair_retrograde_cycles,
    scan_station_events,
)


class FakeSpeedBackend:
    def get_speed(self, body, ts):
        if ts < datetime(2020, 1, 3, tzinfo=UTC):
            return 1.0
        if ts < datetime(2020, 1, 7, tzinfo=UTC):
            return -1.0
        return 1.0


def test_scan_station_events_detects_directional_speed_flips():
    events = scan_station_events(
        backend=FakeSpeedBackend(),
        bodies=["Mercury"],
        start_ts=datetime(2020, 1, 1, tzinfo=UTC),
        end_ts=datetime(2020, 1, 10, tzinfo=UTC),
        step_hours=6,
    )

    assert [event.station_type for event in events] == [STATION_IN, STATION_OUT]
    assert all(event.body == "Mercury" for event in events)


def test_pair_cycles_and_phase_priority():
    events = [
        StationEvent(datetime(2020, 1, 10, tzinfo=UTC), "Mercury", STATION_IN),
        StationEvent(datetime(2020, 1, 30, tzinfo=UTC), "Mercury", STATION_OUT),
    ]
    cycles = pair_retrograde_cycles(events, station_phase_days=7, pre_post_window_days=14)

    assert len(cycles) == 1
    assert cycles[0].cycle_id == "Mercury_20200110_20200130"
    assert daily_retrograde_state(date(2020, 1, 1), "Mercury", cycles, events).phase == "pre_station"
    assert daily_retrograde_state(date(2020, 1, 10), "Mercury", cycles, events).phase == "retrograde_entry"
    assert daily_retrograde_state(date(2020, 1, 20), "Mercury", cycles, events).phase == "retrograde_core"
    assert daily_retrograde_state(date(2020, 1, 25), "Mercury", cycles, events).phase == "retrograde_exit"
    assert daily_retrograde_state(date(2020, 2, 5), "Mercury", cycles, events).phase == "post_station"
