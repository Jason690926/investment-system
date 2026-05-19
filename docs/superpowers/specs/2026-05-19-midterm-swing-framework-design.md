# 設計：中長期波段框架（穩定論點 + 程式鎖定錨點）

日期：2026-05-19
狀態：設計待用戶複審 → writing-plans

## 一、問題（用戶對 5/18 報表回饋）

1. **缺明確雙向支撐/壓力點**：報表偏多方視角，未明確告知「做多/做空各自的停損點(支撐) 與 加碼點(壓力)」。
2. **建議太短期、翻來覆去**：「今天不宜進場 / 今天又可以進場」，分析隨當日漲跌變動。
3. **不做當沖**：格局須放大至中長期，至少 2 週到 1 個月以上（買進持有 / 放空持有）。

## 二、根因（探索 ai_analyzer_v2.py 後確認）

- `ai_analyzer_v2.py:359/365` prompt 寫死 `▶ 短期（1-5日）`、`▶ 短線進場條件（1-5日）`；`:720` `今日時機：立刻可行動/等待確認/不宜行動` —— 粒度鎖在當日/短線，是「翻來覆去」的結構性來源。
- 支撐/壓力有產出（`SUPPORT:`/`RESISTANCE:` tag）但**由 AI 每日推斷**（2026-05-08 刻意保留），每日重推 → 價位漂移 → 論點漂移，與「穩定」天然衝突。

## 三、用戶拍板的三項骨架決策

| # | 決策 | 否決的替代 |
|---|------|-----------|
| D1 | **穩定論點 + 失效價位**：給 2 週-1 個月波段論點 + 明確失效價；失效未破前論點不變，每日重跑只更新「距失效距離」 | 純拉長視角每日重判（翻來覆去未根治）；雙層主軸+短線備註（AI 易自我矛盾） |
| D2 | **程式鎖定錨點**：失效價/加碼觸發鎖在程式可算結構位（復用 candlestick.py） | AI 推斷 prompt 強制（漂移風險）；混合 |
| D3 | **neutral → 誠實不操作 + 雙向條件觸發**：盤整股明講無方向 + 區間 + 突破轉多/跌破轉空 | 只寫誠實不操作；強制次要訊號選邊（=「都是買多」偏見來源） |

範圍：`analyze_stock_three_masters` + `analyze_market_only` + `generate_personal_recommendation` 三者一起對齊（用戶指定）。方案 A（新增程式 helper + 結構區塊取代短線段），方案 B（純 prompt，違反 D2）與 C（只鎖失效價，部分滿足）已否決。

## 四、設計

### §1 程式錨點 helper（資料地基）

`modules/candlestick.py` 新增：

```
calc_swing_levels(bars: list, direction: str, current_price: float|None) -> dict | None
```

- **復用**：`_find_local_peaks` / `_find_local_troughs`（既有，min_gap=3）取**最後 60 根日 K**（不足 60 則用全部，<20 根回 `None`）的真實波段高/低點，取窗口內**最近一個**局部峰=波段高、最近一個局部谷=波段低；`calc_pnf_target(bars, direction=...)`（E-1 已方向感知）取等幅波段目標。
- `mid = (range_low + range_high) / 2`，其中 `range_high`=波段高、`range_low`=波段低。`entry_zone`：long = `[波段低, mid]`、short = `[mid, 波段高]`（皆含端點，回傳為 `(下界, 上界)` tuple）。
- **回傳**（全程式算，AI 禁改；資料不足回 `None`）：

| 欄位 | long | short | neutral |
|------|------|-------|---------|
| `invalidation`（失效/停損，最重要）| 最近波段低點 | 最近波段高點 | — |
| `add_trigger`（加碼觸發）| 突破波段高/箱頂 +量 | 跌破波段低/箱底 +量 | — |
| `entry_zone`（進場區）| `[波段低, mid]` | `[mid, 波段高]` | — |
| `range_low` / `range_high` | — | — | 波段低 / 波段高 |
| `flip_long` / `flip_short` | — | — | 突破 range_high 轉多 / 跌破 range_low 轉空（+量）|
| `target` | `calc_pnf_target(long)` | `calc_pnf_target(short)` | None |

- **穩定性原理**：波段高低點只在「新局部峰谷形成」時改變，而那恰為失效事件本身；故價格未觸及失效線時，每日重跑錨點不動 → 論點不漂移。此為根治翻來覆去的核心機制。
- helper **不改** `calc_pnf_target` 行為，僅呼叫它。

### §2 prompt 重構 + 穩定鐵律（行為變更核心）

套用 `analyze_stock_three_masters` + `analyze_market_only`。

**(a) dynamic_block 注入鎖定錨點**（緊接現有 `【突破最低量能門檻】`，同「禁止更改」鐵律模式）：

```
【波段操作錨點（程式計算，禁止更改）｜方向={DIRECTION}】
失效/停損價：{invalidation} 元　加碼觸發：{add_trigger} 元
進場區：{entry_zone} 元　波段目標：{target} 元
（neutral：區間 {range_low}~{range_high}；突破上緣轉多 / 跌破下緣轉空）
```

helper 回 `None` → 注入「本期波段錨點資料不足，不給框架」（誠實>錯誤，沿用既有 fallback 慣例）。

**(b) static_block 移除短線段、換波段段**：

- **刪**：`▶ 短期（1-5日）`、`▶ 短線進場條件（1-5日）`、`今日時機：立刻可行動/等待確認/不宜行動`（`:359/365/720`）。
- **增** `### 五、波段操作框架（2週-1個月+，依 DIRECTION）`：
  - long：論點一句 + 失效價(停損) + 加碼觸發 + 進場區 + 波段目標，全引用鎖定錨點。
  - short：對稱鏡像（回補價=失效 / 加空觸發 / 反彈空區 / 下行目標）。
  - neutral：誠實不操作 + 雙向條件——「無波段方向，{range_low}~{range_high} 內不操作；突破 {range_high}+量 轉多 / 跌破 {range_low}+量 轉空」。
- **新增穩定鐵律**（static_block 交易原則區）：

  > ⚠️ 波段論點穩定性：本框架為 2 週-1 個月以上定位。失效價未被觸及前，論點與進出場價維持不變；每日重跑只更新「現價距失效價還有多遠」，禁止因單日漲跌改變方向或重設價位。不做當沖，不依當日紅綠翻轉判斷。

**(c) 逐字保留不動**（降低退化面）：第一行 `RISK_PCT/SUPPORT/RESISTANCE/WYCKOFF_PHASE/DIRECTION` 標記、威科夫定方向鐵律、風險評分、▶型態/P&F 鐵律、`_parse_tagged` 解析端。`analyze_market_only` 的 `今日時機` 同步換波段語言。

### §3 個人建議對齊 + 渲染/解析退化面

**(a) `generate_personal_recommendation` 對齊**（5 個 action_template 變體 `:855-945`，**不重寫結構**）：

1. 改標題：`▶ 短線放空條件（1-5日）`→`▶ 波段放空框架（2週-1個月+）`、`▶ 短線介入條件（1-5日）`→`▶ 波段介入框架`、`▶ 今日K棒提醒`→`▶ 盤面提醒（不構成當日進出依據）`。
2. 去當沖語：`立刻可入/等待確認/不建議進場`、`可伺機放空/等待確認` → 波段語氣「可布局/等突破確認/條件未到不進場」。
3. 注入同一組鎖定錨點：`market_summary`（`:841-844`）追加 `calc_swing_levels` 失效/加碼/進場價；prompt 加同一條穩定鐵律 + 「價位須引用鎖定錨點，禁自行估算」。

short 禁加碼鐵律（`:847-851`）、neutral 模板**保留不動**（已符精神，僅去當沖語言）。

**(b) 退化面（零退化驗證點）**：

| 面向 | 處置 |
|------|------|
| 第一行結構化標記 / `_parse_tagged` | tag 不動 → 靜態 git diff 證零影響 |
| pill 渲染（撐/壓/目標 + 方向 badge）| 來源是 tag 非新段落 → 不受影響 |
| CSS class | 不刪 `.short-term-title`/`.mid-term-title`（他處仍引用）；新段用既有 `.stop-loss`/`.support-level`/`.resistance-level`，無孤兒樣式 |
| `_clean_html_output` / print_report / dashboard | 純清理 + 整塊消費，不解析段落標題 → 不受改名影響 |

唯一須真實重跑驗證者：AI 是否遵守新 prompt（純加性+移除短線段，風險低）。

### §4 驗證與測試計畫（依 CLAUDE.md AI 修改紀律）

**(a) 程式層 pytest（零 AI 成本）** — 新增 `tests/test_swing_levels.py`：
- long / short（鏡像）/ neutral 各語意正確；target 串 `calc_pnf_target` 對應方向。
- 邊界：bars 不足 / 無局部峰谷 / current_price 缺 → 回 `None`。
- **穩定性回歸**：同 bars 多次呼叫 byte-identical；尾端加一根「未觸及失效」bar 後錨點不變（直接驗證翻來覆去根治）。
- 既有 119 tests + `calc_pnf_target` 既有測試全須續綠。

**(b) AI 管道層本機 DB raw 推演（零 AI 成本）** — 撈 DB 既有 `StockAnalysis.html_content`（long/short/neutral 各一）+ `WeeklyReport`，本機跑 `_clean_html_output` + pill 渲染 + `_parse_tagged`，git diff 證標記/解析端逐字未動。

**(c) AI 行為層（須用戶真實重跑 ~$0.6，明確告知）** — 驗 6 點：
1. 出現「波段操作框架（2週-1個月+）」，無「短期（1-5日）」/「今日時機」。
2. long/short 各有明確失效(停損)+加碼觸發價，與 dynamic_block 鎖定值一致。
3. neutral 寫「無方向+區間+雙向 flip」，非「等回檔買進」。
4. 個人建議去當沖化、價位與分析錨點一致。
5. 連兩日重跑同股（失效未破）→ 方向與價位不變（翻來覆去根治實證）。
6. 第一行標記/pill/方向 badge 全正常。

**(d) 風險與回滾**：純 prompt + 加性 helper，無 DB schema/migration。AI 不遵守 → revert 一個 commit，無資料污染。

## 五、涉及檔案

| 檔案 | 修改 |
|------|------|
| `modules/candlestick.py` | 新增 `calc_swing_levels()`（純加性，不改既有函式）|
| `modules/ai_analyzer_v2.py` | `analyze_stock_three_masters` / `analyze_market_only` static+dynamic block；`generate_personal_recommendation` 模板標題/語氣/錨點注入 |
| `tests/test_swing_levels.py` | 新增 |
| `plan.md` | 新增 §二十三 記架構決策 |
| `CLAUDE.md` | 進度快照（收工時）|

無 DB schema 變更、無 migration、無經常性 AI 成本（helper 純本機計算）。
