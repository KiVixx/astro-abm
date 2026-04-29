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

DROP VIEW IF EXISTS v_space_weather_unified;

CREATE VIEW v_space_weather_unified AS (
WITH candidates AS (
    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'authoritative' AS quality_flag, ingest_run_id, notes,
        1 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'space_weather'
      AND source = 'nasa_omni'
      AND metric_name IN ('solar_wind_speed', 'imf_bz', 'kp_index')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'authoritative' AS quality_flag, ingest_run_id, notes,
        1 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'space_weather'
      AND source = 'noaa_goes_xrs'
      AND metric_name = 'xray_flux'

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'provisional' AS quality_flag, ingest_run_id, notes,
        2 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'space_weather'
      AND source = 'noaa_swpc_recent'

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'provisional' AS quality_flag, ingest_run_id, notes,
        5 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'space_weather'
      AND source = 'noaa_swpc'
), selected AS (
    SELECT ts, metric_name, min(source_priority) AS source_priority
    FROM candidates
    GROUP BY ts, metric_name
)
SELECT
    c.ts, c.entity_type, c.entity_id, c.source, c.interval, c.asset_class, c.market, c.region,
    c.metric_name, c.metric_value, c.metric_value_2, c.metric_value_3, c.metric_value_4,
    c.observed_ts, c.available_ts, c.quality_flag, c.ingest_run_id, c.notes, c.source_priority
FROM candidates c
JOIN selected s
    ON c.ts = s.ts
   AND c.metric_name = s.metric_name
   AND c.source_priority = s.source_priority
);

DROP VIEW IF EXISTS v_open_interest_unified;

CREATE VIEW v_open_interest_unified AS (
WITH candidates AS (
    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'official' AS quality_flag, ingest_run_id, notes,
        1 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'binance_futures'
      AND metric_name IN ('open_interest', 'open_interest_value')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'official' AS quality_flag, ingest_run_id, notes,
        1 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'binance_futures_current'
      AND metric_name = 'open_interest'

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'official' AS quality_flag, ingest_run_id, notes,
        2 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'binance_vision_metrics'
      AND metric_name IN ('open_interest', 'open_interest_value')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'vendor' AS quality_flag, ingest_run_id, notes,
        3 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'tardis_binance_futures'
      AND metric_name IN ('open_interest', 'open_interest_value')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'vendor' AS quality_flag, ingest_run_id, notes,
        6 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'coinalyze'
      AND metric_name IN ('open_interest', 'open_interest_value')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'vendor' AS quality_flag, ingest_run_id, notes,
        4 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'coinalyze_1h'
      AND metric_name IN ('open_interest', 'open_interest_value')

    UNION ALL

    SELECT
        ts, entity_type, entity_id, source, interval, asset_class, market, region,
        metric_name, metric_value, metric_value_2, metric_value_3, metric_value_4,
        observed_ts, available_ts, 'vendor' AS quality_flag, ingest_run_id, notes,
        5 AS source_priority
    FROM abm_hourly_facts
    WHERE entity_type = 'derivatives'
      AND source = 'coinalyze_daily'
      AND metric_name IN ('open_interest', 'open_interest_value')
), selected AS (
    SELECT ts, entity_id, metric_name, min(source_priority) AS source_priority
    FROM candidates
    GROUP BY ts, entity_id, metric_name
)
SELECT
    c.ts, c.entity_type, c.entity_id, c.source, c.interval, c.asset_class, c.market, c.region,
    c.metric_name, c.metric_value, c.metric_value_2, c.metric_value_3, c.metric_value_4,
    c.observed_ts, c.available_ts, c.quality_flag, c.ingest_run_id, c.notes, c.source_priority
FROM candidates c
JOIN selected s
    ON c.ts = s.ts
   AND c.entity_id = s.entity_id
   AND c.metric_name = s.metric_name
   AND c.source_priority = s.source_priority
);
