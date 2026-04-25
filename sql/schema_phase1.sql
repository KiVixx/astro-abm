CREATE TABLE IF NOT EXISTS abm_hourly_facts (
    ts TIMESTAMP,
    entity_type SYMBOL CAPACITY 16 CACHE INDEX,
    entity_id SYMBOL CAPACITY 256 CACHE INDEX,
    source SYMBOL CAPACITY 32 CACHE,
    interval SYMBOL CAPACITY 8 CACHE,
    asset_class SYMBOL CAPACITY 16 CACHE,
    market SYMBOL CAPACITY 16 CACHE,
    region SYMBOL CAPACITY 32 CACHE,
    metric_name SYMBOL CAPACITY 128 CACHE INDEX,
    metric_value DOUBLE,
    metric_value_2 DOUBLE,
    metric_value_3 DOUBLE,
    metric_value_4 DOUBLE,
    observed_ts TIMESTAMP,
    available_ts TIMESTAMP,
    quality_flag SYMBOL CAPACITY 16 CACHE,
    ingest_run_id SYMBOL CAPACITY 64 CACHE,
    notes VARCHAR
) TIMESTAMP(ts)
PARTITION BY MONTH
WAL;

CREATE TABLE IF NOT EXISTS market_ohlcv_1h (
    ts TIMESTAMP,
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    source SYMBOL CAPACITY 32 CACHE,
    venue SYMBOL CAPACITY 32 CACHE,
    market_type SYMBOL CAPACITY 16 CACHE,
    asset_class SYMBOL CAPACITY 16 CACHE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    quote_volume DOUBLE,
    trade_count LONG,
    complete BOOLEAN,
    observed_ts TIMESTAMP,
    available_ts TIMESTAMP
) TIMESTAMP(ts)
PARTITION BY MONTH
WAL;

CREATE TABLE IF NOT EXISTS abm_entities (
    entity_id SYMBOL CAPACITY 256 CACHE INDEX,
    entity_type SYMBOL CAPACITY 16 CACHE,
    asset_class SYMBOL CAPACITY 16 CACHE,
    source SYMBOL CAPACITY 32 CACHE,
    venue SYMBOL CAPACITY 32 CACHE,
    region SYMBOL CAPACITY 32 CACHE,
    description VARCHAR,
    active BOOLEAN,
    updated_at TIMESTAMP
) TIMESTAMP(updated_at)
PARTITION BY MONTH
WAL;

CREATE TABLE IF NOT EXISTS etl_runs (
    started_at TIMESTAMP,
    run_id SYMBOL CAPACITY 128 CACHE INDEX,
    job_type SYMBOL CAPACITY 64 CACHE INDEX,
    provider SYMBOL CAPACITY 64 CACHE INDEX,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    status SYMBOL CAPACITY 32 CACHE INDEX,
    rows_written LONG,
    skipped_existing LONG,
    errors LONG,
    finished_at TIMESTAMP,
    notes VARCHAR
) TIMESTAMP(started_at)
PARTITION BY MONTH
WAL;
