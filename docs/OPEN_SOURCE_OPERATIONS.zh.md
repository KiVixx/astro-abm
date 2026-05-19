# Astro ABM 一鍵運行與資料維護指南

這份文件面向剛 clone 項目的維護者。目標是讓資料庫、資料管線、研究輸出有固定入口，而不是靠記憶一長串命令。

## 一句話

最常用命令：

```bash
make bootstrap
```

它會：

1. 如果 `.env` 不存在，從 `.env.example` 建立一份本機 `.env`。
2. 啟動 QuestDB 與 maintenance daemon（維護常駐服務）。
3. 等待 QuestDB 可連線。
4. 套用小時級與日線研究層 schema（資料庫表結構）。
5. 確保 1926-2025 的 100 年日線核心天體 snapshot 已生成，並把 QuestDB 支援的 1970-2025 切片寫入資料庫。
6. 印出環境、資料、研究快照、Docker、QuestDB 狀態。

## 新人 10 分鐘路徑

```bash
git clone https://github.com/KiVixx/astro-abm.git
cd astro-abm
uv sync
make bootstrap
make status
make smoke
make test
```

`make smoke` 是小型公開 smoke build（煙霧測試），不需要本機長歷史 CSV，也不需要私有資料。它只驗證本機 Python、Swiss Ephemeris、研究層 build path 是否能跑通。

`make test` 會自動使用 `uv run --extra dev pytest`，所以乾淨 clone 後不需要手動安裝 pytest。

`make bootstrap` 會建立/補齊 100 年日線核心天體資料。這批資料是 deterministic（可重算）的 Swiss Ephemeris 天體資料，不依賴 API key；第一次跑會花比較久，之後 `make maintain-now` 只會檢查本機 snapshot 與 QuestDB 1970-2025 daily features 是否完整，完整時會快速跳過。

注意：QuestDB 的 WAL/partitioned designated timestamp table 不接受 1970 年以前的 timestamp。因此 `make astro-daily` 會保留完整 `1926-2025` CSV snapshot，但寫入 QuestDB 時只 ingest `1970-2025` 的可查切片；1926-1969 仍在本機 snapshot 裡，可用 Python / DuckDB / CSV 分析。

## 常用命令

| 命令 | 中文說明 |
|---|---|
| `make status` | 檢查 git、Docker、QuestDB、本機資料、研究快照狀態 |
| `make bootstrap` | 一鍵建立 `.env`、啟動 QuestDB+維護服務、套用 schema |
| `make up` | 啟動 QuestDB + maintenance daemon |
| `make db-up` | 只啟動 QuestDB |
| `make down` | 停止 Docker 服務，但不刪資料庫 volume |
| `make migrate` | 套用 QuestDB schema / migrations |
| `make maintain-now` | 立即跑一次 hourly + daily 維護；手動入口會容忍單一上游暫時失敗並保留摘要 |
| `make astro-daily` | 確保 1926-2025 的 100 年日線核心天體 snapshot 已生成，並寫入 QuestDB 1970-2025 切片 |
| `make smoke` | 跑小型公開 smoke build |
| `make checkpoint` | 重建研究 workflow checkpoint |
| `make checkpoint-check` | 只檢查現有 checkpoint，不重建 |
| `make test` | 跑完整測試，會自動帶入 dev dependencies（開發測試依賴） |

底層入口是：

```bash
uv run python scripts/astro_abm_ops.py <command>
```

例如：

```bash
uv run python scripts/astro_abm_ops.py status
uv run python scripts/astro_abm_ops.py bootstrap --db-only
uv run python scripts/astro_abm_ops.py maintain-now
uv run python scripts/astro_abm_ops.py astro-daily
uv run python scripts/astro_abm_ops.py checkpoint --check-only
```

`make maintain-now` 會使用 `--allow-partial`，適合人工維護：例如 NOAA / GOES 這類上游偶發 timeout 時，其他資料源仍會完成，輸出裡會清楚標出 failed task。若要在排程或 CI 裡使用嚴格失敗碼，可直接跑不帶 `--allow-partial` 的 `uv run python scripts/astro_abm_ops.py maintain-now`。

`make astro-daily` 的預設是核心日線資料：positions（行星位置）、retrograde cycles（逆行週期）、moon phase（月相）、daily features / facts（日線特徵/長表 facts）。它預設跳過 all-body exact aspects（全部星體精確相位），因為那是比較重的批次資料；需要完整 exact aspects 時可手動跑 `scripts/build_astro_daily.py --include-exact-aspects` 或 aspect chunk profiles。

## 三種資料完整度

開源維護時要把資料分成三種，不要混淆。

| 模式 | 中文理解 | 新人是否能直接跑 | 說明 |
|---|---|---|---|
| `smoke` | 小型煙霧測試 | 可以 | 不需要私有 CSV，用短日期範圍驗證程式能跑 |
| `public` | 公開資料模式 | 大多可以 | 依賴 FRED API key、Binance、NOAA/NASA、Swiss Ephemeris |
| `local_full` | 本機完整研究模式 | 不一定 | 需要 `astro_research/data/local/` 內的 SPX/Gold/DXY/Credit CSV |

## 本機資料邊界

以下資料不應進 git：

```text
astro_research/data/local/equity/spx_daily.csv
astro_research/data/local/commodities/gold_daily.csv
astro_research/data/local/fx/dxy_daily.csv
astro_research/data/local/credit/hy_oas_daily.csv
```

原因：

- 可能體積大。
- 可能有授權限制。
- 有些資料只能 local research，不適合 redistributing（再分發）。

應該提交的是：

```text
astro_research/data/local/README.md
astro_research/data/local/LOCAL_DATA_PROVENANCE.json
astro_research/data/local/examples/*.example.csv
```

## API key

`.env.example` 會提供本機開發預設值。正式抓 FRED macro data 時，請在 `.env` 裡設定：

```bash
FRED_API_KEY=你的_key
```

`make status` 會提示 `FRED_API_KEY` 是否存在，但不會印出 key。

## QuestDB 與 Docker

啟動：

```bash
make up
```

停止：

```bash
make down
```

只啟動資料庫：

```bash
make db-up
```

QuestDB Web UI：

```text
http://localhost:9000
```

Postgres wire port：

```text
localhost:8812
```

## 維護服務做什麼

`make up` 會用 Docker profile 啟動 `maintenance` service。

它會排程：

- hourly maintenance：每小時第 5 分鐘跑，維護近期 BTC/ETH、OI/funding、price action、regime、NOAA SWPC、ephemeris。
- daily maintenance：UTC 00:20 跑，維護 Binance Vision metrics、GOES X-ray、NOAA/NASA 太空天氣、未來一年 ephemeris。

立即手動跑一次：

```bash
make maintain-now
```

## 研究 checkpoint

如果本機已經有完整研究快照，可以跑：

```bash
make checkpoint
```

它會重建：

- crisis casebook（危機個案簿）
- H001-H004 exploratory batch（探索性正式批次）
- research readout（研究摘要）
- run manifest（可重現性清單）

如果只是檢查已有輸出：

```bash
make checkpoint-check
```

## 開源 clone 後常見警告

`make status` 可能會顯示：

- local CSV missing：代表沒有本機長歷史 CSV，只能跑 smoke/public 部分。
- research input missing：代表還沒建立 full research snapshots，不能完整跑 checkpoint。
- FRED_API_KEY missing：代表 FRED macro data 會跳過或不完整。
- QuestDB unavailable：代表資料庫還沒啟動，跑 `make bootstrap`。

這些 warning 不一定是錯誤。它們是在告訴維護者目前處於哪個資料完整度。

## 安全提交規則

提交前檢查：

```bash
git status --short --branch
git diff --check
git diff --cached --name-only
```

不要提交：

- `.env`
- `astro_research/output/`
- `astro_research/data/local/*.csv`
- `*.parquet`
- API keys / tokens / passwords
