# Astro ABM

[English](README.md) · **繁體中文**

**本地優先的 AI 市場世界線推演平台。**

**正式網站：** [qooqlo.com](https://qooqlo.com)

Astro ABM 把天體運行、市場日線、宏觀與金融壓力資料，交給不同類型的 AI 代理群體共同推演，生成一條可以逐日播放的「市場世界線」。

它讓你看見：

- 每一天的天象、市場與資料覆蓋脈絡
- 散戶、槓桿交易者、長期持有者與宏觀配置者的模擬反應
- 群體事件、壓力變化、模擬因果鏈與下一日情境鋪墊
- 確定性 mock 或 OpenAI-compatible LLM 生成的中英文世界線
- 1926–2025 天體日線研究庫與持續維護的市場資料層
- 香港六合彩結果資料庫與均勻隨機娛樂世界線

> 世界線只用於相關性研究與情境推演，不是因果證明、財務建議或交易訊號。

## 快速開始

需要 Docker、Python 3.11+、[uv](https://docs.astral.sh/uv/) 與 Node.js/npm。

```bash
git clone https://github.com/KiVixx/astro-abm.git
cd astro-abm

uv sync --extra dev
npm --prefix apps/web ci
make bootstrap
```

分別開啟兩個終端：

```bash
make api
```

```bash
make web
```

然後打開 [http://127.0.0.1:3000](http://127.0.0.1:3000)。預設可使用 mock 模式，不需要 LLM API Key。

建立一條示範世界線：

```bash
make scenario-demo
```

資料與服務狀態：

```bash
make status
```

建立或更新被 Git 忽略的本機六合彩資料庫：

```bash
make marksix-maintain
```

完成後打開 `/marksix`。號碼資料覆蓋 1976 年至今；1976–1992 年資料只有年份、期號及 6+1 號碼，完整帶日期記錄由 1993 年開始。最近期數由香港賽馬會資料刷新。號碼世界線只採均勻隨機生成：每個合法組合的機率相同，歷史頻率不能預測未來開獎。只限 18 歲或以上人士娛樂使用。

第一次執行 `make bootstrap` 會建立本機資料庫並生成 100 年核心天體日線資料，因此可能需要一段時間；後續由 maintenance container 增量維護。

## 直接交給 Codex

不想手動配置時，把以下整段 Prompt 貼給 Codex：

```text
請幫我在這台電腦安裝並啟動 Astro ABM：
https://github.com/KiVixx/astro-abm.git

目標是讓我可以在瀏覽器建立並查看一條本地 AI 市場世界線。請自主完成以下工作：

1. 如果目前沒有 repo，clone 到合適的本機目錄；如果已存在，先檢查工作樹，不要覆蓋我的修改。
2. 閱讀 README.md、PROJECT_DETAILS.md 與 docs/OPEN_SOURCE_OPERATIONS.zh.md。
3. 檢查 Docker、Python 3.11+、uv、Node.js 與 npm；只安裝缺少的必要依賴。
4. 執行：
   - uv sync --extra dev
   - npm --prefix apps/web ci
   - make bootstrap
   - make status
   - make product-smoke
5. 啟動 make api 與 make web；若 8000 或 3000 被占用，使用項目提示的替代端口。
6. 驗證 API /health 和 Web 首頁可以存取，建立或重新生成 demo scenario，並告訴我可打開的網址。
7. 預設使用 mock LLM，不要求外部 API Key；不要把任何密鑰、.env、本機資料、生成報告或 output artifacts 加入 Git。
8. 遇到單一外部資料源暫時失敗時保留診斷並繼續可完成的步驟，不要無限重試。
9. 最後用中文回報：完成項目、資料完整度、服務網址、測試結果、警告與下一步。

請直接執行，不要只給我操作建議；只有在需要系統權限或不可替代的憑證時才詢問我。
```

## 詳細文件

- [項目詳細說明](PROJECT_DETAILS.md)
- [一鍵運行與資料維護指南](docs/OPEN_SOURCE_OPERATIONS.zh.md)
- [中文維護者簡報](docs/research/project_maintenance_brief_zh.md)
- [資料授權政策](DATA_LICENSE.md)
- [安全政策](SECURITY.md)
- [參與貢獻](CONTRIBUTING.md)

程式碼採用 [AGPL-3.0-or-later](LICENSE)；市場資料、研究快照及第三方天文資料各自受來源授權條款約束。
