# Plan：5/22 週報 10 bug 修法（6 commits TDD）

**對照 spec**：`docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md`
**對照 plan.md §**：二十九

---

## 執行順序

C1 是基石（資料層），其他互不依賴：C1 → C2 → C3 → C4 → C5 → C6 → 收工 commit

每 commit 走「先 test、commit；再 impl、commit」，避免修法後 test 寫回去就過。

---

## C1：data_enricher 合成進行中週/月棒（S1 + W1）

### 新增/改動點
- `modules/data_enricher.py` 新 helper `_synthesize_in_progress_bar(daily_df, period_df, freq: Literal['W','M']) -> pd.DataFrame`
- `get_full_stock_data` 抓 weekly/monthly 後呼叫 `_synthesize_in_progress_bar`，覆寫/append 進行中棒
- `_chart_json_to_df` 不動（保留 Bug A 邏輯）

### TDD
1. **t1（test commit）**：`tests/test_synthesize_in_progress_bar.py` 6 case
   - 當期 5 個交易日 → close = 最新日 close、high/low/volume 正確
   - 當期 1 個交易日 → 四價合 1
   - 跨月（5/30 + 6/2）→ 月只取 5/30、週取兩根
   - daily 末根 < 進行中起始 → 不合成（回 period_df 不變）
   - daily 空 → 不合成
   - period_df 末根 Date == 合成 Date → 覆寫；否則 append
2. **t2（impl commit）**：實作 helper + 接到 `get_full_stock_data`，跑全測試 208 + 6 全綠

---

## C2：_dual_pnf 統一 rounding + placeholder 注入成品（S2 + S4）

### 新增/改動點
- `modules/ai_analyzer_v2.py` 新 helper `_quantize_price(x: float) -> float`
- `_dual_pnf`（line 277-295）改：
  - quantize 後存回 `result['target_pnf']`
  - placeholder 注入完整成品句（含 `P&F概念目標：` 開頭、`元（等幅量度）` 結尾）
- prompt 模板（line 1138）改鐵律：「整句已由程式產生，verbatim 引用，禁止改寫或重複輸出」

### TDD
1. **t1（test commit）**：`tests/test_dual_pnf_quantize.py` 5 case
2. **t2（impl commit）**：實作 `_quantize_price` + 改 `_dual_pnf` + 改 prompt，跑全測試 + 5 全綠

---

## C3：週報 prompt 量能/區間/max_tokens（W2 + W3 + I2）

### 新增/改動點
- `modules/ai_analyzer_v2.py`：
  - `analyze_weekly_taiwan_v2`（line 1633~1693）：
    - 從 `weekly_bars[-5:]` 算 `week_5_avg_zhang`
    - 從 `weekly_bars[-1]` 取 `week_vol_zhang`、`week_close`
    - 從 `weekly_bars[-3:]` 算 `week_close_range`、`week_hl_range`
    - prompt 注入新欄位 + 鐵律「收盤/高低區間 label 不可混用」
  - `get_industry_indicator_stocks`（line 1628）：max_tokens 800 → 1500

### TDD
1. **t1（test commit）**：`tests/test_weekly_taiwan_prompt.py` 4 case
2. **t2（impl commit）**：改 prompt + max_tokens，跑全測試 + 4 全綠

---

## C4：_structure_block gate_hint 結構已轉弱禁多方（S5）

### 新增/改動點
- `modules/ai_analyzer_v2.py` `gate_hint` dict（line 566-569）：「結構已轉弱」value 加「禁標 積累/上漲/再積累」

### TDD
1. **t1（test commit）**：`tests/test_structure_gate_short.py` 2 case
   - `_structure_block(flag='結構已轉弱')` 輸出含「禁標 積累/上漲/再積累」
   - `_structure_block(flag='結構未轉弱')` 輸出不含此規則（既有規則保留）
2. **t2（impl commit）**：改 dict，跑全測試 + 2 全綠

---

## C5：觀察股第六節雙層防護（S3）

### 新增/改動點
- `modules/ai_analyzer_v2.py`：
  - 新 helper `_strip_section_six(html: str, is_holding: bool) -> str`
  - `analyze_market_only` 末尾呼叫 `_strip_section_six(html, is_holding)`
  - prompt（line 1174-1181）改鐵律強化「禁止輸出『六、』標題」

### TDD
1. **t1（test commit）**：`tests/test_strip_section_six.py` 4 case
2. **t2（impl commit）**：實作 helper + 改 prompt + 接到 `analyze_market_only`，跑全測試 + 4 全綠

---

## C6：dashboard.js 週末 NEWS regen + run_weekly_report DB fallback（I1）

### 新增/改動點
- `static/js/dashboard.js` line 315-321：週末視窗分支加 `/api/news/regenerate` 呼叫
- `run_weekly_report.py` line 107-117：RSS 空時 DB fallback
- `get_industry_indicator_stocks`：接收 `news_fallback_note` 並 prompt 注入告知

### TDD（拆兩 sub-commit，避免 dashboard.js + python 混改）
1. **t1（test commit）**：`tests/test_weekly_report_news_fallback.py` 3 case
2. **t2a（impl commit）**：`run_weekly_report.py` + `get_industry_indicator_stocks` fallback
3. **t2b（impl commit）**：`static/js/dashboard.js` 週末分支加 regen + `node -c` 驗證

---

## 收工 commit

- 更新 `CLAUDE.md` 當前進度快照（記 6 commit 範圍 + 驗收清單 + 沿用未驗）
- `git push origin/main`

---

## 風險控管

| 風險 | 緩解 |
|------|------|
| C1 合成邏輯與 yfinance 完整週/月聚合不符 | 對照真實 weekly_bars 已完成週的 OHLC 做 sanity 驗 |
| C5 post-process regex 誤砍（例如七、八節剛好不存在） | 寫 boundary test：第六節是最後一節時也要砍對 |
| C6 fallback 用到舊新聞讓 AI 誤導 | 強制注入「（新聞來源：YYYY-MM-DD DB 快取）」AI 須引用 |
| 6 commit push 後 Render auto-deploy 中斷 | 每 commit 自我封閉、無 DB migration，逐 commit revert 安全 |
