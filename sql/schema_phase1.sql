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

INSERT INTO abm_hourly_facts
    (ts, entity_type, entity_id, source, interval, asset_class, market, metric_name, metric_value, observed_ts, available_ts, quality_flag)
VALUES
    ('2026-04-15T12:00:00.000000Z', 'crypto_ohlcv', 'BTCUSDT', 'binance', '1h', 'crypto', 'spot', 'close', 84500.25, '2026-04-15T12:00:00.000000Z', '2026-04-15T12:00:05.000000Z', 'final');

INSERT INTO abm_hourly_facts
    (ts, entity_type, entity_id, source, interval, asset_class, metric_name, metric_value, observed_ts, available_ts, quality_flag)
VALUES
    ('2026-04-15T12:00:00.000000Z', 'space_weather', 'GLOBAL', 'noaa_swpc', '1h', 'macro', 'kp_index', 4.33, '2026-04-15T12:00:00.000000Z', '2026-04-15T12:05:00.000000Z', 'derived');

INSERT INTO abm_hourly_facts
    (ts, entity_type, entity_id, source, interval, asset_class, metric_name, metric_value, observed_ts, available_ts, quality_flag)
VALUES
    ('2026-04-15T12:00:00.000000Z', 'ephemeris', 'GLOBAL', 'pyswisseph', '1h', 'macro', 'moon_phase_pct', 0.72, '2026-04-15T12:00:00.000000Z', '2026-04-15T12:00:00.000000Z', 'derived');

INSERT INTO abm_hourly_facts
    (ts, entity_type, entity_id, source, interval, asset_class, metric_name, metric_value, observed_ts, available_ts, quality_flag)
VALUES
    ('2026-04-15T12:00:00.000000Z', 'social_sentiment', 'BTCUSDT', 'lunarcrush', '1h', 'crypto', 'sentiment_score', 61.2, '2026-04-15T12:00:00.000000Z', '2026-04-15T12:06:00.000000Z', 'final');
