CREATE TABLE IF NOT EXISTS event_study_results (
  ts TIMESTAMP,
  run_id SYMBOL,
  event_type SYMBOL,
  asset SYMBOL,
  window_name SYMBOL,
  metric SYMBOL,
  effect_value DOUBLE,
  baseline_value DOUBLE,
  effect_minus_baseline DOUBLE,
  bootstrap_ci_low DOUBLE,
  bootstrap_ci_high DOUBLE,
  p_value DOUBLE,
  q_value_fdr DOUBLE,
  n_events INT,
  n_observations INT,
  data_version SYMBOL,
  calc_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, run_id, event_type, asset, window_name, metric);
