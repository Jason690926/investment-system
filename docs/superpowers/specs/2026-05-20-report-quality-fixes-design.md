# 設計：投資建議書 15 Bug 修法（PDF 報表全面對齊）

日期：2026-05-20
狀態：設計待用戶複審 → writing-plans
前置：spec 2026-05-19（波段框架）已實作至 commit `b710dac`

## 一、問題（用戶提供 2026-05-19 22:09 報表，15 支股，22 頁 PDF）

審視 PDF 後找出 15 個不符合常理 / 市場建議書規範的 bug，按嚴重度分組：

### 致命（會直接誤導用戶決策）
1. **持股部位處理建議缺位**：晶心科 -39.6% / 創惟 -18.6% 多單虧損中，分析卻全部給「等回測壓力放空」（建新空單），完全沒告訴用戶該停損出場/減碼/續抱。
2. **Pill 價位 ↔ 內文操作框架錯位（short 股普遍）**：晶心科 pill「空進 208 / 空停 227 / 空標 208」vs 內文「回測 227 放空 / 目標 208」，pill 把支撐標為「空進」、目標 = 進場 = 208 完全錯位。創惟、矽力、南亞科同類。
3. **K 棒重複 / 缺漏**：5 支股票（晶心科、創惟、矽力、南亞科、東捷）日 K 表最後兩根 OHLC 完全相同（同 5/19 列兩次）。技嘉日 K 只有 3 根，缺 5/13/5/14。
4. **撼訊三川底連 3 天觸發**：5/13/5/14/5/15 連續 3 根 K 都標「三川底（酒田）」，違反「整體型態只標最末根」慣例。
5. **華星光「平頭頂」名實不符**：5/18 high=551 / 5/19 high=550，1 元差被判平頭頂；500 元級別股票 tick=1.0 元，1 元 = 1 tick 不該算同高。

### 邏輯不嚴
6. **NEWS 操作建議 vs 個股結論方向相反**：NEWS 寫「跌深 AI、半導體可列入觀察布局」，但 15 支裡 12 支「等回測壓力放空」、0 支「跌深布局」。
7. **操作框架格式 15 支只有 5 支結構化**：晶心科等 10 支只給一句「等回測 X 放空」總結，沒結構化進場/停損/目標子標題。
8. **量能門檻語意倒置**：所有 short 股「等待條件」都寫「需量能達 X 張（突破門檻）」，把 `vol_5avg × 1.5`（向上突破量）套在「向下跌破」場景。
9. **撼訊 P&F target 74 < 壓力 74.7**：target 應 ≥ 壓力突破後 measured move；Filter B `target ≤ cur × 1.02` 沒擋下（74/67.5=1.097 通過），但 target 低於明文壓力線仍是常識違反。
10. **南亞科「4 月早晨之星」**：早晨之星是 3 根 K 棒型態，月線一個月 = 1 根，不可能單月構成。AI 把週/日線型態誤標到月線描述。
11. **矽力放量描述互打**：「努力大結果差」框架本指「上漲嘗試的買盤量大」，套到「下跌大量」場景變語意矛盾。
12. **創惟「放量失敗」字面矛盾**：「等待條件：回測 96~98 壓力帶放量 ≥ 3,021 張失敗，為放空確認」 — 「放量失敗」修飾對象不明。

### 排版/細節
13. **字型 fallback 半形/全形混用**：`--font-mono` 用 IBM Plex Mono（無 CJK glyph），中文字 fallback 撞到 CJK Radicals Supplement（「⼗」`U+2F17`、「⼤」`U+2F25`、「⽇」`U+2F25`）。
14. **缺月 K 明細表**：所有股票月 K 引用（「3 月放量 152K」「4 月跳空高開」）在內文出現但無對應表格，用戶無法檢核。
15. **缺 Personal 章節**：PDF 只有 NEWS + HOLDINGS + WATCHLIST 三段，沒對應 `generate_personal_recommendation` 輸出（dashboard 有渲染但 print_report 沒包）。

## 二、根因（exploration 已驗證）

| Bug | 程式定位 | 根因 |
|-----|---------|------|
| #1, #15 | `templates/print_report.html` 缺 personal 區塊；`generate_personal_recommendation` 無「方向衝突」模板 | print 模板沒包 personal；prompt 對「多單持有 + 派發分析」無專屬輸出 |
| #2 | `app.py:144-166` pill mapping | short 時只改 label 文字，未改價位 source — `support_price` 永遠是「支撐線」但 short label 標「空進」 |
| #3 | `modules/data_enricher.py`（待驗）+ `_fmt_bars` | daily_bars 可能在最新日重複 append；技嘉案例 yfinance 對該 ticker 部分日 NaN |
| #4 | `candlestick.py:545-588 label_bars` | 對 bars[4:] 每根 K 都呼叫 `detect_patterns`，多根組合型態（三川底等）會在 15 根 freshness 窗口內連續觸發 |
| #5 | `candlestick.py:343-345` | 平頭頂容差 `< 0.003`（0.3%），高價股太寬鬆 |
| #6 | `analyze_daily_news` | 獨立 AI call，看不到個股池方向分佈 |
| #7 | `analyze_stock_three_masters` prompt 第四段 | 「三宗師融合結論」沒強制 schema，AI 自行決定是否展開操作框架 |
| #8 | `_dynamic_block` 注入 `vol_breakout = vol_5avg × 1.5` | prompt 沒區分 long/short，AI 套到 short 跌破場景 |
| #9 | `candlestick.py:590-710 calc_pnf_target` | 找「最近窄箱」算 target，AI 寫「壓力 74.7」是看週 K high；兩來源無交叉檢查 |
| #10 | `candlestick.py:545-588 label_bars` | monthly_bars 同樣會觸發 3+ 根組合型態 |
| #11, #12 | `analyze_stock_three_masters` prompt | 量價術語沒方向 qualify；「放量失敗」未定義 |
| #13 | `templates/print_report.html:14-15` | `--font-mono: "IBM Plex Mono", "Consolas", monospace` 鏈缺中文 fallback |
| #14 | `_fmt_bars` | 只給日 K 5 根 + 週 K 3 根，無月 K 表 |

## 三、用戶拍板架構決策

### B1c：DB 加 `stop_loss` 一欄（pill 錯位修法路徑）
- 保留 `support_price` / `resistance_price` / `target_price` 永遠固定中性語意（箱底/箱頂/measured target）
- 新增 `stop_loss` 欄位，short 用、long 為 None
- 1 次 Supabase ALTER TABLE（零 downtime）；pill 讀寫分離乾淨

### Personal in PDF：全部包含（持股 + 觀察）
- HOLDINGS 區塊：個人建議含「持倉診斷」段（方向診斷 / 出場條件 / 續抱條件）
- WATCHLIST 區塊：個人建議含「進場判斷」段（與既有對齊）

## 四、修法設計（七 commit）

### Commit 1：D 組 — 型態誤判修法（純候選函式，無 AI 重跑）

`modules/candlestick.py`：

- **D1 多根組合型態去重**（fix #4）：`label_bars` 末層加 dedup — 若 `_MULTI_CANDLE[name] >= 3`（早晨/黃昏/三白/三黑/三川/三山/三空/三法）且該型態在前 `_MULTI_CANDLE[name]` 根內已標過，當前根 fallback 為「陽/陰線(體型%)」。
- **D2 平頭頂底改絕對 tick 容差**（fix #5）：複用 `app.py:_format_price` 的 TWSE 申報單位表，平頭頂判定改 `abs(h0 - h1) ≤ tick_size(h1)`。
- **D3 月 K skip 3+ 根組合型態**（fix #10）：`label_bars(bars, timeframe='monthly')` 加 timeframe 參數；monthly 時 `detect_patterns` 結果過濾掉 `_MULTI_CANDLE[name] >= 3` 的型態。

驗收：pytest 新增 D1/D2/D3 各 ≥ 3 case，全綠；既有 127 測試零退化。

### Commit 2：C 組 — K 棒重複/缺漏（fix #3）

`modules/data_enricher.py` + `modules/ai_analyzer_v2.py _fmt_bars`：

- **C1**：`_fmt_bars` 開頭 dedup by `date`（最小防禦）
- **C2**：`data_enricher.py` 拼接 daily_bars 時驗證最後一根 date 唯一；如同日 append 兩次則丟掉舊的
- **C3**：日 K < 5 根時 fallback 顯示「最近 N 根」而非寫死「最近 5 根」表頭

驗收：pytest 新增 fixture「同日重複 append」/「日 K 只有 3 根」case，斷言 dedup + label 正確。

### Commit 3：H 組 — 字型 fallback（fix #13）

`templates/print_report.html:15`：

```css
--font-mono: "IBM Plex Mono", "Noto Sans TC", "Microsoft JhengHei", "Consolas", monospace;
```

驗收：HTML 視覺檢查；無 pytest 影響。

### Commit 4：G 組 — calc_pnf_target Filter C + 月 K 表（fix #9, #14）

- **G1**：`calc_pnf_target` 加 Filter C — long 時 `target > swing_high × 1.02`、short 時 `target < swing_low × 0.98`（swing_high/low 從 `calc_swing_levels` 取），不符往更早箱體找
- **G2**：`_fmt_bars` 加 monthly_bars 最近 6 根 table（半年），讓用戶能驗證月線描述

驗收：pytest 新增「target < 壓力」reject case；報表 PDF 視覺包含月 K 表。

### Commit 5：B 組 — DB stop_loss + swing 注入 + pill mapping（fix #2，AI 重跑驗證點）

最大、最險的 commit。三件事：

1. **DB schema**：
   - `modules/models.py` 加 `stop_loss = db.Column(db.Numeric)` 到 `StockAnalysis`
   - Supabase ALTER TABLE 線上跑（手動，user 確認後執行）

2. **寫入路徑**：`analyze_stock_three_masters` + `analyze_market_only`
   - 改用 `calc_swing_levels` 鎖定值寫入 DB：
     - long: `support_price=swing.range_low`, `resistance_price=swing.range_high`, `target_price=swing.target`, `stop_loss=None`
     - short: `support_price=swing.range_low` (下方目標), `resistance_price=swing.range_high` (回測壓力), `target_price=swing.target` (P&F 下行目標), `stop_loss=swing.invalidation` (前高失效)
     - neutral: 全 None 或保留既有 AI tag
   - AI 仍寫 `SUPPORT/RESISTANCE/TARGET_PNF` tag（向後相容、prompt 可讀），但 DB 寫入以 swing 為準（AI tag fallback）

3. **pill mapping**：`app.py:144-166`
   - long: `撐 = support_price / 壓 = resistance_price / 目標 = target_price`
   - short: `空標 = support_price / 空進 = resistance_price / 空停 = stop_loss`
   - neutral: 維持現狀

驗收：
- pytest 既有 119 + 新 swing 8 全綠
- DB 8 筆既有 StockAnalysis raw 重渲染零 crash、long 股 pill 顯示與改前一致
- AI 重跑驗證：short 股 pill 空進/空停/空標價位邏輯通（空進在上、空停最高、空標最低）

### Commit 6：A 組 — print PDF 包含 Personal + 持倉診斷（fix #1, #15，AI 重跑驗證點）

1. **`templates/print_report.html`**：HOLDINGS 與 WATCHLIST 每支股 block 底部加 `<div class="personal-rec">`，從 query 取 `generate_personal_recommendation` 結果（`UserStockSetting.recommendation_html` 之類欄位，依現況 schema）

2. **`modules/ai_analyzer_v2.py generate_personal_recommendation`**：對 holding 加「方向衝突診斷」模板：
   - 若 `phase_to_direction(wyckoff_phase) == 'short'` 且用戶持有多單（`UserStock` 有 cost）：
     - **持倉診斷**：方向診斷（多單 vs 派發 → 標「方向衝突警示」）
     - **出場條件**：跌破 `swing.range_low` 立即減碼 / 反彈至 `swing.range_high` 全出
     - **續抱條件**：站穩 `swing.range_high × 1.02` 上方且量能 ≥ `vol_5avg × 1.5`

驗收：DB 取既有 holding case 跑新 prompt（dry-run）、PDF 包含 personal 段

### Commit 7：E + F 組 — Prompt schema 與術語（fix #6, #7, #8, #11, #12）

純 prompt 改動：

- **E1 NEWS 末段觀察池總覽**（fix #6）：`analyze_daily_news` 結尾加程式注入 `_pool_summary_block`（X 多 / Y 空 / Z 觀望），AI 末段加「您觀察池當前 X 多 / Y 空，與本日財經建議 [一致/分歧] 提醒」
- **E2 操作框架強制 schema**（fix #7）：`analyze_stock_three_masters` 第四段加強制「## 操作框架」+ 三 bullet「進場價 / 停損 / 目標」，使用 swing 鎖定值
- **F1 量能門檻方向感知**（fix #8）：`_dynamic_block` 依方向注入「突破量」/「跌破量」+「Spring 量」，prompt 術語表寫死
- **F2 量價術語方向 qualify**（fix #11）：prompt 加「多方努力 = 上漲日量」/「空方努力 = 下跌日量」術語
- **F3 禁「放量失敗」**（fix #12）：prompt 範例庫提供標準句型「縮量回測 → 反彈乏力 → 放空確認」

驗收：DB raw 推演（既有 8 筆）+ AI 重跑驗證

### Task 8：全局驗證（非 commit）

- 既有 127 測試 + 新增測試全綠
- `py_compile` 全綠
- DB 8 筆既有 raw 跑 `_clean_html_output` + 渲染 + pill mapping 零退化
- git diff 靜態證明關鍵函式（解析端、清理端）零改動

## 五、依賴序與風險

```
Commit 1 (D 組型態) ──┐
Commit 2 (C 組 K 棒) ─┼─→ Commit 4 (G 組 PnF Filter C, 用 swing_high)
Commit 3 (H 組字型) ──┘                  │
                                          ↓
                       Commit 5 (B 組 stop_loss + pill)
                                          ↓
                       Commit 6 (A 組 personal in PDF)
                                          ↓
                       Commit 7 (E + F 組 prompt schema)
                                          ↓
                       Task 8 (全局驗證)
```

- Commit 5 是分水嶺：DB schema 改 + pill mapping 改，回滾困難
- Commit 6/7 改 prompt，AI 不遵守則 revert commit 即可（無資料污染）
- Commit 1/2/3/4 純後端 + 模板 + 純候選函式，回滾零成本

## 六、AI 成本估算

- Commit 5 + 6 + 7 各需 ~$0.6 一鍵分析驗證（共 ~$1.8）
- Task 8 不需 AI（純 DB raw 重渲染）
- 若分批驗證可拉到 commit 5 + 6 + 7 一次驗（~$0.6 × 1）

## 七、回滾策略

| Commit | 回滾方法 |
|--------|---------|
| 1 (D) | revert，純候選函式無資料污染 |
| 2 (C) | revert，data_enricher 改動 |
| 3 (H) | revert，純 CSS |
| 4 (G) | revert，calc_pnf_target Filter C 加性 |
| 5 (B) | revert prompt + pill mapping；DB stop_loss 欄位保留為 NULL（向前相容） |
| 6 (A) | revert template + prompt 模板 |
| 7 (E+F) | revert，純 prompt |
