CREATE TABLE IF NOT EXISTS market_daily_bars (
  ts TIMESTAMP,
  asset SYMBOL,
  source SYMBOL,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  adj_close DOUBLE,
  volume DOUBLE,
  currency SYMBOL,
  market_timezone SYMBOL,
  data_version SYMBOL,
  source_note VARCHAR
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, asset, source);

CREATE TABLE IF NOT EXISTS market_daily_features (
  ts TIMESTAMP,
  asset SYMBOL,
  source SYMBOL,
  ret_1d DOUBLE,
  log_ret_1d DOUBLE,
  ret_3d DOUBLE,
  ret_5d DOUBLE,
  ret_10d DOUBLE,
  ret_20d DOUBLE,
  realized_vol_5d DOUBLE,
  realized_vol_20d DOUBLE,
  realized_vol_60d DOUBLE,
  drawdown_5d DOUBLE,
  drawdown_20d DOUBLE,
  drawdown_60d DOUBLE,
  abs_ret_rank_252d DOUBLE,
  is_extreme_absret_95 BOOLEAN,
  is_extreme_absret_99 BOOLEAN,
  data_version SYMBOL
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, asset, source);

CREATE TABLE IF NOT EXISTS world_event_daily (
  ts TIMESTAMP,
  event_id SYMBOL,
  event_name VARCHAR,
  category SYMBOL,
  subcategory SYMBOL,
  severity_score DOUBLE,
  region SYMBOL,
  country SYMBOL,
  source SYMBOL,
  source_ref VARCHAR,
  data_version SYMBOL
) TIMESTAMP(ts) PARTITION BY YEAR WAL
DEDUP UPSERT KEYS(ts, event_id);
