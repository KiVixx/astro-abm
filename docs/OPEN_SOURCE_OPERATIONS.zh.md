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
make research-prepare
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
| `make research-prepare` | 跑公開研究準備流程；可切換到本機完整或正式探索模式 |
| `make fetch-local-data` | 拉取 SPX / Gold / DXY / CreditProxy 本機長歷史 CSV，資料檔仍不進 git |
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
uv run python scripts/astro_abm_ops.py research-prepare --mode public
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms
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
| `local-full` | 本機完整研究模式 | 不一定 | 需要 `astro_research/data/local/` 內的 SPX/Gold/DXY/Credit CSV |

## 研究準備入口

`make research-prepare` 預設等同於：

```bash
uv run python scripts/astro_abm_ops.py research-prepare --mode public
```

它會建立/刷新 source registry（資料來源註冊表）、market daily（市場日線）、
macro daily（宏觀日線）、financial stress daily（金融壓力日線）、
formal readiness（正式研究就緒檢查）、DuckDB full-history store（全歷史研究庫），
最後跑 research layer validation（研究層驗證）。輸出報告在：

```text
astro_research/output/reports/research_prepare_public.md
astro_research/output/reports/research_prepare_public.json
```

## 產品日線快照維護

Scenario / Workbench 讀取的是本機日線研究快照，例如：

```text
astro_research/output/parquet/market_daily/
astro_research/output/parquet/macro_daily/
astro_research/output/parquet/financial_stress/
```

這一層和 QuestDB 的 1H crypto 維護不同。若只跑 `abm-maintenance`
的 hourly/daily 交易維護，QuestDB 會更新，但產品頁面看到的日線快照
不一定會更新。

手動刷新產品快照：

```bash
make product-snapshots
```

Docker maintenance daemon 也可以每日刷新這一層：

```bash
ASTRO_ABM_REFRESH_PRODUCT_SNAPSHOTS=1
ASTRO_ABM_PRODUCT_SNAPSHOT_MODE=local-full
```

如果也希望 daemon 每日重新拉取 SPX / Gold / DXY / CreditProxy 這些
ignored 本機長歷史 CSV，還需要明確接受本機研究資料條款：

```bash
ASTRO_ABM_REFRESH_LOCAL_DATA=1
ASTRO_ABM_ACCEPT_RESEARCH_LOCAL_TERMS=1
```

這個設計是刻意的：資料檔不進 git，且 Yahoo / LBMA / credit proxy
等來源需要授權與再分發檢查，所以自動拉取必須由維護者明確開啟。

可選模式：

```bash
uv run python scripts/astro_abm_ops.py research-prepare --mode public
uv run python scripts/astro_abm_ops.py research-prepare --mode local-full
uv run python scripts/astro_abm_ops.py research-prepare --mode formal --workers 4
uv run python scripts/astro_abm_ops.py research-prepare --mode formal --workers 4 --run-batch
```

| 模式 | 中文說明 | 適合誰 |
|---|---|---|
| `public` | 公開/API 資料準備，不要求本機私有 CSV | 新人 clone 後第一步 |
| `local-full` | 盡量使用本機長歷史 CSV；缺檔只警告 | 已放入 SPX/Gold/DXY/Credit CSV 的維護者 |
| `formal` | 額外建立昂貴的 macro_core aspect chunks（宏觀核心相位切片）、research_events（研究事件）、research_hypotheses（研究假設） | 要跑探索性正式研究批次的人 |

`formal` 模式預設不跑完整 exploratory batch（探索性正式批次），因為耗時與輸出量較大；需要時加 `--run-batch`。若你希望本機 CSV 缺失時直接失敗，加 `--strict-local-data`。

## 長歷史本機資料拉取

這四個資料檔不進 git，但新人可以自己拉取生成：

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms
```

預設情況下，這條命令會把最新 provenance（來源記錄）寫到 ignored 的：

```text
astro_research/data/local/LOCAL_DATA_PROVENANCE.local.json
```

這樣新人補完本機資料後，`git status` 仍然可以保持乾淨。只有維護者想更新 repo 內 commit-safe canonical manifest（可提交的標準來源清單）時，才使用：

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms --provenance-mode tracked
```

或只拉其中一個：

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --asset SPX --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset Gold --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset DXY --accept-research-local-terms
uv run python scripts/astro_abm_ops.py fetch-local-data --asset CreditProxy --accept-research-local-terms
```

來源與中文解釋：

| 資料 | 英文欄位/來源 | 中文說明 |
|---|---|---|
| SPX | Yahoo Finance chart endpoint `^GSPC` | S&P 500 指數日線 OHLCV |
| DXY | Yahoo Finance chart endpoint `DX-Y.NYB` | 美元指數日線 OHLCV |
| Gold | LBMA `gold_pm.json` + `gold_am.json` fallback | 倫敦金銀市場協會黃金美元定盤價；PM 優先，缺 PM 用 AM 補 |
| CreditProxy | FRED `BAA - AAA` | 信用壓力代理值；用 Baa 公司債收益率減 Aaa 公司債收益率，再轉 business-daily |

注意：Yahoo / LBMA 生成的 CSV 只作本機研究，不應從 repo 再分發；`CreditProxy` 不是 ICE/BofA HY OAS，只是長歷史信用壓力代理。

### 為什麼分成兩條命令？

```bash
uv run python scripts/astro_abm_ops.py fetch-local-data --all --accept-research-local-terms
uv run python scripts/astro_abm_ops.py research-prepare --mode local-full
```

兩條命令分工不同：

| 命令 | 中文職責 | 產物 |
|---|---|---|
| `fetch-local-data` | 只負責「把外部長歷史資料抓回本機」 | ignored CSV + ignored local provenance |
| `research-prepare --mode local-full` | 只負責「用已存在資料重建研究層」 | market/macro/stress snapshots、DuckDB、readiness report |

這樣設計的原因：

- 資料抓取有授權與網路風險：Yahoo / LBMA / FRED 可能失敗，也有 redistribution（再分發）限制；不應和研究 pipeline 綁死。
- 研究準備應可重跑：資料已存在時，可以反覆跑 `research-prepare`，不用每次重新打外部 API。
- 新人容易定位問題：第一條失敗代表來源/API/授權問題；第二條失敗代表本機資料 schema、coverage 或研究建置問題。
- 未來可以替換資料來源：若有人手動放入合法授權 CSV，只需跑第二條命令，不需要使用內建抓取器。

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
- `astro_daily_100y_snapshot` 是 canonical（權威本機）1926-2025 研究快照；它顯示 OK，就代表完整日線研究資料仍可供 DuckDB／Python／世界線脈絡使用。若顯示 WARN，狀態會列出實際缺少的檔案；其他已存在的快照仍可供不依賴該元件的研究流程使用。
- `astro_daily_100y_questdb` 是可選的 1970-2025 查詢副本。只有這項 WARN 時，不代表 100 年資料遺失；只在需要用 QuestDB 查日線資料時才需跑 `make astro-daily` 補齊。

若 canonical 快照只缺 `astro_moon_phase_events.csv`，`make astro-daily` 會自動改用月相元件修復模式：只重算 exact 月相事件與月相事件視窗，保留既有 station／aspect 視窗，不會重算 100 年 positions 與 facts。若缺少其他核心檔案，才會執行完整 build。

`make status` 也會檢查產品快照是否真的更新，而不只是檔案是否存在：market daily 按資產、macro daily 按 series、financial stress 按 universe 顯示最新日期與延遲。門檻會配合原始頻率：日頻 5 個日曆日、週頻 14 日、月頻 45 日，避免把 NFCI／USREC 這類正常週頻／月頻資料誤報為停更。若顯示 stale，依提示執行 `uv run python scripts/astro_abm_ops.py product-snapshots`。

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
