# Dashboard 尚未分析顯示上次分析 + 錨點 strip：設計

- 日期：2026-05-28
- 觸發：5/26 §三十二 8 commit 驗收完成後，brainstorming Opt-2/3 dashboard UX：
  - **Opt-2**：新交易日開盤後 14:30 前 mini-card 全部回到「尚未分析」灰色狀態，家人讀者無法掃過昨日決策 pill → 失去前一日操作參考
  - **Opt-3**：mini-card 缺關鍵價位（進場區 / 停損 / 目標），需點進個股詳情才能掃 → 14 檔逐一點開太慢
- 對應 plan：§三十三

---

## 一、問題陳述

### Opt-2 — 「尚未分析」狀態無前一日決策參考

`stock_service.get_user_stocks()` line 31-44 只取 `analysis_date == analysis_day_tw()` 的 cache：

```python
analysis_day = _analysis_day_tw()  # 14:30 前=昨日；14:30 後=今日
rows = db.query(StockAnalysis).filter(
    StockAnalysis.symbol.in_(symbols),
    StockAnalysis.analysis_type == 'daily',
    StockAnalysis.analysis_date == analysis_day,
    ...
)
```

家人讀者使用情境：
- 早上 09:00 開盤前打開 dashboard → 看持股要不要追加 / 停損
- `_analysis_day_tw()` 已切到今日 5/27（前一交易日 5/26 已過 14:30）
- 但今日 09:00 還沒人按「一鍵分析」 → `analyses = {}` → 14 檔全部「尚未分析」灰色
- **前一日 5/26 的分析仍在 DB**，但被 `analysis_date == 今日` 篩掉
- 家人讀者失去「5/26 我們對矽力的判斷是『🟢 進場區可佈』」這個前一日決策

### Opt-3 — mini-card 無關鍵價位

現有 mini-card 顯示：方向 chip / wyckoff phase / RISK / action pill / 4 OHLC / 20 日 K — **零價位錨點**。

家人讀者要知道「矽力現價 618 是否在進場區內」必須：
1. 點進個股詳情頁
2. 等 html_content 載入
3. 翻到第五節「操作框架」讀「進場區：442.32 ~ 456.00」

14 檔逐一點開過長。

---

## 二、設計原則

### 原則 1：「尚未分析」沿用前一日決策但視覺明確區分

對家人讀者：前一日決策 > 無資訊。Stale 但明確標示 > 強制空白。

視覺對比：
- **今日已分析**：4 chip 正常色彩（dirChip + wyckoff + RISK + actionPill）
- **沿用前一日**：4 chip + opacity 60% 變淺 + 加「上次 5/25」tag chip

### 原則 2：錨點 strip 跟方向 pill 同源 + 同步翻轉

dashboard 既有 pill 邏輯依 `phase_to_direction(wyckoff)` 翻轉：
- long: 撐 / 壓 / 目標
- short: 空進 / 空停 / 空標
- neutral: 區間 / 雙向

錨點 strip 對齊同一套翻轉，避免「pill 標 short 但 strip 標『撐 X』」概念矛盾。

### 原則 3：進場區用精確區間（加 column），其他價位用既有 column

「進場區 X-Y」是 swing_levels['entry_zone']（tuple），現有 DB 無欄位 → 加 2 個 column（`entry_low` / `entry_high`）。

`stop_loss` / `target_price` / `support_price` / `resistance_price` 全部既有，直接讀。

### 原則 4：14 天 lookback + 失效 fallback = 完全空白

涵蓋週末 + 連假 + 短期休市；超過 14 天無分析（新加入觀察 / 長期停權）→ 完全空白（無 chip、無 strip），與「新股」狀態一致避免「14 天前資料」誤導。

### 原則 5：純加性，避免影響既有「今日已分析」路徑

`stock_service.get_user_stocks()` 主查詢不動；fallback 只對「主查詢沒命中」的 symbols 執行。`is_today_analysis` 旗標讓前端決定樣式。

---

## 三、影響範圍

### 後端
- `migrations/2026-05-28-add-entry-zone-columns.sql`（新檔）：StockAnalysis 加 `entry_low` / `entry_high` Numeric(10, 2) nullable
- `modules/models.py`：StockAnalysis class 加 2 個 Column
- `modules/ai_analyzer_v2.py`：`analyze_stock_three_masters` / `analyze_market_only` 寫入 result dict 時，把 `swing_levels['entry_zone']` 拆寫到 `entry_low` / `entry_high`
- `modules/stock_service.py`：`get_user_stocks` 加 14-day fallback 查詢 + item dict 新欄位

### 前端
- `static/js/dashboard.js`：
  - `buildCard` 加 `card-stale-data` class（is_today_analysis=false）
  - 加 `last-analysis-tag` chip（顯示「上次 5/25」）
  - 加 `renderAnchorStrip(s)` helper（依 direction 翻轉 label）
  - `markCardAnalyzed` 觸發時移除 `card-stale-data` class 與 `last-analysis-tag`
- `static/css/app.css`：3 個新 class（`.card-stale-data` / `.last-analysis-tag` / `.card-anchor-strip`）

### 測試
- `tests/test_stock_service_fallback.py`（新檔）：
  - 主查詢命中 → 不觸發 fallback（`is_today_analysis=true`）
  - 主查詢未命中 + 14 天內有分析 → fallback 命中（`is_today_analysis=false`、`last_analysis_date` 正確）
  - 14 天 lookback 邊界（14 天前 = 命中、15 天前 = 不命中）
  - 多 symbol 混合（part 今日 / part 昨日 / part 無）
- 既有測試不退化

### 不動
- `models.py` 主分析欄位（既有 support/resistance/target/stop_loss 仍用）
- `_render_operation_framework`（讀 swing_levels 不變）
- 「14:30 前 = 昨日」`_analysis_day_tw()` 邏輯（沿用）
- DB unique constraint（沿用 symbol+date+type）

---

## 四、修法設計

### F1 — Migration：StockAnalysis 加 entry_low / entry_high

```sql
-- migrations/2026-05-28-add-entry-zone-columns.sql
ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS entry_low NUMERIC(10, 2);
ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS entry_high NUMERIC(10, 2);
```

零 downtime；既有 row entry_low/high = NULL；前端 fallback 顯示「—」。

### F2 — `models.py`：對應 ORM Column

```python
class StockAnalysis(Base):
    ...
    stop_loss       = Column(Numeric(10, 2))
    entry_low       = Column(Numeric(10, 2))   # 新：進場區下緣
    entry_high      = Column(Numeric(10, 2))   # 新：進場區上緣
    action_pill     = Column(String(32))
    ...
```

### F3 — `ai_analyzer_v2.py`：寫入端

兩個分析函式（`analyze_stock_three_masters` / `analyze_market_only`）算完 `swing_levels` 後：

```python
ez = swing_levels.get('entry_zone') if swing_levels else None
result['entry_low']  = float(ez[0]) if ez else None
result['entry_high'] = float(ez[1]) if ez else None
```

呼叫端（`app.py /api/analyze` / `run_daily_report.py`）已用 `result.get(...)` 寫入 `StockAnalysis` row，新加 2 個欄位自動帶入。

### F4 — `stock_service.get_user_stocks`：14-day fallback

```python
from datetime import timedelta

def get_user_stocks(db: Session, user_id: int) -> list:
    stocks = (db.query(Stock).filter_by(user_id=user_id).order_by(...).all())
    analysis_day = _analysis_day_tw()
    symbols = [s.symbol for s in stocks]

    # 主查詢：今日（沿用）
    analyses = {}
    if symbols:
        rows = (db.query(StockAnalysis).filter(
            StockAnalysis.symbol.in_(symbols),
            StockAnalysis.analysis_type == 'daily',
            StockAnalysis.analysis_date == analysis_day,
            StockAnalysis.html_content.isnot(None),
        ).all())
        analyses = {r.symbol: r for r in rows}

    # Fallback：14 天內最近一筆（只對主查詢未命中的 symbol）
    missing = [sym for sym in symbols if sym not in analyses]
    fallback_analyses = {}
    if missing:
        cutoff = analysis_day - timedelta(days=14)
        rows = (db.query(StockAnalysis).filter(
            StockAnalysis.symbol.in_(missing),
            StockAnalysis.analysis_type == 'daily',
            StockAnalysis.analysis_date >= cutoff,
            StockAnalysis.analysis_date < analysis_day,
            StockAnalysis.html_content.isnot(None),
        ).order_by(StockAnalysis.symbol, StockAnalysis.analysis_date.desc()).all())
        # 每 symbol 取最近一筆（first wins，因為 order by date DESC）
        for r in rows:
            if r.symbol not in fallback_analyses:
                fallback_analyses[r.symbol] = r

    # 組 result
    result = []
    for s in stocks:
        item = {'id': s.id, 'symbol': s.symbol, 'name': s.name, 'status': s.status}
        analysis = analyses.get(s.symbol)
        fallback = fallback_analyses.get(s.symbol)
        a = analysis or fallback
        if a:
            item['risk_pct']      = a.risk_pct
            item['wyckoff_phase'] = a.wyckoff_phase
            item['action_pill']   = a.action_pill
            item['support']       = float(a.support_price) if a.support_price else None
            item['resistance']    = float(a.resistance_price) if a.resistance_price else None
            item['target_pnf']    = float(a.target_price) if a.target_price else None
            item['stop_loss']     = float(a.stop_loss) if a.stop_loss else None
            item['entry_low']     = float(a.entry_low) if a.entry_low else None
            item['entry_high']    = float(a.entry_high) if a.entry_high else None
            item['is_today_analysis'] = (analysis is not None)
            item['last_analysis_date'] = a.analysis_date.isoformat()
        # ... holding 資訊沿用
        result.append(item)
    return result
```

關鍵設計：
- Fallback 查詢只跑一次（撈所有 missing symbols 14 天內）；`order_by date DESC` + 「first wins」邏輯每 symbol 取最近一筆
- 主查詢命中 → `is_today_analysis=True`；fallback 命中 → `False`；都沒 → 兩欄都沒 key（前端 `??` 兜底）
- `analysis_date < analysis_day` 邊界：嚴格小於（避免主查詢已找過今日仍重撈）

### F5 — `dashboard.js buildCard`：stale 視覺 + 錨點 strip

```js
function buildCard(s) {
  const isToday = s.is_today_analysis !== false;  // true / undefined → 今日；false → stale
  const isAnalyzed = s.risk_pct != null;
  const cardClasses = `stock-card${isAnalyzed ? ' analyzed' : ''}${!isToday && isAnalyzed ? ' card-stale-data' : ''}`;

  // ... 既有 dirChip / wyckoffChip / riskChip / actionChip

  // 新：上次分析 tag chip（stale 才顯示）
  const lastTag = (!isToday && s.last_analysis_date)
    ? `<span class="last-analysis-tag" title="上次分析日">上次 ${formatLastDate(s.last_analysis_date)}</span>`
    : '';

  const statusRowHtml = (dirChip || wyckoffChip || riskChip || actionChip || lastTag)
    ? `<div class="card-status-row">${dirChip}${wyckoffChip}${riskChip}${actionChip}${lastTag}</div>`
    : '';

  // 新：錨點 strip
  const anchorStripHtml = renderAnchorStrip(s);

  return `<div class="${cardClasses}" data-stock-id="${s.id}" onclick="openStockPage(${s.id})">
    <div class="card-row1">...</div>
    ${statusRowHtml}
    ${anchorStripHtml}
    <div class="card-spark-wrap">...</div>
    ...
  </div>`;
}

function formatLastDate(iso) {
  // '2026-05-25' → '5/25'
  const [, mm, dd] = iso.split('-');
  return `${parseInt(mm, 10)}/${parseInt(dd, 10)}`;
}

function renderAnchorStrip(s) {
  // 都沒分析資料（連 fallback 都沒） → 不顯示
  if (s.risk_pct == null && !s.wyckoff_phase) return '';

  const dir = s.wyckoff_phase ? phaseDirection(s.wyckoff_phase)?.t : null;
  const fmt = (v) => (v != null ? `${v}` : '—');
  let html = '';

  if (dir === '空') {
    // short: 空進(entry_high) / 空停(stop_loss) / 空標(target_pnf)
    html = `空進 ${fmt(s.entry_high)} <span class="anchor-sep">|</span> 空停 ${fmt(s.stop_loss)} <span class="anchor-sep">|</span> 空標 ${fmt(s.target_pnf)}`;
  } else if (dir === '多') {
    // long: 進(entry_low-entry_high) / 停(stop_loss 或 entry_low) / 標(target_pnf)
    const entry = (s.entry_low != null && s.entry_high != null)
      ? `${s.entry_low}-${s.entry_high}`
      : '—';
    const stop = s.stop_loss != null ? s.stop_loss : (s.entry_low != null ? s.entry_low : '—');
    html = `進 ${entry} <span class="anchor-sep">|</span> 停 ${fmt(stop)} <span class="anchor-sep">|</span> 標 ${fmt(s.target_pnf)}`;
  } else {
    // neutral: 區間 + 雙向標示
    const range = (s.support != null && s.resistance != null)
      ? `${s.support}-${s.resistance}`
      : '—';
    html = `區間 ${range} <span class="anchor-sep">|</span> 雙向`;
  }

  return `<div class="card-anchor-strip">${html}</div>`;
}
```

`markCardAnalyzed` 同步調整：今日分析完成觸發時移除 `card-stale-data` class + 移除 `last-analysis-tag` chip + 重渲染錨點 strip（避免「分析完仍灰」UX 卡 bug）。

### F6 — `app.css`：3 個新 class

```css
/* Stale data 視覺（昨日 / 14 天內 fallback）*/
.stock-card.card-stale-data .card-status-row,
.stock-card.card-stale-data .card-anchor-strip,
.stock-card.card-stale-data .card-spark-wrap,
.stock-card.card-stale-data .card-ohlc {
  opacity: 0.6;
}

/* 「上次 5/25」tag chip — 沿用既有 chip 設計風格 */
.last-analysis-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--muted);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-feature-settings: 'tnum' on;
}

/* 錨點 strip — 一行精簡顯示 */
.card-anchor-strip {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 8px;
  margin: 6px 0;
  font-size: 12px;
  color: var(--fg);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-feature-settings: 'tnum' on;
  gap: 4px;
}

.card-anchor-strip .anchor-sep {
  color: var(--muted);
  margin: 0 4px;
}
```

---

## 五、為什麼這樣設計

### 1. 加 entry_low / entry_high column 而非「沿用 support 單值」
原 brainstorming 議定「零 migration」，但用戶確認「進場區精確區間」優先 → 接受 1 migration。理由：
- support_price 對 long 場景 ≈ entry_zone 下緣，但 short 場景「空進」是 resistance，概念不一致
- 從 html_content 解析脆弱（AI 文案漂移即壞）
- 1 migration 換取「精確且 direction-aware」的 strip，成本可控

### 2. 14-day fallback 而非「無限制 fallback」
週末（5 天）+ 連假（最多 6 天）+ 系統暫停 1-2 天 < 14 天。超過 14 天通常代表：
- 該股已長期停權
- 用戶新加入觀察但未跑分析
- 系統故障未察覺

任一情況下「14 天前資料」都不應作為決策參考 → 寧可空白也別誤導。

### 3. 主查詢 + missing fallback 而非「一次查 14 天」
單一查詢「`>= analysis_day - 14`」會多撈不必要的舊資料（已有今日資料的 symbol 仍會撈到 14 天紀錄）。兩階段查詢：
- 主查詢命中率高（一鍵分析後 ≈100%）→ 大部分 case fallback 不執行
- Fallback 只跑 missing 子集 → DB 載入量最小

### 4. `is_today_analysis=False` 而非 `is_stale=True`
正向命名（is_today）比反向命名（is_stale）更清楚；undefined fallback 為「今日已分析」邏輯與既有行為一致（避免新欄位破壞舊測試）。

### 5. 錨點 strip stale 視覺一致沿用 opacity 60%
不另設「stale strip 樣式」減維護成本；opacity 60% 已足以視覺區分今日 vs 過往。

### 6. `formatLastDate('2026-05-25') → '5/25'`
家人讀者熟悉「5/25」而非「2026-05-25」全日期；省卡片空間。

### 7. neutral 顯示「區間 X-Y | 雙向」而非完整 long/short 並陳
家人讀者不熟「neutral 雙向操作」框架；提示「雙向」促使點進詳情看完整論點，比一行擠 6 個價位易讀。

---

## 六、驗收

### Pytest（本機可驗）
- `tests/test_stock_service_fallback.py` 預計 5 case 全綠
- 既有 291 case 不退化

### Deploy + 不重跑（migration only，零 token 成本）
1. 跑 `migrations/2026-05-28-add-entry-zone-columns.sql`（Supabase Web SQL Editor）
2. Render auto-deploy → 開 dashboard
3. 開盤前場景（09:00 TW）：14 檔 mini-card 應全部顯示**淺灰 60% + 4 chip + 「上次 5/26」tag + 錨點 strip**（沿用前一日資料）

### Deploy + 重跑 ~$0.6（驗 entry_low/high 寫入）
4. 按一鍵分析 → 14 檔分析完成
5. 卡片 stale 樣式移除（正常色彩）+ tag 消失
6. 錨點 strip 顯示新分析錨點：
   - long 股（如矽力）：「進 442.3-456.0 | 停 224.5 | 標 728.5」
   - short 股（如撼訊）：「空進 73.7 | 空停 76.0 | 空標 62.0」
   - neutral 股（如華擎）：「區間 X-Y | 雙向」

---

## 七、回滾

純加性 + 1 migration（IF NOT EXISTS 安全）：

- F1 migration 出問題 → 不影響既有功能（NULL column）
- F2/F3 寫入端 → 既有 row entry_low/high = NULL，前端 strip 顯示「—」不 crash
- F4 fallback 邏輯 → `git revert` 即回到「主查詢 only」
- F5/F6 前端視覺 → `git revert` 卡片回原樣

最壞情況：fallback 查詢效能不佳 → 加 index `(symbol, analysis_date DESC)` 或關閉 fallback（單行條件）。

---

## 八、Spec 文件

- spec：`docs/superpowers/specs/2026-05-28-dashboard-stale-anchor-design.md`（本檔）
- plan：`docs/superpowers/plans/2026-05-28-dashboard-stale-anchor.md`（下一步寫）
