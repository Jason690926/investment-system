# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-13 收工 — 三 bug 徹底解決：股價格式 / NEWS 大盤 / P&F 目標）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `00f5159`（已 push origin/main）**

**本次（2026-05-13 第三輪）進度 — 用戶系統性除錯三個 bug：**

### Commit `e601d3e` — fix(format): _format_price 依 TWSE tick 規則

**用戶回報：** 創惟（6104）收盤 100.5 顯示 100、矽力-KY（6415）收盤 467.5 顯示 468

**根本診斷：** `app.py:_format_price` line 73-78 對 ≥100 用 `f"{v:,.0f}"`，Python `:.0f` 採 IEEE 754 round-half-to-even（banker's rounding）：
- `f"{100.5:,.0f}"` = `"100"`（100 偶數）→ 創惟案例
- `f"{467.5:,.0f}"` = `"468"`（468 偶數）→ 矽力案例

設計缺陷：TWSE tick 規則 100–500 元區間 tick=0.5，必然產生 .5 價位，整數格式必丟資訊。dashboard.js 用 `${q.close}` 顯示完整精度不受影響，僅 print_report.html 4 處（價格 + 撐/壓/目標 pill）受害。

**修法（依 TWSE 申報價格升降單位）：**
- `<50` 元（tick 0.01–0.05）→ 2 dp
- `50–500` 元（tick 0.10–0.50）→ 1 dp
- `≥500` 元（tick 1.00–5.00）→ 0 dp 千分位

**驗證：** `tests/test_format_price.py` 新增 15 case（user bug case + tick 邊界 + Decimal/int 輸入）。

### Commit `7ee7950` — fix(twii): NEWS 大盤數字昨日復發徹底解決

**用戶回報：** 今日財經新聞的大盤數字是昨日的，前次 `fde93e5` / `f800c7f` 修法已做過卻又發生。

**根本診斷：前次修法盲區**
- `fde93e5` 只擋 AI 從訓練資料引用歷史數字（"1778點" / "破3萬點"）
- 但若 `modules/data_fetcher.py:_fetch_ticker` 對 `^TWII` 回傳「昨日 bar」（盤前 / Render IP 限流 / Yahoo 1d chart 邊界），caller 盲拿 `iloc[-1]` 餵給 `analyze_daily_news` → AI 忠實複述「今日大盤 X 點」實際是昨日的 X
- 這不是 AI 幻覺，是資料層說謊
- 個股已透過 `32bf6af` 的 `_resolve_quote` 加 stale 偵測，TWII 卻無對等防護

用戶 pushback「股價都可以抓取了，為何大盤指數不能抓?」一針見血 — 答案：個股有 freshness check、TWII 沒有。

**修法（比照個股 stale 偵測 pattern，三件事）：**
1. `modules/data_fetcher.py:_fetch_ticker` 回傳 dict 加 `last_date` 欄位（success / fallback 兩 path 都有）
2. `run_daily_report.py` + `app.py:/api/news/regenerate` 取 `twii_data` 後檢查 `last_date == today_tw`：
   - 一致 → 注入 `twii_price` 給 `analyze_daily_news`
   - 不一致 → 不注入 + log 警告，AI prompt 無 `twii_block`，誠實 > 錯誤
3. `templates/print_report.html` 範圍 chip 改顯示 `daily_news.summary_date` 而非 `date_str[:10]`，header 文案「今日財經新聞」改「財經新聞」配合 — 同時修了 Bug 6 (2026-05-08) 「fallback yesterday 但 UI 顯示今天」的雙重誤導

**驗證：** `tests/test_twii_freshness.py` 新增 7 case（_fetch_ticker source 含 last_date / freshness logic 五情境 / analyze_daily_news 在 twii_price=None 時不注入 twii_block）。

### Commit `00f5159` — fix(pnf): 目標價邏輯不通（target<現價）

**用戶回報：** 6150 撼訊現價 73.1 但 P&F 概念目標 62（目標低於現價無意義）。質疑「其他沒有目標 = 尚未突破前高」邏輯：「照理說應該是往歷史回朔去找出現在的目標價才對」。

**根本診斷：`modules/candlestick.py:512-575 calc_pnf_target` 兩面盲區**
- 找到舊期窄箱後檢查 `cur > box_top × 1.02` 即過關
- 但 target = box_top + (box_top - box_bottom) 可能已被 cur 遠超，**code 未檢查就 return**
- 另一面：line 566-567 寫死「最近箱體未突破 → 直接 None，不往舊箱找」，違反用戶「回溯找歷史」期待

**修法（Filter A + Filter B）：**
- Filter A（既有調整）：`cur ≤ box_top × 1.02` → `continue` 往更早找（舊邏輯 `return None` 不再硬死）
- Filter B（新增）：`target ≤ cur × 1.02` → `continue` 往更早找
- 全歷史掃完都無有效箱才回 None

**設計選擇：** 保留 Darvas 等幅量度（破鄉理論）而非重寫為 P&F 3-box reversal counting — 對 AI 報表觀感無實質差異、維護成本低、與既有 commit / CLAUDE.md 語意一致。若日後 None 頻繁出現再評估升級為 P&F counting，進 `plan.md`。

**驗證：**
- 既有 7 個 calc_pnf_target test 仍綠（`test_basic_breakout` / `test_stable_target_after_new_bar` 兩個 cur 微調以滿足 Filter B）
- 新增 2 個 regression：`test_bug_c_target_below_current_rejected`（6150 風格）、`test_bug_c_unbroken_recent_falls_back_to_older_box`（用戶回溯期待）

### 本輪共同 sanity 信號
- pytest 46/46 全綠（37 candlestick + 7 TWII + 2 Bug C 新增）
- 本機因 Flask 依賴未裝，`tests/test_format_price.py` 15 case 與 `tests/test_print_report.py` 在本機無法 collect；邏輯已 inline 驗證 13/13；CI / 主開發機可正常跑
- py_compile candlestick / app / data_fetcher / run_daily_report / ai_analyzer_v2 全綠
- 三 commit 已 push（`84d1e95..00f5159`），Render auto-deploy 觸發中

### 留給下次

**Bug D（討論題，下輪評估）：** 用戶提出個股 K 棒/量能應與大盤同期表現對比，避免 AI 誤將大盤連動歸因為個股訊號。本輪未實作，三方案待評估：
- 最小版：dynamic_block 加 TWII 同期 change% + 鐵律 1 行（~$1.2 驗證 AI 重跑成本）
- 中等版：加產業同期表現（需 industry classification）
- 廣版：RS Rating（需 1 年歷史回填 + 持續維護）

下輪先進 `plan.md` 評估後再實作。

**待生產驗證（用戶 deploy 後實機操作）：**
1. 印表報表 6104 收盤 100.5 顯示 100.5、6415 收盤 467.5 顯示 467.5
2. 印表報表 6150 撼訊 P&F 目標欄位（看是顯示「—（尚未接近突破點）」還是合理的 > 73.1 數字）
3. NEWS chip 顯示實際 `summary_date`（若昨日 fallback 則顯示昨日日期）
4. 盤前清快取時 server log 出現「TWII 資料非今日」警告，AI 輸出不含大盤點位

---

## 過往進度（2026-05-13 收工 — 修 QuoteCache 鎖死 bug）

**所在週次：週7（UI 重整 + 設計層 bug 修復）**

**狀態：HEAD = `32bf6af`（已 push origin/main）**

**本次（2026-05-13 第二輪）進度 — 修「儀表板股價不是當日收盤」設計層 bug：**

**Commit `32bf6af` — fix(quote): 修 QuoteCache 鎖死壞資料整天 — post-close 優先 MarketDataCache + stale 偵測**

**根本診斷：systematic-debugging 四階段定位根因**
- `QuoteCache` 註解明文寫死「寫滿即固化（盤中自動更新由前端 retry/refresh 控制）」，但 `dashboard.js` 沒有 setInterval / retry / refresh 機制
- 失效條件只看 `cache_date == today_tw`，不分「盤前/盤中/盤後」身份；任何盤前/盤中 cache miss 觸發 yfinance → 寫入「未 settle 的 OHLC」→ 整天黏住
- DB 證據：5/13 全 18 支於 TPE 00:36 凌晨被某觸發源寫入（GitHub Actions 已停用、`run_daily_report.py` 不寫 quote_cache、dashboard.js 無 setInterval — 觸發源未確認），盤後查仍是凌晨那份；`prev_close` 連 5/12 真實收盤都對不上

**修法（B+C 融合，純後端一檔改動）：**
- 抽 `_resolve_quote(db, symbol, today_tw, now_utc, get_yahoo_quote=None)` 純函式 + 6 helpers（`_post_close_tw` / `_today_close_threshold_utc` / `_upsert_quote_cache` / `_bars_to_spark` / `_strip_internal` / `_try_market_data_cache` / `_try_quote_cache_db`）
- `api_market_quote` view function 簡化為 dispatch
- 讀取優先序變更：

| 時段 | 順序 |
|------|------|
| post-close（TW ≥ 14:30）| ① **MarketDataCache(today)**（命中即 upsert QuoteCache）→ ② mem stale check → ③ QuoteCache stale check → ④ Yahoo（upsert QuoteCache）|
| pre-close | ① mem → ② QuoteCache → ③ MarketDataCache → ④ Yahoo（保留原行為）|

- stale 判定：`cached_at < 今日 14:30 TW threshold` → 視為盤前/盤中寫入、不可信、繞過
- `_quote_cache` value 加 `_cached_at_utc` 內部欄位，回傳前以 `_strip_internal` 剝除底線開頭欄位
- 自動修復：post-close 第一個 request 進來後既有壞 QuoteCache 會被自動覆寫

**驗證：**
- 新增 `tests/test_market_quote.py`：11 case（4 helper + 5 核心優先序 / stale 偵測 + 1 pre-close 不退化 + 1 mem invalidation + 1 Yahoo 失敗）全綠
- 既有 65 case 全綠（pytest 76/76）
- `py_compile app.py` OK
- 用 DB 既有 MarketDataCache 拆 `daily_bars[-1]` 驗證 close 對得上 QuoteCache（6921.TW 5/12 → MATCH ✓）
- **生產驗證**：commit push → Render auto-deploy → user refresh dashboard → 5/13 quote_cache **18/18 從凌晨 00:36 → 20:51 TPE**；`prev_close` 全部對得上 5/12 MDC 真實收盤 ✅

**還沒解（不影響功能）：**
- 凌晨 00:36 觸發源仍未確認（剩可能：Render warm-up / 外部 monitor / 手機分頁喚醒）
- 但無論誰觸發，新邏輯都會在 post-close 第一次 request 自動修復，所以列為 nice-to-have

**留給下次：**
- 想根除凌晨觸發：查 Render 後台 cron / health-check 設定
- 想 post-close 也走 ③ MDC 而非 fall through 到 Yahoo：跑一次「一鍵分析」讓今日 MDC populate（GitHub Actions 已停用，需手動觸發）

---

## 過往進度（2026-05-13 dashboard 卡片改版 + 工具鏈擴充）

**狀態：HEAD = `37cc3e6`**

**本次（2026-05-13）進度 — dashboard 卡片重新設計（5 輪 mockup → 正式上線）：**

**Commit `37cc3e6` — feat(ui): dashboard 卡片改版 — slate-900 + 台股紅綠 + 20日K + IBM Plex Sans**

設計流程（用 ui-ux-pro-max skill 查設計庫 + mockup 迭代）：
- v1：slate-900 + IBM Plex Sans + tabular-nums（基礎方案）
- v2：加 7 日 sparkline + RISK 改 inline chip + 移除 risk-bar
- v3：翻轉漲跌色為**台股紅綠慣例**（用戶提醒既有 app.css 用美股慣例是 bug）
- v4：badge 從 absolute 改 inline（解決「觀察中」3 字壓到 price）+ sparkline 改 mini K 棒
- v5：對齊修正（wyckoff/risk chip） + K 棒擴增 7 → 20 根（覆蓋 1 個月交易日）

**主要技術變動：**
1. **CSS token 重定義** `static/css/app.css`：
   - 主題：slate-950/900 系列（bg `#020617` / card `#0F172A` / border `#334155`）
   - 漲跌：`--up: #EF4444` / `--down: #22C55E`（台股慣例）
   - 風險：`--risk-low: cyan` / `--risk-mid: amber` / `--risk-high: fuchsia`（獨立 token 避開紅綠）
   - 強調：`--accent: #38BDF8`（已分析、tab active）
2. **全檔色彩翻轉**：`.up/.down/.bull/.bear/.support-level/.resistance-level/.wyckoff-*/.qs-*` 從美股慣例改為台股
3. **字體**：IBM Plex Sans Google Font + `font-feature-settings: 'tnum' on` 全域
4. **卡片 layout**：
   - badge `absolute` → inline 放 card-name 上方
   - 新增 `.card-status-row`（wyckoff + RISK chip 並排）
   - 新增 `.card-spark-wrap`（20 日迷你 K 線 SVG）
   - 移除 `.risk-bar/.risk-fill`（長條圖換 inline chip）
   - `.analyzed-badge` display:none（漸層 bar 已足夠）
5. **Sparkline 後端**：
   - `get_stock_quote` 抓 30 天 → 回傳 `spark_bars: [{o,h,l,c}] × 20`
   - `api_market_quote` 三條讀取路徑（QuoteCache / MarketDataCache / Yahoo）均回 spark_bars
6. **Sparkline 前端**：
   - `renderSparkline(bars)`：動態生成 SVG 20 根 K 棒（紅實體 = 漲 / 綠實體 = 跌）
   - `sparkPctLabel(bars)`：算 20D 整體漲跌幅 + 染色
   - `buildCard / updateCardPrice / markCardAnalyzed` 全部適配新結構

**Memory 紀錄：**
- 新增 `feedback_taiwan_stock_color_convention.md`：台股漲跌色慣例規則，未來會話開工自動載入提醒

**Claude Code 工具鏈擴充（user scope 全域）：**
- 安裝 `ui-ux-pro-max` skill（67 風格 / 161 配色 / 99 UX 準則，本次主要用它跑 fintech dashboard design system）
- 安裝 `context7` MCP server（即時抓 Flask/SQLAlchemy/Anthropic SDK 等套件文件）
- CLAUDE.md「Claude Code 工具鏈」區塊新增說明

**驗證：**
- pytest 37/37 通過
- py_compile 全綠
- dashboard.js / app.js syntax OK
- Render 自動 deploy 中（webhook 觸發）

---

## 過往進度（2026-05-12 收工 — 6項邏輯Bug全修）

**狀態：HEAD = `fb58e39`**

**本次（2026-05-12 第二輪）進度 — 系統性審視週7程式碼，找出並修正 6 項邏輯 Bug：**

**Commit `fb58e39` — fix(audit): 修6項邏輯Bug — HTML清理/AI幻覺/權限/時間鎖/週末視窗/快取TW date**

| # | 嚴重度 | 檔案:行 | Bug | 修法 |
|---|--------|---------|-----|------|
| 1 | 🔴 | `ai_analyzer_v2.py:875` | `analyze_taiwan_market_v2` 末尾無 `_clean_html_output`，AI 若回傳 `<head>/<style>` 會污染頁面（與其他三個 AI 函式不一致）| 末尾加 `_clean_html_output(...)` 包裝 |
| 2 | 🔴 | `ai_analyzer_v2.py:973-977` | `analyze_weekly_taiwan_v2` 沒加歷史幻覺鐵律（commit `fde93e5` 只強化了 daily_news + taiwan_market_v2，週報函式遺漏）| prompt 加【數據鐵律】區塊（與 taiwan_market_v2 同模板）|
| 3 | 🟡 | `app.py:738-739` | `api_clear_today_cache` 缺 admin 檢查，任何登入用戶可清光所有共用快取 | 加 `if current_user.role != 'admin': return 403` |
| 4 | 🟡 | `app.py:505,509` | 時間鎖與冷卻硬編碼為 `< 0`（永遠停用），CLAUDE.md 標註的「測試模式遺留」 | 還原 `< 15` 與 `< 4 * 3600`，移除測試模式註解 |
| 5 | 🟡 | `app.py:822-827` + `dashboard.js:208-214` | 週末視窗只判 `h >= 14`，週五 14:00–14:29 報表已切到「週末視窗」但週報未跑 → daily_news=None、weekly=None 頂部空缺 | 兩端都改為 `h > 14 or (h == 14 and m >= 30)` 精確到分鐘 |
| 6 | 🟢 | `app.py:304, 382` | `api_market_quote` / `api_market_data` 用 UTC `dt_date.today()`，與其他端點用的 TW date 不一致，08:00 TW 翻日後 cache key 失準 | 改用 `(utcnow + 8h).date()` |

**未修 — 微小 7：`_fmt_bars` 特徵基準退化**
- 重新審視後判斷不算 bug：現有 fallback 已處理 `range_high == range_low → 中段` / `vol_avg == 0 → 均量`；生產 daily_bars ≥ 60 根不會踩到。

**驗證：**
- `pytest tests/test_candlestick.py` → 37/37 通過
- `py_compile`：app.py / ai_analyzer_v2.py / run_daily_report / run_weekly_report / stock_service 全綠
- `dashboard.js` JS SYNTAX OK
- 變更：3 檔、+23/-14 行

**注意：修 2 改了 `analyze_weekly_taiwan_v2` 的 prompt，下次週報跑（最近的週末視窗）才會看到效果。模板已被 `taiwan_market_v2` 同步驗證，不需特別重跑。**

---

**本次（2026-05-12 第一輪）進度 — K線多空欄位誤判修正：**

**Commit `e4bec98` — fix(kline): 修正K線多空欄位誤判邏輯 + 加入程式化特徵標注**

**根本診斷：AI 看紅K就說看漲、綠K就說看跌**
- `_fmt_bars()` 只輸出 OHLCV，AI 靠單根顏色+「陽線（收>開）看漲/陰線（收<開）看跌」速查推斷
- `analyze_market_only` prompt table 有「多空」欄，AI 填的是主觀判斷，非程式計算
- 違背本間宗久原則：十字星含意取決於高位/低位，非固定看法

**修法：**
- `_fmt_bars()`：每根K棒加入程式計算 `【特徵=量能·位置[·跳空]】`
  - 量能：放量(>1.5x)/縮量(<0.7x)/均量，基準 bars[-20:] 平均
  - 位置：極高位/高位/中段/低位/極低位，基準 bars[-20:] 高低範圍
  - 跳空：open vs prev_close ±1% 判定
- `analyze_market_only()` prompt：table 「多空」欄改「特徵」，移除「陽線/陰線」速查，加特徵欄鐵律，加K線序列bullet
- `analyze_stock_three_masters()` prompt：「說明多空含意」改「結合特徵量能·位置解讀」，加禁止只看紅/綠鐵律

**本次（2026-05-11）進度 — NEWS 區塊無法即時重生：**

**Commit `f800c7f` — fix(news): 清快取一併刪 DailyMarketSummary + 新增 /api/news/regenerate**

**根本診斷：清快取後 NEWS 仍顯示舊資料**
- `api_clear_today_cache` 只刪 `StockAnalysis`，完全不動 `DailyMarketSummary`
- NEWS 區塊讀最近一筆 `DailyMarketSummary`，只有 14:30 batch 才會更新
- 清快取→重跑一鍵分析：個股重新產生，NEWS 永遠是舊的

**修法：**
- `api_clear_today_cache`：一起刪 `DailyMarketSummary` 所有記錄
- 新增 `/api/news/regenerate` POST：重抓 RSS + 取 TWII 即時行情 + 呼叫 AI（含新鐵律 prompt）+ 覆寫今日 `DailyMarketSummary`
- `dashboard.js clearTodayCache`：清完後自動串呼 `/api/news/regenerate`，按鈕顯示「重生新聞…」進度

**本次（2026-05-11）進度 — AI 歷史幻覺封鎖 + K線 30 項測試：**

**Commit `fde93e5` — fix(ai): 封鎖AI引用歷史幻覺數字 + 新增K線30項測試**

**根本診斷：「1778點/突破3萬點」重複出現的根因**
- 前次修法（pubDate 48h + TWII注入）只保護 `analyze_daily_news()`
- `analyze_taiwan_market_v2()` 完全無防護 → AI 從訓練資料注入歷史事件
- 修法：兩個函式均加入明確禁令，列舉具體禁止數字（「1778點」「突破3萬點」「史高」等）

**修法細節：**
- `analyze_daily_news()`：補 2 條鐵律（禁歷史事件數字 + 新聞含此類描述需核實才引用）
- `analyze_taiwan_market_v2()`：新增【數據鐵律】區塊，注入當前收盤點位 `{price}` 並禁止引用訓練資料歷史數字；提供替代寫法（「創近N日高」）

**K線型態測試套件：**
- 新增 `tests/test_candlestick.py`，30 項測試，全部通過
- 覆蓋：Bug1三山頂freshness / Bug2嚴格峰谷 / Bug3大陽線gap_down / Bug4/5三白兵三黑鴉首根影線 / Bug6/7星形型態體型要求 + 回歸測試（正常形態不誤觸）

**本次（2026-05-11）進度 — K線型態全面 Bug 修正（7項）：**

**Commit `5b0fd26` — fix(candlestick): 7項K線型態Bug修正**

| # | 型態 | Bug | 修法 |
|---|------|-----|------|
| 1 | 三山頂/三川底 | 型態成立後每日重複觸發（舊高低點持續在40根窗口內）| 加入 `bars_since_peak/trough <= 15`，第三峰/谷超過15根前不觸發 |
| 2 | 峰谷偵測函數 | `>=` / `<=` 導致平台頂底（多根同高）每根都算峰值，製造假三山 | 改為嚴格 `>` / `<` |
| 3 | 大陽線 | 只排除 `gap_up`，跳空低開強力收復仍顯示「無跳空缺口」，描述矛盾 | 補上 `not gap_down` |
| 4 | 三白兵 | 第一根K棒（i-2）上影線未驗證 | 補 `(h[i-2]-c[i-2]) <= 30% 實體` |
| 5 | 三黑鴉 | 第一根K棒（i-2）下影線未驗證 | 補 `(c[i-2]-l[i-2]) <= 30% 實體` |
| 6 | 早晨之星 | 第一根任意陰線即觸發、第三根小陽線也觸發 | 要求第一根實體 > 50% 振幅、第三根同樣 > 50% |
| 7 | 黃昏之星 | 同上，第一根/第三根大小無限制 | 要求第一根大陽線（>50%）、第三根大陰線（>50%）|

**根本診斷：三山頂「一直顯示」的根因**
- Bug 2（`>=`偵測假峰）× Bug 1（無時效性）= 平台震盪股每天觸發
- 修後：第三峰必須是近15根內的真實局部高點，超過後自動靜音

---

**本次（2026-05-08）進度 — 分析日 14:30 邊界修正：**

**Bug E（分析日用 UTC 凌晨 00:00 翻日，08:00~14:30 灰色地帶）**
- ✅ 根因：`date.today()` 在 UTC+0 伺服器上，台灣 08:00 就翻日 → 08:00~14:30 快取失效但收盤資料還不在，跑出來是昨日資料且擋住下午正確分析
- ✅ 修法：新增 `_analysis_day_tw()`（三個檔案共用邏輯）
  - 平日 14:30 後 → 今日；其他（含週末/假日）→ 往前找最近工作日
- ✅ `app.py`：三個分析端點（`api_get_analysis` / `api_analyze_stock` / `api_recommend_stock`）改用此 helper
- ✅ `stock_service.py` `get_user_stocks()`：改由 `analysis_day` 精確篩選（非 `max(date)` 不限日期）
  - 效果：14:30 後看板卡片全部回到「尚未分析」→ 視覺提示可以分析了
- ✅ `run_daily_report.py`：`is_cached_today` / `cache_market_analysis` 改用 TW date 保持一致

**本次（2026-05-08）進度 — 週報觸發邏輯重整：**

**週末視窗 + 一鍵分析合併週報**
- ✅ 設計：週五 14:00 ~ 週一 09:00 = 週末視窗，一個入口
- ✅ `dashboard.js`：`isWeeklyWindow()` 判斷（UTC+8 換算）；`analyzeAll()` 在週末視窗先射 `/api/weekly-report/generate` 背景並行；`updateAnalyzeBtn()` 動態標示「含週報」
- ✅ `dashboard.html`：移除獨立「📊 週報」按鈕
- ✅ `app.py` `show_weekly`：補上週一 09:00 前條件 `(wd==0 and h<9)`
- ✅ `run_weekly_report.py`：`week_end` 改用 `(weekday-4)%7` 永遠指向本週五（修前週六跑 → 日期顯示 Mon~Sat）
- ✅ `run_daily_report.py`：移除 Friday auto-trigger（改為 button-driven）

**本次（2026-05-08）進度 — K線型態酒田五法強化 + 四項修復：**

**Bug 7（三山頂/三川底 偽陽性，9根就觸發）**
- ✅ 根因：用固定 bar index (`highs[2]`, `highs[6]`) 而非真實局部高低點；窗口只有 9 根，遠不足
- ✅ 修法：新增 `_find_local_peaks()` / `_find_local_troughs()`（左右各 min_gap=3 根確認真實峰谷）；lookback 改為 40 根；要求3個高/低點彼此間距 ≥ 5 根且高度在均值 ±3% 以內
- ✅ `_MULTI_CANDLE` 三山/三川 candle_count 從 10 → 40（與 lookback 一致）

**三白兵/三黑鴉條件補齊（酒田正規）**
- ✅ 舊：只要連三陽/陰線收盤遞增/減
- ✅ 新：加入「每根開盤必須在前根實體內（不跳空進入）」+ 上/下影線短（≤ 實體的 30%）
- 效果：連三跳空大漲現在只觸發三空上升，不再誤觸三白兵

**新增三空（酒田五法）**
- ✅ 三空上升（酒田）：連三根跳空上漲 → bearish（追漲已竭）
- ✅ 三空下降（酒田）：連三根跳空下跌 → bullish（恐慌已竭）

**新增三法（酒田五法）**
- ✅ 上升三法（酒田）：大陽線 → 3根在範圍內整理 → 大陽線突破 → bullish（多頭趨勢確認）
- ✅ 下降三法（酒田）：大陰線 → 3根在範圍內整理 → 大陰線跌破 → bearish（空頭趨勢確認）

**K線型態補全（酒田單根）**
- ✅ 新增蜻蜓十字（長下影無上影，強烈底部訊號 bullish/strong）
- ✅ 新增長腳十字（上下影線均長，強烈不確定 neutral/medium）
- ✅ 新增平頭頂（兩根高點相同，bearish/medium）、平頭底（兩根低點相同，bullish/medium）
- ✅ 十字星加互斥條件，避免與蜻蜓十字/長腳十字重複觸發

**Bug A（股票名稱旁股價消失）**
- ✅ 根因：`app.py /print-report` 用 `cache_date == today_tw` 查 QuoteCache → 14:30 前批次未跑，回傳空
- ✅ 修法：改用 max(cache_date) subquery 取最近一筆（與 Bug6 DailyMarketSummary 同模式）

**Bug B（報表未提示量需突破多少張）**
- ✅ 根因：突破/Spring 量能門檻完全依賴 AI 自行發揮，無程式計算數值
- ✅ 修法：`ai_analyzer_v2.py` 兩個函式新增 `_vol_breakout = vol_5avg × 1.5`、`_vol_spring = vol_5avg × 1.2`
  - dynamic_block 注入【突破最低量能門檻】欄位（程式計算，禁止更改）
  - `analyze_stock_three_masters` action_section 直接嵌入具體張數
  - `analyze_market_only` static_block 等待條件指示 AI 引用欄位數值

**Bug C（P&F 目標價偏高 — 破鄉理論驗證）**
- ✅ 破鄉理論公式正確：`target = base_high + (base_high - base_low)` = 等幅量度 Measured Move
- ✅ 問題是基底定義不嚴謹：用趨勢段（波動率>35%）當基底 → 目標必然偏高
- ✅ 修法 `calc_pnf_target`：
  1. 波動率 > 35% → 縮至 4 根找更緊箱體
  2. `current_price < base_high × 0.85` → 回 None（尚未接近突破點，不顯示目標）
- ✅ 兩個 analyze 函式均傳入 `current_price` 參數；None 時顯示「—（尚未接近突破點）」

**本次（2026-05-08）進度 — 財經新聞區塊修復：**

**Bug 6（每日財經新聞區塊完全不出現）**
- ✅ 根因 A：`app.py /print-report` 用 `filter_by(summary_date=今天)` 查 DB，但批次 14:30 才跑 → 早上開報表回傳 None → 整個 `§ NEWS` 區塊消失
  - 修法：改為 `.order_by(summary_date.desc()).first()` 取最近一筆（昨天資料含「隔日方向注意」早上看最有用）
- ✅ 根因 B：`analyze_daily_news()` prompt 從未設計「建議」section → 三個預期區塊只有兩個
  - 修法：加第三個 `<h3>操作建議（依新聞評估）</h3>` section，max_tokens 600 → 800
  - 生效時機：今天 14:30 批次重跑後，新摘要才含第三個區塊

**2026-05-07 累積修復（昨日）：**
- Bug 1 & 2：財經新聞引用錯誤大盤數值（pubDate 48h 過濾 + TWII 注入）
- Bug 3：K線型態 AI 自行命名（`label_bars()` 程式標注 + 鐵律）
- Bug 4：列印 PDF 大量空白（移除 `.stock-block` page-break-inside: avoid）
- Bug 5：P&F 目標 AI 自行估算（`calc_pnf_target()` 等幅量度程式計算）

**本次（2026-05-07）進度 — 報表三大 Bug 修復 + PDF 空白 Bug 修復 + P&F 計算修正：**

**Bug 1 & 2（財經新聞引用錯誤大盤數值）**
- ✅ `data_fetcher.py`：`get_tw_news_rss()` 加 pubDate 48 小時過濾，排除舊文章混入（根因：無日期篩選導致 Google News 回傳歷史舊文，如「台股破3萬點」「大漲1778點」）
- ✅ `ai_analyzer_v2.py`：`analyze_daily_news()` 新增 `twii_price` / `twii_change_pct` 參數，注入 prompt 並加鐵律「若提及大盤點位必須使用此數值，嚴禁訓練資料歷史數值」
- ✅ `run_daily_report.py`：呼叫 `get_global_markets()` 取 TWII 今日收盤與漲跌幅，傳入 `analyze_daily_news()`

**Bug 3（K線型態 AI 自行命名錯誤）**
- ✅ `candlestick.py`：新增 `label_bars(bars) -> dict`，對每根 K 棒以數學公式計算型態標籤（`{date: 型態名稱}`），日K/週K/月K 三個時間框架均適用
- ✅ `ai_analyzer_v2.py`：`_fmt_bars()` 加 `pattern_labels` 參數，每根K棒後附加 `▶大陰線` 等程式計算標籤；`analyze_market_only()`、`analyze_stock_three_masters()`、`analyze_taiwan_market_v2()`、`analyze_weekly_taiwan_v2()` 全部套用
- ✅ 所有分析 prompt 加鐵律：「▶型態名稱 為程式精確計算，禁止更改，只解讀含意」
- ✅ 驗證：晶心科 2026/05/06 → `▶大陰線`（正確）、2026/05/07 → `▶陽線(11%)`（正確）

**Bug 4（列印 PDF 持股與分析之間大量空白）**
- ✅ `templates/print_report.html`：移除 `.stock-block` 的 `page-break-inside: avoid`
  - 根因：analysis-wrap 超過一頁時 Chrome 仍分頁，但先把整塊推到下一頁，前頁留下大整頁空白
  - 修法：對各子區塊個別控制 — `.stock-block-header` / `.data-row` / `.pills` 加 `break-inside: avoid` + `break-after: avoid`，讓 analysis 緊接 pills 自然展開；`.analysis-wrap table` 加 `break-inside: avoid` 防 K棒表格被切斷

**Bug 5（P&F 概念目標 AI 自行估算，無固定公式）**
- ✅ 根因：`TARGET_PNF:` 完全由 AI 自由輸出，每次結果不同，HTML span 與結構化標記可能不一致
- ✅ `candlestick.py`：新增 `calc_pnf_target(bars, lookback=12) -> float | None`，公式 = `base_high + (base_high - base_low)`（等幅量度），優先用週K（12根≈3個月），備援日K（20根）
- ✅ `ai_analyzer_v2.py`（`analyze_market_only` + `analyze_stock_three_masters`）：
  - 移除 `TARGET_PNF:` 結構化標記（不再需要 AI 輸出）
  - dynamic_block 注入程式計算值 + 鐵律「禁止更改」
  - result dict 直接用 `_pnf`，不再解析 AI 輸出
- ✅ 驗證：base_high=250, base_low=175 → 目標 325（與手算一致）
- 注意：**支撐壓力維持 AI 推斷**（從真實 OHLCV 推斷，非純幻想；支撐壓力本身主觀，AI 推斷可接受）

**先前未解（仍待）：**
- ⏳ 分享 PDF 寄送 timeout：`SSL/465: timed out`（Render → Gmail SMTP 不穩）
  - 決策：暫緩，改手動存 PDF 轉傳給親友
  - 已討論方案供日後參考：A. 換 Resend HTTP API（推薦） / B. Render Starter / C. 加 timeout

**下一步（按優先順序）：**
1. **驗證 K線特徵標注**：下次個股分析後，確認第二節 table「特徵」欄顯示程式計算值（如「放量·高位」），不再出現「看漲/看跌」；十字星解讀有帶位置語境
2. **驗證 AI 幻覺封鎖**：Render 部署 `e4bec98` 後，按「🗑 清快取」→ 等新聞重生 → 確認 NEWS 不再出現「1778點」「突破3萬點」
3. **驗證三山頂修正**：觀察原本天天顯示三山頂的個股，確認 15 根靜音機制生效
4. **驗證早晨之星/黃昏之星**：確認小陰+小實體+小陽不再誤觸發（需 3 根實體均 > 50% 振幅才觸發）
5. **驗證週末視窗**：週五 14:00 後按一鍵分析，確認按鈕顯示「含週報」、週報背景產生、PDF 顯示 §MARKET
6. **驗證量能門檻出現**：下次個股分析確認報表「等待條件」有具體張數（如「突破需 1,800 張」）
7. **驗證 P&F 目標合理性**：若顯示「—（尚未接近突破點）」代表修法生效
8. **K線型態歷史累積**：目前第一批資料已入 DB，待 1-2 個月後查看 return_3/5/10d 回填結果
9. 清理遺留
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
10. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
11. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB

## 費用速查

| 情境 | 月費 |
|------|------|
| 個人使用（1人 × 18支）| 約 US$15（NT$480）|
| 對外收費建議 | NT$300/人/月 |
| 打平門檻 | 5-6人（5人接近打平，6人開始盈餘）|

詳細估算見 `plan.md` 第零節（每日 ~$0.64、每週含週報 ~$3.40）。

## 專案基本資訊
- GitHub：`https://github.com/Jason690926/investment-system`（私人）
- 部署：Render `https://investment-system-lxq5.onrender.com`
- 資料庫：PostgreSQL via Supabase
- 本機路徑：`C:\Users\frodo.MSI\OneDrive\Desktop\investment-system`

---

## Claude Code 工具鏈（user scope，全域）

裝於 2026-05-12，跨專案可用：

- **ui-ux-pro-max** (skill)：UI/UX 設計庫查詢，50+ 風格、161 配色、57 字體配對、99 UX 準則、25 圖表類型，含 dark mode 獨立規則與對比度檢查。
  - **何時觸發**：改 `templates/*.html`、`static/css/*`、`static/js/dashboard.js` 視覺面 / 配色 / 字體 / 排版 / chart 時自動觸發
  - **成本**：核心是 local Python 查詢，0 token；後續套規格走我一般 token
  - **指令**：`python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system`
- **context7** (MCP server)：即時抓套件官方文件，補我訓練 cutoff (2025-08) 後的 API 變動。
  - **何時觸發**：問 Flask / SQLAlchemy / yfinance / anthropic SDK / mistune / SortableJS / html2pdf.js 等套件文件時自動觸發
  - **成本**：MCP call，0 token（不打 LLM）
  - **工具**：`mcp__plugin_context7_context7__resolve-library-id` + `query-docs`

**注意：**
- ui-ux-pro-max **不適用** AI prompt 調整、DB schema、K 線演算法、cache 邏輯這類非前端工作
- context7 **不適用** 重構、寫腳本、debug 業務邏輯、code review，僅限「套件文件查詢」
- 兩者互不衝突，可同時觸發（例：改前端時若用到新版 Tailwind class，先 context7 確認語法，再 ui-ux-pro-max 給設計建議）

---

## 修改 AI 功能的紀律（避免燒 token）

修改會呼叫 Claude API 的程式碼前（週報產生、個股分析、產業指標股、市場分析等），必須在本機**用 DB 既有的真實 raw 輸出**完整推演 cleanup / prompt / 渲染管道，確認修法在實際資料上會 work，再讓使用者重跑。

**Why：** 每次週報重跑燒 ~$0.20、每次個股全分析燒 ~$0.6+。一輪「推測 → push → 使用者重跑 → 還是壞 → 再推測」就燒掉 $0.40+。1 人月預算才 $15，反覆燒會明顯吃掉預算且使用者體驗差。

**How to apply（修 AI 相關 bug 必做）：**
1. **先撈 DB 既有壞掉的 raw 輸出**（如 `WeeklyReport.html_market`、`StockAnalysis.html_content`）看實際內容，**不要憑想像**
2. **本機跑 cleanup / 渲染 pipeline 在那份真實壞資料上**驗證，確認修法 work
3. **覆蓋多種失敗情境**：完整輸出、截斷輸出、未閉合標籤、markdown 包裝等都要測
4. 如果只能用 AI 重跑才能驗證（如 prompt 改動），明確告知使用者「這次修法是基於分析、不確定 AI 會否規矩遵守，請評估是否值得花 ~$X 重跑」
5. 不確定就用「prompt + cleanup 雙保險」（prompt 約束根本面、cleanup 防禦邊界）— 不要只改其中一個就 push

---

## 前端設計原則

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration. This project uses a dark theme — keep it dark and extend it with character.

Motion: Use animations for effects and micro-interactions. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context.
</frontend_aesthetics>
