# Spec：5/22 週報 cross-check 10 bug 修法

**日期**：2026-05-24
**對照 plan.md**：§二十九
**對照 PDF**：5/22 20:35 持股分析報告（27頁、14股）

---

## 一、診斷已查證根因（從 PDF 反推）

| Bug | 根因檔案：行 | 證據 |
|-----|--------------|------|
| S1 | `modules/data_enricher.py:19-56, 340-377` | 全 14 檔 K 表：日K[-1].close ≠ 週K[-1].close = 月K[-1].close = 前一交易日日 close。 |
| W1 | `modules/ai_analyzer_v2.py:1637, 1647-1648, 1653` | `price` = `daily['Close'].iloc[-1]` = 42267；weekly_bars[-1].close = 41368（受 S1 影響）；prompt 兩源並陳。 |
| I1 | `static/js/dashboard.js:315-321` + `run_weekly_report.py:107-117` | 週末視窗只觸發 `/api/weekly-report/generate`，沒呼叫 `/api/news/regenerate`。 |
| S2 | `modules/ai_analyzer_v2.py:287` + `run_daily_report.py:130, 138` | AI 看到 `:.0f` = 74；DB 存 float 73.7。 |
| S3 | `modules/ai_analyzer_v2.py:997-1001, 1174-1181` | 純 prompt gate，無 post-process safety net。 |
| S4 | `modules/ai_analyzer_v2.py:277-295, 1138, 194-246` | placeholder 含 label 字串，AI 把 label 整段當 [數值] 代入。 |
| I2 | `modules/ai_analyzer_v2.py:1628` | `max_tokens=800` 過小。 |
| W2 | `modules/ai_analyzer_v2.py:1642-1643, 1656` + `modules/data_enricher.py:362-363` | 注入 `vol`/`vol5` 是日量/日均，label 卻叫「本週末量」。 |
| W3 | `modules/ai_analyzer_v2.py:1647, 1650-1693` | prompt 無「收盤區間/高低區間」欄位，AI 自由命名。 |
| S5 | `modules/ai_analyzer_v2.py:566-569` | gate_hint「結構已轉弱」沒禁標多方相位。 |

---

## 二、修法設計

### C1：S1 + W1 — `data_enricher` 合成進行中週/月棒

**設計核心**：
1. `_chart_json_to_df`（line 19-56）保留 Bug A 的 spurious 剔除邏輯不動。
2. 在 `get_full_stock_data`（line 340-377）抓 daily/weekly/monthly 後，加 `_synthesize_in_progress_bar(daily_df, weekly_df, 'W')` 與 `(daily_df, monthly_df, 'M')`：
   - 取 daily_df 中「本週/本月起始日」之後的所有 bars
   - 若有 ≥1 根，合成：`open=當期第一日 open, high=max(highs), low=min(lows), close=最新日 close, volume=sum(volumes)`
   - 合成棒的 `Date` = 本週週一 / 本月 1 日
   - 若 weekly_df / monthly_df 末根 `Date` 已等於合成棒 Date → 覆寫；否則 append
3. 邊界處理：
   - 當期無 daily bars（連假期）→ 不合成（weekly/monthly_df 維持原樣）
   - daily_df 為空 → 不合成
   - 本週開始日：用 `pd.Timestamp.now(tz='Asia/Taipei').normalize() - pd.Timedelta(days=weekday)` 算

**對 W1 的連鎖效應**：S1 修好後 `weekly_bars[-1].close` = 42267.97 = `price`，prompt 兩源自動對齊。不額外動 prompt。

**測試**（≥6 case）：
1. 當期 5 個交易日 daily → 合成週 close = 最新日 close
2. 當期 1 個交易日 daily → 合成週 close/high/low/open 全 = 該日
3. 當期跨月（5/30 週五 + 6/2 週一）→ 月只合成 5/30 一根，週合成兩根
4. daily 末根日期 < 進行中週起始 → 不合成
5. daily 為空 → weekly/monthly 不變
6. 合成棒覆寫 vs append 分支

---

### C2：S2 + S4 — `_dual_pnf` 統一 rounding + placeholder 注入成品

**設計核心**：
1. 新 helper `_quantize_price(x)`：`<100 → round(x, 1); ≥100 → round(x, 0)`（對齊 TWSE tick）
2. `_dual_pnf`（line 277-295）：
   - `pnf_long_q = _quantize_price(pnf_long)` if pnf_long else None
   - 同樣 `pnf_short_q`
   - **同步寫回**：`result['target_pnf'] = pnf_long_q`（pill 來源用同值）
   - **prompt placeholder 改注入完整成品句**：
     - long 有值：`【P&F等幅量度·多方】P&F概念目標：73.7元（等幅量度）`
     - long 無值：`【P&F等幅量度·多方】P&F概念目標：—（尚未接近突破點）`
3. prompt 模板（line 1138）：移除「⚠️ P&F概念目標已由程式...格式：[數值]元」整段，改成「⚠️【P&F等幅量度·多方/空方】整句已由程式產生，第四節結論請完整 verbatim 引用，禁止改寫或重複輸出」

**測試**（≥5 case）：
1. `_quantize_price(73.7) == 73.7`, `_quantize_price(74.0) == 74`, `_quantize_price(105.5) == 106`
2. `_dual_pnf` 注入內容無「P&F概念目標：[數值]元」格式語
3. `_dual_pnf` 注入內容含完整成品句「P&F概念目標：73.7元（等幅量度）」
4. `result['target_pnf']` = `_quantize_price(pnf_long)`
5. pnf=None 時注入「—（尚未接近突破點）」

---

### C3：W2 + W3 + I2 — 週報 prompt 量能/區間/max_tokens

**設計核心**：
1. `analyze_weekly_taiwan_v2`（line 1633~1693）：
   - 從 `twii_enriched['weekly_bars']` 拿最後 1 根算 `week_vol_zhang`、最後 5 根算 `week_5_avg_zhang`
   - 從 weekly_bars[-3:] 算 `week_close_range = (min(close), max(close))`、`week_hl_range = (min(low), max(high))`
   - prompt 注入新欄位（取代舊 `vol`/`vol5`）：
     ```
     本週週量：{week_vol_zhang} 張 ｜ 近 5 週均量：{week_5_avg_zhang} 張
     近 3 週收盤區間：{week_close_range[0]}~{week_close_range[1]} 點
     近 3 週高低區間：{week_hl_range[0]}~{week_hl_range[1]} 點
     ```
   - prompt 鐵律加：「『收盤區間』與『高低區間』為不同概念；引用須使用程式注入 label 不可混用」
2. `get_industry_indicator_stocks`（line 1628）：`max_tokens=800 → 1500`

**測試**（≥4 case）：
1. weekly_bars 3 根時 week_close_range 計算正確
2. prompt 字串含「本週週量」「近 5 週均量」「近 3 週收盤區間」「近 3 週高低區間」
3. prompt 字串不含舊 label「本週末量」
4. `get_industry_indicator_stocks` max_tokens 參數 = 1500

---

### C4：S5 — `_structure_block` gate_hint 結構已轉弱禁標多方

**設計核心**：
`gate_hint`（line 566-569）：
```python
'結構已轉弱': '→ 相位限定 派發/再派發/下跌/不明，禁標 積累/上漲/再積累（已轉弱 + 多方相位語意衝突）',
```

**測試**（≥2 case）：
1. `_structure_block(flag='結構已轉弱')` 輸出含「禁標 積累/上漲/再積累」
2. `_structure_block(flag='結構未轉弱')` 輸出不含此規則（既有規則保留）

---

### C5：S3 — 觀察股第六節雙層防護

**設計核心**：
1. prompt（line 1174-1181）改寫：
   - **舊**：「（僅當 dynamic_block 出現【持倉提示】時輸出，否則整節跳過）」
   - **新**：「⚠️ 鐵律：若 dynamic_block 無【持倉提示】，**禁止輸出『六、』標題與其後任何內容**，第五節結束即完整結束。」
2. 新 helper `_strip_section_six(html: str, is_holding: bool) -> str`：
   - `is_holding=True` → 原樣回傳
   - `is_holding=False` → regex `r'###?\s*六、.*?(?=###?\s*[七八九]|$)'` （DOTALL）砍掉 + log warning「AI 違規輸出第六節，已 post-process 砍除」
3. `analyze_market_only`（line ~1190）末尾返回前呼叫 `_strip_section_six(html, is_holding)`

**測試**（≥4 case）：
1. `is_holding=True` 含「### 六、持倉部位建議\n...」→ 保留
2. `is_holding=False` 含「### 六、持倉部位建議\n...內容...」→ 砍除
3. `is_holding=False` 含「### 六、...\n### 七、...」→ 砍六留七（邊界）
4. `is_holding=False` 含瑞軒 literal「（本次 dynamic_block 未出現【持倉提示】，本節跳過）」→ 砍除

---

### C6：I1 — 週末 NEWS regen + DB fallback

**設計核心**：
1. `dashboard.js:315-321` 週末分支：
   ```js
   if (isWeeklyWindow()) {
     // 新增：與日報路徑對稱，週末也觸發 NEWS regen
     newsPromise = api('/api/news/regenerate', { method: 'POST' });
     try {
       await api('/api/weekly-report/generate', { method: 'POST' });
       toast('週末視窗：週報背景產生中（約 1-2 分鐘）');
     } catch (e) { ... }
   } else { ... 既有日報邏輯 ... }
   ```
2. `run_weekly_report.py:107-117` RSS 抓空時降級：
   ```python
   news = get_tw_news_rss(n=15)
   if not news:
       # DB fallback：撈最近一筆 DailyMarketSummary（可能 1-2 天前）
       latest = db.query(DailyMarketSummary).order_by(
           DailyMarketSummary.summary_date.desc()
       ).first()
       if latest and latest.news_json:
           news = json.loads(latest.news_json)
           news_fallback_note = f'（新聞來源：{latest.summary_date} DB 快取）'
       else:
           news_fallback_note = '（RSS 故障且 DB 無近期新聞，本次推斷）'
   else:
       news_fallback_note = None
   ```
3. `get_industry_indicator_stocks` 接收 `news_fallback_note` 並在 prompt 開頭注入告知 AI 標明來源。

**測試**（≥3 case）：
1. dashboard.js 週末分支字串含 `'/api/news/regenerate'`（node -c syntax + grep 驗）
2. `run_weekly_report.py` RSS 空 + DB 有最近一筆 → 用 DB 並設 `news_fallback_note`
3. `run_weekly_report.py` RSS 空 + DB 無 → news=[] 且設 fallback_note

---

## 三、回滾策略

每 commit 純加性 / 加性 helper / prompt 改寫，無 DB migration。任一 commit 有問題 `git revert` 對應 commit。

- C1 風險最大（影響全 14 檔報表所有 K 表）→ 額外做真實 yfinance API 對照測（合成棒 high/low 是否符合 yfinance 完整週/月聚合的事後值）
- C2~C5 純 ai_analyzer_v2，獨立可 revert
- C6 跨檔（dashboard.js + run_weekly_report.py），分兩 sub-commit

---

## 四、驗收清單（deploy 後燒 ~$0.6 重跑 5/22 報表）

1. ✅ 每股進行中週/月 close = 當日日 close（晶心科週/月 close 240，非 230）
2. ✅ 大盤週報「本週收盤」與週 OHLC 一致、量能 label 寫「本週週量」非「本週末量」
3. ✅ 大盤週報出現「近 3 週收盤區間」「近 3 週高低區間」分明
4. ✅ INDUSTRY 區出現真實新聞，或 DB fallback 標示 `（新聞來源：YYYY-MM-DD DB 快取）`
5. ✅ INDUSTRY 區無句尾截斷
6. ✅ 觀察股零洩漏第六節（12 檔全部）
7. ✅ 撼訊 pill「目標 73.7」與內文「73.7 元」一致
8. ✅ 矽力/南亞科/華星光 P&F 段無重複/巢狀
9. ✅ 撼訊結構旗標「結構已轉弱」時 phase 不會標「再積累」（應改標 派發/不明）
