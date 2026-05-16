CREATE TABLE IF NOT EXISTS astro_daily_positions (
  ts TIMESTAMP,
  dataset_id SYMBOL,
  body SYMBOL,
  lon_deg DOUBLE,
  lat_deg DOUBLE,
  distance_au DOUBLE,
  lon_speed_deg_day DOUBLE,
  lat_speed_deg_day DOUBLE,
  distance_speed_au_day DOUBLE,
  right_ascension_deg DOUBLE,
  declination_deg DOUBLE,
  zodiac_sign SYMBOL,
  zodiac_degree DOUBLE,
  is_retrograde BOOLEAN,
  is_oob BOOLEAN,
  ephemeris_backend SYMBOL,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, dataset_id, body);

CREATE TABLE IF NOT EXISTS astro_daily_facts (
  ts TIMESTAMP,
  dataset_id SYMBOL,
  body SYMBOL,
  metric SYMBOL,
  metric_group SYMBOL,
  value_double DOUBLE,
  value_long LONG,
  value_bool BOOLEAN,
  value_symbol SYMBOL,
  value_text VARCHAR,
  unit SYMBOL,
  ephemeris_backend SYMBOL,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, dataset_id, body, metric);

CREATE TABLE IF NOT EXISTS astro_retrograde_cycles (
  station_in_ts TIMESTAMP,
  dataset_id SYMBOL,
  cycle_id SYMBOL,
  body SYMBOL,
  station_in_date_ts TIMESTAMP,
  station_out_ts TIMESTAMP,
  station_out_date_ts TIMESTAMP,
  retrograde_start_ts TIMESTAMP,
  retrograde_end_ts TIMESTAMP,
  pre_window_start_ts TIMESTAMP,
  post_window_end_ts TIMESTAMP,
  retrograde_days INT,
  pre_post_window_days INT,
  station_phase_days INT,
  station_in_type SYMBOL,
  station_out_type SYMBOL,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(station_in_ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(station_in_ts, dataset_id, cycle_id);

CREATE TABLE IF NOT EXISTS astro_aspect_events (
  exact_ts TIMESTAMP,
  dataset_id SYMBOL,
  event_id SYMBOL,
  body_a SYMBOL,
  body_b SYMBOL,
  aspect_name SYMBOL,
  aspect_deg DOUBLE,
  exact_delta_deg DOUBLE,
  relative_speed_deg_day DOUBLE,
  applying_before BOOLEAN,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(exact_ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(exact_ts, dataset_id, event_id);

CREATE TABLE IF NOT EXISTS astro_moon_phase_events (
  exact_ts TIMESTAMP,
  dataset_id SYMBOL,
  event_id SYMBOL,
  phase_name SYMBOL,
  elongation_deg DOUBLE,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(exact_ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(exact_ts, dataset_id, event_id);

CREATE TABLE IF NOT EXISTS astro_event_windows (
  ts TIMESTAMP,
  dataset_id SYMBOL,
  event_id SYMBOL,
  event_type SYMBOL,
  body SYMBOL,
  body_a SYMBOL,
  body_b SYMBOL,
  aspect_name SYMBOL,
  phase_name SYMBOL,
  exact_ts TIMESTAMP,
  exact_date_ts TIMESTAMP,
  rel_day INT,
  window_name SYMBOL,
  window_days INT,
  weight DOUBLE,
  calc_version SYMBOL
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, dataset_id, event_id);

CREATE TABLE IF NOT EXISTS astro_daily_features (
  ts TIMESTAMP,
  dataset_id SYMBOL,
  mercury_phase SYMBOL,
  mercury_is_retrograde BOOLEAN,
  mercury_days_since_station INT,
  mercury_days_until_station INT,
  mercury_cycle_id SYMBOL,
  venus_phase SYMBOL,
  venus_is_retrograde BOOLEAN,
  venus_days_since_station INT,
  venus_days_until_station INT,
  venus_cycle_id SYMBOL,
  mars_phase SYMBOL,
  mars_is_retrograde BOOLEAN,
  mars_days_since_station INT,
  mars_days_until_station INT,
  mars_cycle_id SYMBOL,
  jupiter_phase SYMBOL,
  jupiter_is_retrograde BOOLEAN,
  jupiter_days_since_station INT,
  jupiter_days_until_station INT,
  jupiter_cycle_id SYMBOL,
  saturn_phase SYMBOL,
  saturn_is_retrograde BOOLEAN,
  saturn_days_since_station INT,
  saturn_days_until_station INT,
  saturn_cycle_id SYMBOL,
  active_retrograde_count INT,
  active_retrograde_bodies VARCHAR,
  station_cluster_count_3d INT,
  station_cluster_count_7d INT,
  station_cluster_count_14d INT,
  major_aspect_active_count INT,
  major_aspect_cluster_count_3d INT,
  major_aspect_cluster_count_7d INT,
  major_aspect_cluster_count_14d INT,
  moon_phase_name SYMBOL,
  moon_phase_angle_deg DOUBLE,
  moon_illumination_pct DOUBLE,
  jupiter_saturn_angle_deg DOUBLE,
  jupiter_saturn_regime SYMBOL,
  mars_saturn_angle_deg DOUBLE,
  mars_saturn_regime SYMBOL,
  calc_version SYMBOL
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, dataset_id);
