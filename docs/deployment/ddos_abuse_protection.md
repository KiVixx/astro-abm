# DDoS 與資源濫用防護

## 防護範圍

Astro ABM 的應用層防護主要處理「成本型濫用」：大量建立世界線、反覆呼叫
LLM、超大請求、同時生成過多工作，以及持續填滿本地儲存。它不能單獨吸收
大流量網路型 DDoS；公開部署仍應使用 CDN/WAF 與 Nginx 等反向代理。

目前基線包含：

- 訪客／帳戶配額，以及不可透過清除 Guest Cookie 繞過的 IP 雜湊限流
- 建立世界線與 LLM 操作的每小時／每日限制
- 登入與註冊限制
- 最大請求本文、情境天數、資產數、代理數及文字長度
- 單一報告、報告總數及報告目錄總容量上限
- 跨 API worker 的全域與每位使用者生成並發租約
- 有上限的世界線列表讀取
- Production 預設關閉全域 LLM preset 遠端管理

客戶 IP 只以加鹽 SHA-256 雜湊保存，不保存原始 IP。雜湊仍屬可連結的營運
資料，正式環境應設定私密且穩定的 `ASTRO_ABM_RATE_LIMIT_SALT`，並限制
帳戶資料庫的存取權。

## 必要部署拓撲

```text
Internet -> CDN / WAF -> Nginx -> Uvicorn 127.0.0.1:8000
```

可由 [`deploy/nginx/astro-abm.conf.example`](../../deploy/nginx/astro-abm.conf.example)
開始設定。Nginx 官方提供[請求速率限制](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)、
[連線數限制](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html)及
[請求本文大小限制](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size)。

Uvicorn 必須只綁定 loopback 或私有網路，否則攻擊者可繞過 Nginx。只有在
直接上游確實是可信代理時，才設定 `ASTRO_ABM_TRUSTED_PROXY_IPS`。不要信任
任意來源的 `X-Forwarded-For`；FastAPI 的[代理標頭說明](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
也要求只信任已知代理。

## 重要環境變數

完整預設值見 `.env.example`。公開環境至少應檢查：

```text
ASTRO_ABM_ENV=production
ASTRO_ABM_ALLOWED_ORIGINS=https://your-web.example
ASTRO_ABM_TRUSTED_PROXY_IPS=<Nginx/CDN 實際來源 CIDR>
ASTRO_ABM_RATE_LIMIT_SALT=<長隨機私密值>
ASTRO_ABM_RATE_LIMIT_DB_TIMEOUT_SECONDS=0.25
ASTRO_ABM_IP_CREATE_RATE_PER_HOUR=12
ASTRO_ABM_IP_CREATE_RATE_PER_DAY=40
ASTRO_ABM_IP_LLM_RATE_PER_HOUR=120
ASTRO_ABM_MAX_REQUEST_BODY_BYTES=4194304
ASTRO_ABM_SCENARIO_MAX_DAYS=366
ASTRO_ABM_GENERATION_GLOBAL_CONCURRENCY=4
ASTRO_ABM_GENERATION_OWNER_CONCURRENCY=1
ASTRO_ABM_ALLOW_REMOTE_PRESET_MANAGEMENT=0
```

限額應依實際 LLM 成本、CPU、RAM、磁碟與使用者規模調整。提高單一限額時，
應同時檢查其他層，不要只放寬入口速率。

限流 SQLite 若持續繁忙超過 `ASTRO_ABM_RATE_LIMIT_DB_TIMEOUT_SECONDS`，API 會
fail closed 並回傳 `429`，不會讓洪峰長時間佔住 worker 或在計數失敗時放行。

## 維運

定期執行：

```bash
make cleanup-guests
make security-status
```

`cleanup-guests` 會移除逾期匿名工作區、孤立報告、過期生成租約、舊限流事件
與失效 session；不會修改研究資料。`security-status` 只輸出彙總計數與限額，
不顯示原始 IP、Cookie、Token 或 API Key。

建議監控 HTTP `413`、`429`、`503`、`507` 的比率、生成租約數、世界線報告
數量與目錄容量。若大量出現：

- `429`：入口或帳戶速率受限
- `503`：生成並發已滿，客戶端應稍後重試
- `507`：本地世界線儲存達到容量上限，需清理或擴容

## 已知限制

目前的持久限流與生成租約使用單機 SQLite，適合單節點公開 alpha。多節點部署
需要共享限流／租約後端（例如由 API gateway、Redis 或資料庫提供），否則每個
節點會各自計數。CDN/WAF 規則、告警、備份與事故處理仍屬部署者責任。
