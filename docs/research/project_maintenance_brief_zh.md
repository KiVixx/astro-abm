# Astro ABM 項目維護者簡報

日期：2026-05-18

## 投影片 1：一句話定位

Astro ABM 目前不是交易模型，也不是完整的 agent-based simulator。

它是一個研究資料層與可再生研究輸出系統，用來檢查 astro / space-weather 事件窗口是否在歷史上與金融壓力或市場波動狀態同時出現。

## 投影片 2：現在已經有什麼

- 小時級資料工程骨架：市場資料、space-weather、ephemeris、ETL 對齊、QuestDB schema。
- 研究層 MVP：source registry、macro / market / stress / event / hypothesis / event-study tables。
- crisis casebook：針對歷史危機案例產生描述性報告與 index。
- exploratory formal batch：H001-H004 研究批次輸出、run manifest、coverage / traceability / summary artifacts。
- research readout：把 casebook 與 exploratory batch 結果整理成描述性摘要。
- workflow checkpoint：一條命令重建目前研究輸出並檢查 repo 邊界。

## 投影片 3：維護者最重要的邊界

這個 repo 的研究語言必須保持描述性：

- 可以說 historical association、coincide with、overlap、stress-regime exploration。
- 不可以說 causality、prediction、trading signal、investment advice。
- 研究輸出只能支持「歷史重疊與關聯探索」，不能被包裝成買賣建議。

資料邊界也要保持清楚：

- generated reports 應留在 `astro_research/output/`。
- local CSVs 應留在 `astro_research/data/local/` 並保持 ignored。
- secrets、API keys、credential-like strings 不應進入 staged diff。

## 投影片 4：目前研究輸出的再生順序

維護者要重建目前研究輸出時，優先使用 checkpoint：

```bash
uv run python scripts/research_workflow_checkpoint.py
```

它會依序執行：

1. build crisis casebook reports
2. build crisis casebook index
3. run H001-H004 exploratory formal batch
4. build research readout summary
5. verify outputs stay under `astro_research/output/`
6. verify generated outputs, local CSVs, and secrets are not staged
7. verify readout language remains descriptive only

## 投影片 5：快速健康檢查

只檢查既有 checkpoint 輸出，不重跑研究流程：

```bash
uv run python scripts/research_workflow_checkpoint.py --check-only
```

檢查 git 邊界：

```bash
git status --short -- astro_research/output astro_research/data/local
git diff --cached --name-only
```

預期狀態：

- `astro_research/output` 不應出現在 staged / tracked 變更中。
- `astro_research/data/local` 的 CSV 不應出現在 staged / tracked 變更中。
- staged diff 不應包含 credentials。

## 投影片 6：維護者如何讀輸出

主要入口：

- Casebook index：`astro_research/output/reports/research_workflow_checkpoint/casebook/index.md`
- Exploratory batch：`astro_research/output/reports/research_workflow_checkpoint/exploratory_batch/`
- Research readout：`astro_research/output/reports/research_workflow_checkpoint/readout.md`

讀法建議：

- 先看 `readout.md` 確認整體結論與限制。
- 再看 batch `summary.md`、`top_findings.md`、`warnings.json`。
- 最後回到 casebook 個案報告，看歷史窗口的輸入可用性與重疊情況。

## 投影片 7：run manifest 為什麼重要

`run_manifest.json` 是研究批次的可再生錨點。

它應該記錄：

- run id
- config snapshot hash
- git commit / dirty state
- input row and schema fingerprints
- output artifact hashes
- warning payload

維護者要判斷一份研究輸出是否可信，應先確認 manifest 存在，並檢查它是否對應當前想審閱的批次。

## 投影片 8：什麼不要碰，除非直接阻塞

近期維護策略是保持 checkpoint 小而穩。

不要因為整理簡報或研究輸出就順手改：

- provenance rewiring
- source registry plumbing
- formal readiness tightening
- macro coverage
- schema / migration
- transformed frequency handling

這些都是較大範圍的資料契約變更，應該獨立規劃。

## 投影片 9：目前最實用的維護流程

修改研究流程前：

```bash
git status --short --branch
uv run python scripts/research_workflow_checkpoint.py --check-only
```

修改後：

```bash
uv run pytest astro_research/tests/test_research_workflow_checkpoint.py
uv run python scripts/research_workflow_checkpoint.py
git diff --check
git status --short -- astro_research/output astro_research/data/local
```

只有在測試與 smoke path 通過、diff 聚焦、generated/local data 未進 git 時才 commit。

## 投影片 10：下一步建議

下一步應優先做可讀性與可審核性，而不是擴大研究範圍：

- 讓 checkpoint output summary 更容易被人一眼檢查。
- 把 readout 的 descriptive-only guard 持續留在自動檢查中。
- 若要新增研究假設，先確認 manifest、traceability、coverage report 能清楚說明資料來源與限制。
- 若要做產品化展示，仍要保留「非因果、非預測、非投資建議、非交易訊號」的明確邊界。
