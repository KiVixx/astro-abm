# Roadmap: Astro ABM

## Phase 1 — Database & Infrastructure Foundation
Objective: Stand up QuestDB and define the aligned hourly storage model for all future pipelines.

Requirements:
- INF-01
- INF-02
- INF-03

Exit Criteria:
- QuestDB runs locally via Docker with persistence.
- SQL schema exists for unified hourly facts and hourly market bars.
- Project has documented local startup instructions.

## Phase 2 — Financial Market Data Ingestion (1H OHLCV)
Objective: Ingest aligned crypto and tradfi hourly market bars into QuestDB.

Requirements:
- CRYP-01
- CRYP-02
- CRYP-03
- TRAD-01
- TRAD-02

Dependencies:
- Phase 1

Exit Criteria:
- Binance BTCUSDT ingestion works on 1-hour candles.
- SPY ingestion works from selected tradfi provider.
- Resulting bars land in QuestDB with aligned schema.

## Phase 3 — Space Weather & Ephemeris Feature Layer
Objective: Ingest or compute the astro-exogenous hourly features.

Requirements:
- SWTH-01
- SWTH-02
- SWTH-03
- SWTH-04
- SWTH-05
- EPH-01
- EPH-02
- EPH-03

Dependencies:
- Phase 1

Exit Criteria:
- NOAA SWPC pull works for selected metrics.
- Kp alignment logic to hourly buckets is implemented.
- pyswisseph generates hourly moon-phase and angular/gravity proxy features.

## Phase 4 — Social Sentiment Validation Layer
Objective: Ingest hourly crypto social features for later validation and calibration.

Requirements:
- SENT-01
- SENT-02
- SENT-03

Dependencies:
- Phase 1

Exit Criteria:
- LunarCrush ingestion works for at least one crypto symbol.
- Social features are aligned to the same UTC hour buckets and written to QuestDB.

## Phase 5 — ETL Alignment & Automation
Objective: Normalize, align, fill, and schedule all pipelines into a repeatable hourly ETL job.

Requirements:
- TRAD-03
- ETL-01
- ETL-02
- ETL-03
- ETL-04
- ETL-05

Dependencies:
- Phase 2
- Phase 3
- Phase 4

Exit Criteria:
- All sources convert to UTC bucket-start timestamps.
- Tradfi forward-fill strategy is implemented for aligned outputs.
- APScheduler triggers ETL at minute 05 each hour.
- Batch QuestDB writes succeed for all datasets.
