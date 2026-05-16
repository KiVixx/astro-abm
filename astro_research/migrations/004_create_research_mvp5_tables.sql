CREATE TABLE IF NOT EXISTS data_source_registry (
  ts TIMESTAMP,
  source SYMBOL,
  provider SYMBOL,
  series_id SYMBOL,
  asset SYMBOL,
  frequency SYMBOL,
  coverage_start_ts TIMESTAMP,
  coverage_end_ts TIMESTAMP,
  is_canonical BOOLEAN,
  requires_api_key BOOLEAN,
  license_note VARCHAR,
  source_url VARCHAR,
  data_version SYMBOL,
  created_at TIMESTAMP
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, source, series_id, asset);

CREATE TABLE IF NOT EXISTS macro_daily_observations (
  ts TIMESTAMP,
  series_id SYMBOL,
  source SYMBOL,
  value DOUBLE,
  original_frequency SYMBOL,
  fill_method SYMBOL,
  units SYMBOL,
  data_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, series_id, source);

CREATE TABLE IF NOT EXISTS market_asset_coverage (
  ts TIMESTAMP,
  asset SYMBOL,
  source SYMBOL,
  coverage_start_ts TIMESTAMP,
  coverage_end_ts TIMESTAMP,
  observation_count LONG,
  missing_count LONG,
  missing_pct DOUBLE,
  first_valid_ts TIMESTAMP,
  last_valid_ts TIMESTAMP,
  frequency SYMBOL,
  data_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, asset, source);

CREATE TABLE IF NOT EXISTS financial_stress_daily (
  ts TIMESTAMP,
  stress_universe SYMBOL,
  equity_stress_score DOUBLE,
  vol_stress_score DOUBLE,
  rates_stress_score DOUBLE,
  credit_stress_score DOUBLE,
  dollar_stress_score DOUBLE,
  gold_stress_score DOUBLE,
  crypto_stress_score DOUBLE,
  cross_asset_stress_score DOUBLE,
  component_count INT,
  spx_drawdown_20d DOUBLE,
  spx_drawdown_60d DOUBLE,
  spx_realized_vol_20d DOUBLE,
  spx_absret_percentile_252d DOUBLE,
  vix_level DOUBLE,
  vix_percentile_252d DOUBLE,
  vix_change_5d DOUBLE,
  us10y_change_5d DOUBLE,
  us10y_change_20d DOUBLE,
  yield_curve_10y2y DOUBLE,
  hy_oas_level DOUBLE,
  hy_oas_change_20d DOUBLE,
  nfci_level DOUBLE,
  btc_drawdown_20d DOUBLE,
  btc_realized_vol_20d DOUBLE,
  gold_return_20d DOUBLE,
  is_equity_stress BOOLEAN,
  is_vol_stress BOOLEAN,
  is_rates_stress BOOLEAN,
  is_credit_stress BOOLEAN,
  is_gold_stress BOOLEAN,
  is_crypto_stress BOOLEAN,
  is_cross_asset_stress BOOLEAN,
  stress_regime SYMBOL,
  data_version SYMBOL
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, stress_universe);

CREATE TABLE IF NOT EXISTS research_events (
  event_ts TIMESTAMP,
  event_id SYMBOL,
  event_family SYMBOL,
  event_type SYMBOL,
  source_table SYMBOL,
  source_event_id SYMBOL,
  body SYMBOL,
  body_a SYMBOL,
  body_b SYMBOL,
  aspect_name SYMBOL,
  phase_name SYMBOL,
  profile SYMBOL,
  exact_ts TIMESTAMP,
  event_date_ts TIMESTAMP,
  event_strength DOUBLE,
  cluster_count INT,
  is_primary BOOLEAN,
  is_overlapping BOOLEAN,
  eligible_for_event_study BOOLEAN,
  exclusion_reason VARCHAR,
  dataset_id SYMBOL,
  calc_version SYMBOL
) TIMESTAMP(event_ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(event_ts, event_id);

CREATE TABLE IF NOT EXISTS research_hypotheses (
  ts TIMESTAMP,
  hypothesis_id SYMBOL,
  title VARCHAR,
  status SYMBOL,
  event_family SYMBOL,
  primary_assets VARCHAR,
  primary_metrics VARCHAR,
  windows VARCHAR,
  expected_direction VARCHAR,
  baseline_methods VARCHAR,
  multiple_testing_group SYMBOL,
  min_events INT,
  min_observations INT,
  config_hash SYMBOL,
  git_commit SYMBOL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, hypothesis_id, config_hash);

CREATE TABLE IF NOT EXISTS event_study_runs (
  ts TIMESTAMP,
  run_id SYMBOL,
  hypothesis_id SYMBOL,
  run_type SYMBOL,
  event_family SYMBOL,
  config_hash SYMBOL,
  git_commit SYMBOL,
  data_version SYMBOL,
  astro_dataset_id SYMBOL,
  start_ts TIMESTAMP,
  end_ts TIMESTAMP,
  assets VARCHAR,
  metrics VARCHAR,
  windows VARCHAR,
  baseline_methods VARCHAR,
  status SYMBOL,
  warning_count INT,
  report_path VARCHAR,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, run_id);

CREATE TABLE IF NOT EXISTS event_study_results_v2 (
  ts TIMESTAMP,
  run_id SYMBOL,
  hypothesis_id SYMBOL,
  event_family SYMBOL,
  event_type SYMBOL,
  asset SYMBOL,
  window_name SYMBOL,
  baseline_method SYMBOL,
  metric SYMBOL,
  effect_value DOUBLE,
  baseline_value DOUBLE,
  effect_minus_baseline DOUBLE,
  effect_ratio DOUBLE,
  bootstrap_ci_low DOUBLE,
  bootstrap_ci_high DOUBLE,
  p_value DOUBLE,
  q_value_fdr DOUBLE,
  placebo_percentile DOUBLE,
  expected_direction SYMBOL,
  effect_direction SYMBOL,
  effect_direction_match BOOLEAN,
  n_events INT,
  n_observations INT,
  n_baseline_observations INT,
  sample_warning VARCHAR,
  overlap_warning VARCHAR,
  coverage_warning VARCHAR,
  data_version SYMBOL,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, run_id, hypothesis_id, event_family, asset, window_name, baseline_method, metric);

CREATE TABLE IF NOT EXISTS world_event_catalog (
  start_ts TIMESTAMP,
  event_id SYMBOL,
  event_name VARCHAR,
  category SYMBOL,
  region SYMBOL,
  country SYMBOL,
  end_ts TIMESTAMP,
  severity_score DOUBLE,
  date_confidence SYMBOL,
  source SYMBOL,
  source_url VARCHAR,
  notes VARCHAR,
  data_version SYMBOL
) TIMESTAMP(start_ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(start_ts, event_id);
