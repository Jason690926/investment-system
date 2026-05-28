# Dashboard 尚未分析顯示上次分析 + 錨點 strip：實作計畫

> **For agentic workers:** 逐 Task 執行，每 Task 走 TDD（紅→綠→commit）。前端無 unit test，標示「人工 visual 驗收」。

**Goal:** 解決 Opt-2/3 dashboard UX 兩件事：
- Opt-2：早上 09:00 開盤前，14 檔 mini-card 不再全部回到「尚未分析」灰色狀態，而是沿用前一日決策 4 chip + 「上次 5/26」tag + opacity 60% stale 視覺
- Opt-3：mini-card 加錨點 strip（依方向動態切換 long/short/neutral label），免點進詳情即可掃過關鍵價位

**Architecture:**
- 後端：`StockAnalysis` 加 `entry_low` / `entry_high` 兩 Numeric column；`ai_analyzer_v2` 寫入端把 `swing_levels['entry_zone']` 拆寫到新欄位；`stock_service.get_user_stocks` 加 14-day fallback 查詢
- 前端：`dashboard.js buildCard` 加 `card-stale-data` class、`last-analysis-tag` chip、`renderAnchorStrip` direction-aware helper；`app.css` 3 新 class
- DB：1 migration（IF NOT EXISTS 安全），Supabase Web SQL Editor 路徑（CLAUDE.md §三十一 驗證過）

**Tech Stack:** Python / pytest / vanilla JS / CSS；spec：`docs/superpowers/specs/2026-05-28-dashboard-stale-anchor-design.md`

---

## ⚠️ Deploy 順序（用戶必讀）

本 plan 包含 schema 變動，**不可** push commits 後才跑 migration（會踩 §三十一 同樣的 `UndefinedColumn` 500 坑）。

**正確順序：**
1. 寫好全部 6 commits（F1–F6）但**先不 push**
2. 用戶在 Supabase Web SQL Editor 跑 `migrations/2026-05-28-add-entry-zone-columns.sql`
3. 確認 column 加好 (`\d stock_analyses` 看到 entry_low / entry_high）
4. `git push origin main` → Render auto-deploy
5. 重 deploy 後 dashboard 驗收（無重跑、零 token）→ stale 視覺生效
6. 燒 ~$0.6 按「一鍵分析」→ 驗 entry_low/high 寫入 + strip 顯示新錨點

---

## F1 — Migration SQL + models.py

### Task 1：加新 column

**Files:**
- Create: `migrations/2026-05-28-add-entry-zone-columns.sql`
- Modify: `modules/models.py`

- [ ] **Step 1: 寫 migration SQL**

```sql
-- migrations/2026-05-28-add-entry-zone-columns.sql
-- §三十三：dashboard 錨點 strip 需要精確進場區間，加 2 個 column
-- 沿用 §三十一 IF NOT EXISTS 安全模式（Supabase Web SQL Editor 路徑）

ALTER TABLE stock_analyses
  ADD COLUMN IF NOT EXISTS entry_low NUMERIC(10, 2);

ALTER TABLE stock_analyses
  ADD COLUMN IF NOT EXISTS entry_high NUMERIC(10, 2);
```

- [ ] **Step 2: `models.py` StockAnalysis 加對應 ORM Column**

定位：`modules/models.py` line 126（`stop_loss` 後面、`action_pill` 前面）。

```python
    stop_loss       = Column(Numeric(10, 2))  # short 失效停損價（B1c，2026-05-20）
    entry_low       = Column(Numeric(10, 2))  # 進場區下緣（plan §三十三，2026-05-28）
    entry_high      = Column(Numeric(10, 2))  # 進場區上緣（plan §三十三，2026-05-28）
    action_pill     = Column(String(32))      # 建議動作 pill（plan §三十一，2026-05-25）
```

- [ ] **Step 3: py_compile 檢查**

```
python -m py_compile modules/models.py
```

- [ ] **Step 4: commit F1**

```
feat(db): StockAnalysis 加 entry_low/entry_high column (plan §三十三)

- migrations/2026-05-28-add-entry-zone-columns.sql（IF NOT EXISTS 安全）
- models.py 對應 ORM Column

進場區精確區間支援 dashboard 錨點 strip「進 X-Y」顯示。
```

---

## F2 — TDD 測試紅燈

### Task 2：新增 `tests/test_stock_service_fallback.py`

**Files:**
- Create: `tests/test_stock_service_fallback.py`

- [ ] **Step 1: 寫失敗測試**（5 case）

```python
"""stock_service.get_user_stocks 14-day fallback 測試（plan §三十三, spec 2026-05-28）。

覆蓋：
- 主查詢命中（is_today_analysis=True）
- Fallback 命中（is_today_analysis=False, last_analysis_date 正確）
- 14 天邊界（14 天前命中、15 天前不命中）
- 多 symbol 混合（part 今日 / part fallback / part 無）
- 無分析資料 → 空（無 is_today_analysis key）
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.models import Base, User, Stock, StockAnalysis
from modules.stock_service import get_user_stocks


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    user = User(id=1, email='test@test.com', password_hash='x', role='user',
                max_stocks=20)
    s.add(user)
    s.commit()
    yield s
    s.close()


def _add_stock(db, user_id, symbol, name='測試股'):
    stock = Stock(user_id=user_id, symbol=symbol, name=name, status='watching')
    db.add(stock)
    db.commit()
    return stock


def _add_analysis(db, symbol, analysis_date, **kwargs):
    defaults = {
        'analysis_type': 'daily',
        'html_content': '<p>test</p>',
        'risk_pct': 50,
        'wyckoff_phase': '上漲',
        'action_pill': '🟢 進場區可佈',
        'support_price': 100,
        'resistance_price': 110,
        'target_price': 130,
        'entry_low': 100,
        'entry_high': 105,
    }
    defaults.update(kwargs)
    a = StockAnalysis(symbol=symbol, analysis_date=analysis_date, **defaults)
    db.add(a)
    db.commit()
    return a


def test_today_analysis_hits_primary_query(db, monkeypatch):
    """主查詢命中 → is_today_analysis=True、fallback 不執行。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, '2330.TW')
    _add_analysis(db, '2330.TW', today, risk_pct=30)

    result = get_user_stocks(db, user_id=1)
    assert len(result) == 1
    assert result[0]['symbol'] == '2330.TW'
    assert result[0]['risk_pct'] == 30
    assert result[0]['is_today_analysis'] is True
    assert result[0]['last_analysis_date'] == '2026-05-27'


def test_fallback_hits_when_today_missing(db, monkeypatch):
    """今日無分析 + 2 天前有 → fallback 命中、is_today_analysis=False。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, '2330.TW')
    _add_analysis(db, '2330.TW', date(2026, 5, 25), risk_pct=40)

    result = get_user_stocks(db, user_id=1)
    assert result[0]['is_today_analysis'] is False
    assert result[0]['risk_pct'] == 40
    assert result[0]['last_analysis_date'] == '2026-05-25'


def test_fallback_14day_boundary(db, monkeypatch):
    """14 天前命中、15 天前不命中（嚴格 >= cutoff）。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'A.TW')
    _add_stock(db, 1, 'B.TW')
    _add_analysis(db, 'A.TW', today - timedelta(days=14), risk_pct=14)
    _add_analysis(db, 'B.TW', today - timedelta(days=15), risk_pct=15)

    result = {item['symbol']: item for item in get_user_stocks(db, user_id=1)}
    # A: 14 天前命中
    assert result['A.TW'].get('risk_pct') == 14
    assert result['A.TW']['is_today_analysis'] is False
    # B: 15 天前不命中（無 risk_pct key、無 is_today_analysis key）
    assert 'risk_pct' not in result['B.TW']
    assert 'is_today_analysis' not in result['B.TW']


def test_fallback_takes_most_recent(db, monkeypatch):
    """同 symbol 有多筆 fallback 候選 → 取最近一筆。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'X.TW')
    _add_analysis(db, 'X.TW', date(2026, 5, 20), risk_pct=20)
    _add_analysis(db, 'X.TW', date(2026, 5, 26), risk_pct=26)  # 最近
    _add_analysis(db, 'X.TW', date(2026, 5, 23), risk_pct=23)

    result = get_user_stocks(db, user_id=1)
    assert result[0]['risk_pct'] == 26
    assert result[0]['last_analysis_date'] == '2026-05-26'


def test_mixed_today_and_fallback_and_none(db, monkeypatch):
    """3 支股：今日命中 / fallback 命中 / 都沒。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'T.TW')   # 今日命中
    _add_stock(db, 1, 'F.TW')   # fallback 命中
    _add_stock(db, 1, 'N.TW')   # 無
    _add_analysis(db, 'T.TW', today, risk_pct=11)
    _add_analysis(db, 'F.TW', date(2026, 5, 24), risk_pct=22)

    result = {item['symbol']: item for item in get_user_stocks(db, user_id=1)}
    assert result['T.TW']['is_today_analysis'] is True
    assert result['T.TW']['risk_pct'] == 11
    assert result['F.TW']['is_today_analysis'] is False
    assert result['F.TW']['risk_pct'] == 22
    assert 'risk_pct' not in result['N.TW']
```

- [ ] **Step 2: 跑測試確認失敗**

```
python -m pytest tests/test_stock_service_fallback.py -q
```

預期 5 個 fail（because `get_user_stocks` 還沒加 fallback 邏輯、entry_low/high column 未注入 dict）。

- [ ] **Step 3: commit F2**

```
test(stock_service): get_user_stocks 14-day fallback 5 TDD case (plan §三十三)
```

---

## F3 — `ai_analyzer_v2.py` 寫入 entry_low/high

### Task 3：寫入端從 swing_levels 拆 entry_zone

**Files:**
- Modify: `modules/ai_analyzer_v2.py`

- [ ] **Step 1: 找到兩個寫入點**

定位：`modules/ai_analyzer_v2.py` `analyze_stock_three_masters` 與 `analyze_market_only` 兩個函式組 result dict 的區段（line ~1170-1180 / line ~1525-1540 附近，跟 §三十二 修法同處）。

- [ ] **Step 2: 兩處皆加 entry_low/high 寫入**

```python
        # 既有 result dict 組裝（沿用）
        result = {
            ...
            'support': _sl.get('range_low') if _sl else None,
            ...
        }
        # F3 §三十三：寫入 entry_zone 拆欄位
        ez = _sl.get('entry_zone') if _sl else None
        if ez and len(ez) == 2:
            result['entry_low']  = float(ez[0])
            result['entry_high'] = float(ez[1])
        else:
            result['entry_low']  = None
            result['entry_high'] = None
```

**關鍵**：放在 §三十二 `_breakout_overrides` 覆寫之後（line ~1180 / ~1540），確保強勢突破覆寫後的新 entry_zone 也被寫入 DB。

- [ ] **Step 3: 確認呼叫端 `app.py` / `run_daily_report.py` 把 result 寫入 DB**

定位 `app.py` 中建 StockAnalysis row 的位置（grep `StockAnalysis(`），確認既有用 `result.get('xxx')` 寫入模式 → 自動帶入新欄位。

```python
# app.py / run_daily_report.py 應已是如下模式（無需改）：
row = StockAnalysis(
    symbol=symbol,
    analysis_date=analysis_day,
    ...
    stop_loss=result.get('stop_loss'),
    entry_low=result.get('entry_low'),     # 新
    entry_high=result.get('entry_high'),   # 新
    action_pill=result.get('action_pill'),
    ...
)
```

若呼叫端用 `**result` unpacking 模式 → 完全零改動；若 explicit 列欄位 → 加 2 行。

- [ ] **Step 4: py_compile 檢查**

```
python -m py_compile modules/ai_analyzer_v2.py
python -m py_compile app.py
python -m py_compile run_daily_report.py
```

- [ ] **Step 5: 退化檢查** — 跑完整測試套件

```
python -m pytest tests/ -q
```

預期：291 原 + 5 新（fallback 仍 fail，正常）= 296，291 pass + 5 fail。

- [ ] **Step 6: commit F3**

```
feat(analyzer): ai_analyzer_v2 寫入 entry_low/high 從 swing_levels (plan §三十三)
```

---

## F4 — `stock_service.py` fallback 邏輯（test 綠）

### Task 4：14-day fallback 查詢

**Files:**
- Modify: `modules/stock_service.py`

- [ ] **Step 1: 改 `get_user_stocks`（spec §四 F4 完整貼上）**

定位：`modules/stock_service.py` line 22-74。

關鍵變更：
- import `timedelta`
- 主查詢沿用
- 新增 fallback：對 missing symbols 查 14 天內最近一筆
- item dict 新增 6 欄位（risk_pct/wyckoff/action_pill 沿用 + support/resistance/target_pnf/stop_loss/entry_low/entry_high/is_today_analysis/last_analysis_date）

完整 patch：

```python
from datetime import date, timedelta  # ← timedelta 新增

def get_user_stocks(db: Session, user_id: int) -> list:
    stocks = (db.query(Stock)
              .filter_by(user_id=user_id)
              .order_by(case((Stock.display_order.is_(None), 1), else_=0),
                        Stock.display_order,
                        Stock.created_at)
              .all())

    analysis_day = _analysis_day_tw()
    symbols = [s.symbol for s in stocks]

    # 主查詢：今日（沿用）
    analyses = {}
    if symbols:
        rows = (db.query(StockAnalysis)
                .filter(StockAnalysis.symbol.in_(symbols),
                        StockAnalysis.analysis_type == 'daily',
                        StockAnalysis.analysis_date == analysis_day,
                        StockAnalysis.html_content.isnot(None))
                .all())
        analyses = {r.symbol: r for r in rows}

    # F4 §三十三：fallback 對 missing symbol 撈 14 天內最近一筆
    missing = [sym for sym in symbols if sym not in analyses]
    fallback_analyses = {}
    if missing:
        cutoff = analysis_day - timedelta(days=14)
        rows = (db.query(StockAnalysis)
                .filter(StockAnalysis.symbol.in_(missing),
                        StockAnalysis.analysis_type == 'daily',
                        StockAnalysis.analysis_date >= cutoff,
                        StockAnalysis.analysis_date < analysis_day,
                        StockAnalysis.html_content.isnot(None))
                .order_by(StockAnalysis.symbol,
                          StockAnalysis.analysis_date.desc())
                .all())
        for r in rows:
            if r.symbol not in fallback_analyses:
                fallback_analyses[r.symbol] = r

    result = []
    for s in stocks:
        item = {
            'id': s.id,
            'symbol': s.symbol,
            'name': s.name,
            'status': s.status,
        }
        primary = analyses.get(s.symbol)
        fallback = fallback_analyses.get(s.symbol)
        a = primary or fallback
        if a:
            item['risk_pct']      = a.risk_pct
            item['wyckoff_phase'] = a.wyckoff_phase
            item['action_pill']   = a.action_pill
            item['support']       = float(a.support_price) if a.support_price is not None else None
            item['resistance']    = float(a.resistance_price) if a.resistance_price is not None else None
            item['target_pnf']    = float(a.target_price) if a.target_price is not None else None
            item['stop_loss']     = float(a.stop_loss) if a.stop_loss is not None else None
            item['entry_low']     = float(a.entry_low) if a.entry_low is not None else None
            item['entry_high']   = float(a.entry_high) if a.entry_high is not None else None
            item['is_today_analysis']  = (primary is not None)
            item['last_analysis_date'] = a.analysis_date.isoformat()
        if s.status == 'holding' and s.trades:
            # 沿用既有 holding 欄位（total_zhang / avg_cost / trades）
            ...  # （沿用原邏輯）
        result.append(item)
    return result
```

- [ ] **Step 2: 跑測試確認綠燈**

```
python -m pytest tests/test_stock_service_fallback.py -q
```

預期 5 passed。

- [ ] **Step 3: 退化檢查**

```
python -m pytest tests/ -q
```

預期：296 全綠（291 原 + 5 新）。

- [ ] **Step 4: py_compile 檢查**

```
python -m py_compile modules/stock_service.py
```

- [ ] **Step 5: commit F4**

```
feat(stock_service): get_user_stocks 14-day fallback + 多欄位注入 (plan §三十三)
```

---

## F5 — 前端 dashboard.js + app.css

### Task 5：stale 視覺 + 錨點 strip

**Files:**
- Modify: `static/js/dashboard.js`
- Modify: `static/css/app.css`

無自動測試，標示「人工 visual 驗收」。

- [ ] **Step 1: `dashboard.js buildCard` 改寫**

按 spec §四 F5 完整貼上：
- `isToday = s.is_today_analysis !== false`
- `cardClasses` 加 `card-stale-data` 條件
- `lastTag` 新 chip（stale 才顯示）
- `anchorStripHtml = renderAnchorStrip(s)` 插在 statusRow 後、spark-wrap 前
- 新增 `formatLastDate(iso)` 與 `renderAnchorStrip(s)` 兩 helper

- [ ] **Step 2: `markCardAnalyzed` 同步移除 stale**

定位：`dashboard.js` line 412。

```js
function markCardAnalyzed(stockId, riskPct, wyckoffPhase) {
  const card = document.querySelector(`[data-stock-id="${stockId}"]`);
  if (!card) return;
  card.classList.add('analyzed');
  card.classList.remove('card-stale-data');   // F5 §三十三：分析完成移除 stale

  // 移除「上次 X/Y」tag
  const tag = card.querySelector('.last-analysis-tag');
  if (tag) tag.remove();

  // ... 既有 wyckoff / risk chip 更新邏輯
}
```

⚠️ **注意**：本函式只在「一鍵分析個股完成」事件觸發，不會帶 entry_low/high 等錨點欄位。為了讓錨點 strip 也即時更新，需要：
- 選項 A：分析完成後重撈 `/api/user/stocks` 整體 renderGrid（簡單但全量）
- 選項 B：分析完成後局部 fetch 該股最新 StockAnalysis 再更新 anchor-strip DOM（精準但複雜）

採選項 A（簡單；既有 grid render 已優化，14 檔重渲染 < 50ms）。`analyzeStock` 完成處 callback 後加 `await reloadGrid()` 或直接觸發既有 `renderGrid` 流程。

- [ ] **Step 3: `app.css` 加 3 個新 class**

按 spec §四 F6 完整貼上：
- `.stock-card.card-stale-data .card-status-row, .card-anchor-strip, .card-spark-wrap, .card-ohlc { opacity: 0.6 }`
- `.last-analysis-tag` chip 樣式（小、淺色、tabular nums）
- `.card-anchor-strip` 樣式（一行置中、淡背景、`.anchor-sep` 灰色分隔線）

定位：`static/css/app.css` 在 `.action-pill` 樣式區後（§三十一 加的位置）。

- [ ] **Step 4: JS 語法檢查**

```
node -c static/js/dashboard.js
```

- [ ] **Step 5: commit F5**

```
feat(ui): dashboard stale 視覺 + 錨點 strip (plan §三十三)

- buildCard 加 card-stale-data class + last-analysis-tag chip
- renderAnchorStrip 依方向（long/short/neutral）動態切換 label
- markCardAnalyzed 完成後移除 stale 樣式
- app.css 3 個新 class（stale opacity 60%、tag chip、anchor strip）
```

---

## F6 — 文件 + plan.md §三十三

### Task 6：文件齊備

**Files:**
- Already exists: `docs/superpowers/specs/2026-05-28-dashboard-stale-anchor-design.md`
- Already exists: `docs/superpowers/plans/2026-05-28-dashboard-stale-anchor.md`（本檔）
- Modify: `plan.md`（加 §三十三 節）

- [ ] **Step 1: plan.md 加 §三十三**

定位：`plan.md` 最末（§三十二 之後）。寫一節摘要：
- 觸發背景（Opt-2/3 brainstorming 5/26 定案）
- 設計選擇（4 表）
- 影響範圍（6 commit 表）
- 為什麼這樣設計（接受 1 migration 換精確區間）
- 驗收 checklist
- 回滾策略

- [ ] **Step 2: commit F6**

```
docs: plan.md §三十三 + spec + impl plan (5/28 dashboard stale anchor)
```

---

## 驗收 checklist

執行完 F1–F6 後（**push 前**）：

- [ ] `git log --oneline -7` 顯示 6 個新 commit + 本 plan/spec
- [ ] `python -m pytest tests/ -q` 全綠（296 passed = 291 原 + 5 新）
- [ ] `python -m py_compile modules/{models,ai_analyzer_v2,stock_service}.py` 無 syntax error
- [ ] `python -m py_compile app.py run_daily_report.py` 無 syntax error
- [ ] `node -c static/js/dashboard.js` 通過
- [ ] 既有 `tests/test_decide_action.py` / `tests/test_strong_breakout.py` 等不退化

**Deploy 步驟（用戶執行）：**
1. Supabase Web SQL Editor 跑 `migrations/2026-05-28-add-entry-zone-columns.sql`
2. SQL 確認：`SELECT column_name FROM information_schema.columns WHERE table_name='stock_analyses' AND column_name IN ('entry_low','entry_high');` 預期 2 row
3. `git push origin main` → Render auto-deploy
4. Render 部署完成後 dashboard hard refresh

**Deploy 後驗收（零 token，純 visual）：**
- 9:00 開盤前場景（或清今日分析 cache 後）→ 14 檔 mini-card 顯示淺灰 60% + 4 chip + 「上次 5/26」tag + 錨點 strip（沿用 5/26 資料）
- 若卡片 stale 樣式 + tag 正確顯示但 strip 顯示「—」→ 表示舊資料 entry_low/high 為 NULL（合理，5/26 那次分析還沒寫入新欄位），需重跑驗

**Deploy 後驗收（燒 ~$0.6 重跑 14 檔）：**
- 按一鍵分析 → 14 檔卡片 stale 樣式移除（回正常色彩）+ tag 消失
- 錨點 strip 顯示新分析錨點：
  - long 股（如矽力突破中）：`進 442.3-456.0 | 停 224.5 | 標 728.5`
  - short 股（如撼訊）：`空進 73.7 | 空停 76.0 | 空標 62.0`
  - neutral 股（如華擎）：`區間 X-Y | 雙向`
- 隔日早上 09:00 開盤前再開 dashboard → 14 檔自動回到 stale 視覺（沿用今日分析）→ Opt-2 完成驗收

---

## 回滾策略

| 出問題 commit | 回滾影響 |
|------|---------|
| F1 (migration + model) | `git revert F1` → models 沒新 column；DB 兩 column 留 NULL（無害）。Migration 一旦跑下去不易撤回，但 column 為 NULL nullable 不影響任何讀取 |
| F2 (test) | `git revert F2` → 純刪 test 檔，零影響 |
| F3 (analyzer 寫入) | `git revert F3` → result dict 無 entry_low/high；DB 兩 column 仍 NULL；前端 strip 顯示「—」 |
| F4 (stock_service fallback) | `git revert F4` → 回到「主查詢 only」舊行為；早上 09:00 全部「尚未分析」灰色（= 修法前狀態） |
| F5 (前端) | `git revert F5` → 卡片回原樣（無 stale 視覺、無 strip）。即使後端 fallback 仍工作，前端不消費 → 用戶看不到 stale 效果 |
| F6 (docs) | 純文件，無功能影響 |

**最壞情境**：F1 migration 跑下去後發現有 schema 問題 → DB 加 column 是純加性，可保留 NULL 不影響任何讀取；若真要回滾 `ALTER TABLE stock_analyses DROP COLUMN entry_low; DROP COLUMN entry_high;`（IF EXISTS 安全模式）。

**獨立性**：F1–F5 commit 設計可單獨 revert，互不依賴（F3 寫入端 / F4 讀取端 / F5 前端各自獨立；F1 schema 為前提但留 NULL 不影響）。

---

## 預估執行時間

| Task | 預估 |
|------|------|
| F1 migration + models | 10 min |
| F2 test 5 case | 25 min |
| F3 analyzer 寫入 + 呼叫端確認 | 15 min |
| F4 stock_service fallback 實作 | 30 min |
| F5 前端 buildCard + anchor strip + CSS | 40 min |
| F6 plan.md §三十三 + commit | 15 min |
| **合計** | **~2.5 小時** |

純後端 commits（F1–F4）約 80 min；前端 visual（F5）40 min；docs 收尾 15 min。
