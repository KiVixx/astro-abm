from datetime import UTC, datetime, timedelta

import h5py
import numpy as np
import pytest


def test_read_goes_xray_hourly_records_aggregates_primary_xrsb_flux(tmp_path):
    from astro_abm.features.goes_xray import GOES_XRS_EPOCH, read_goes_xray_hourly_records

    path = tmp_path / "sample.nc"
    base = datetime(2024, 4, 15, 9, tzinfo=UTC)
    seconds = [
        (base + timedelta(minutes=5) - GOES_XRS_EPOCH).total_seconds(),
        (base + timedelta(minutes=35) - GOES_XRS_EPOCH).total_seconds(),
        (base + timedelta(hours=1, minutes=5) - GOES_XRS_EPOCH).total_seconds(),
    ]
    with h5py.File(path, "w") as handle:
        handle.create_dataset("time", data=np.array(seconds, dtype="float64"))
        handle.create_dataset("xrsb_flux", data=np.array([1.0e-7, 3.0e-7, -9999.0], dtype="float32"))

    records = read_goes_xray_hourly_records(
        path,
        start_utc=datetime(2024, 4, 15, 9, tzinfo=UTC),
        end_utc=datetime(2024, 4, 15, 11, tzinfo=UTC),
        satellite="g16",
    )

    assert records[0]["ts"] == datetime(2024, 4, 15, 9, tzinfo=UTC)
    assert records[0]["xray_flux"] == pytest.approx(2.0e-7)
    assert records[0]["sample_count"] == 2
    assert records[0]["satellite"] == "g16"


def test_build_goes_xray_feature_rows_shapes_hourly_flux():
    from astro_abm.features.goes_xray import build_goes_xray_feature_rows

    rows = build_goes_xray_feature_rows(
        [
            {
                "ts": datetime(2024, 4, 15, 9, tzinfo=UTC),
                "xray_flux": 2.0e-7,
                "sample_count": 60,
                "satellite": "g16",
            }
        ]
    )

    assert rows[0]["entity_type"] == "space_weather"
    assert rows[0]["source"] == "noaa_goes_xrs"
    assert rows[0]["metric_name"] == "xray_flux"
    assert rows[0]["metric_value"] == 2.0e-7
    assert rows[0]["metric_value_2"] == 60.0
    assert "satellite=g16" in rows[0]["notes"]


def test_select_goes_xray_satellite_uses_g18_for_recent_years():
    from astro_abm.features.goes_xray import select_goes_xray_satellite

    assert select_goes_xray_satellite(2024) == "g16"
    assert select_goes_xray_satellite(2025) == "g18"
