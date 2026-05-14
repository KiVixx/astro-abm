# Astro Volatility Research Note 中文版

日期：2026-05-14

## 資料與方法

- 歷史區間：2020-09-01 至 2026-05-13
- 標的：BTCUSDT、ETHUSDT
- 目標欄位：`future_abs_return_24h`
- 大波動事件定義：每個幣種自己的 rolling 90% 分位數
- rolling window：8760 小時，約一年
- 最小 rolling observations：2160 小時，約 90 天
- 星體特徵尾部：使用 train 期定義高/低 10% 尾部

這個版本不再用固定百分比門檻去比較不同年代的 BTC / ETH 波動，而是用「當時市場 regime 下是否屬於相對大波動」來判斷。這可以降低 BTC / ETH 市值變大、流動性變深後，自然波動率下降帶來的偏差。

## 主要發現

目前最穩定的特徵家族是：

- station / retrograde / speed features

也就是行星接近停滯點、逆行、速度變慢、速度分位數偏低這一類特徵。

這個家族在 train、validation、test 三段裡都相對靠前。test 期比較明顯的訊號主要來自 Venus、Mercury、Mars 的 station / speed windows。

test split 裡較強的例子：

- `venus_speed_abs:low`，lift 約 1.89
- `mercury_days_to_station_nearest:low`，lift 約 1.85
- `venus_abs_speed_percentile:low`，lift 約 1.84
- `venus_speed_zscore:low`，lift 約 1.82
- `venus_is_retrograde:true`，lift 約 1.80
- `mars_days_since_station:low`，lift 約 1.81

## 解讀

這些不是彼此獨立的 6 個訊號。很多特徵其實是在描述同一件事：

- 行星速度變慢
- 接近 station
- 剛離開 station
- 進入或處於 retrograde

所以產品上不應該把它們當成一堆獨立 alpha factors 相加，而應該把它們折疊成「事件簇」。

更合理的產品形態是：

- Venus station cluster
- Mercury station cluster
- Mars station cluster
- 慢速行星 regime cluster

然後輸出「未來大波動 watch window」，而不是直接輸出買賣方向。

## 較弱或較高風險的特徵家族

- Angle / aspect features 在 train 期看起來很強，但 validation / test 明顯變弱。
- Moon phase 在這次 scan 裡偏弱。
- Declination / OOB 有一些訊號，但穩定度不如 station / speed。

目前看起來，單純的角度相位比較容易出現故事感強、樣本內好看、樣本外退化的問題。station / speed 類訊號更值得優先研究。

## 未來風險日曆

已生成未來一年 daily risk calendar：

`outputs/astro_risk_calendar_daily_2026_2027.csv`

目前這輪結果中，未來一年最高分的風險窗口集中在：

- 2026-10-22 至 2026-11-17
- 最高分區間：2026-11-12 至 2026-11-14

這段窗口主要由以下訊號重疊造成：

- Venus low speed / retrograde / station proximity
- Mercury station proximity

這應該呈現為：

> Astro-volatility watch window

而不是：

> 方向預測、交易信號、保證波動

## 產品方向

這個研究方向更適合做成「未來波動風險提示服務」，而不是一開始就做黑盒交易模型。

比較自然的產品輸出是：

- 未來 7 天 / 30 天 / 365 天波動風險日曆
- 每個高風險窗口的 active astro clusters
- 歷史上類似窗口的大波動發生率
- 配合市場側確認：realized volatility、OI/funding、price compression

使用者可以用它來回答：

- 哪些日期值得提高注意？
- 哪些天體事件簇正在疊加？
- 當前市場是否也處於容易放大波動的狀態？

## 下一步建議

1. 把高度相關的 raw features 折疊成事件簇。
   - 例如 Venus station cluster、Mercury station cluster、Mars station cluster。

2. 風險日曆不要用 raw active feature count 加總。
   - 改成 cluster-level score，避免同一個天體事件被重複計分。

3. 加入市場側確認。
   - realized volatility
   - OI / funding regime
   - price compression / range contraction

4. 產出使用者可讀的 daily / weekly calendar。
   - 分數
   - 事件簇
   - 歷史類比
   - 限制說明

5. 暫時不要急著做黑盒模型。
   - 目前 rule-based risk calendar 更可解釋，也更符合這個項目的服務定位。
