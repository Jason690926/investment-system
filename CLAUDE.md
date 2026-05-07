# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-08 收工）

**所在週次：週4（進行中）**

**狀態：HEAD = `b1eeaa2`（已 push origin/main）**

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
1. **觀察今日 14:30 批次**：確認財經新聞三個區塊（重大財經重點 + 隔日方向注意 + 操作建議）正確產生；早上開報表能看到昨日摘要
2. **K線型態歷史累積**：目前第一批資料已入 DB，待 1-2 個月後查看 return_3/5/10d 回填結果
3. 清理遺留
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
4. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
5. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB

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
