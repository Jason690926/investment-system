# 優化1+2 實作計畫：持倉部位建議 + 強勢突破追蹤

> **For agentic workers:** 逐 Task 執行，每 Task 走 TDD（紅→綠→commit）。

**Goal:** 報表 §HOLDINGS 對持股（含虧損 neutral）自動附「持倉部位建議」；long 操作框架對放量突破前高的強勢股加「追進」備案。

**Architecture:** 兩者都改 `analyze_market_only`。優化2 新增純函式 `_strong_breakout_state` 算旗標注入 dynamic_block、static_block long 模板加條件分支；優化1 加 optional `holding_ctx` 參數、holding 時 static_block 加「六、持倉部位建議」段、呼叫端傳入。

**Tech Stack:** Python / pytest；spec：`docs/superpowers/specs/2026-05-22-holding-position-advice-design.md`、`...-strong-breakout-tracking-design.md`

---

## 優化2 — 強勢突破追蹤

### Task 1：`_strong_breakout_state` 純函式 + 測試

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（新增函式，置於 `_dual_swing_block` 之後）
- Test: `tests/test_strong_breakout.py`（新建）

- [ ] **Step 1: 寫失敗測試**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strong_breakout_state

def _ed(daily, vt, v5):
    return {'daily_bars': daily, 'volume_zhang': vt, 'volume_5d_avg_zhang': v5}

def _rising_daily(n=40):
    # 單調上升日K，calc_swing_levels 可取到 range_high
    return [{'date': f'2026-04-{i+1:02d}', 'open': 10+i, 'high': 12+i,
             'low': 9+i, 'close': 11+i, 'volume_zhang': 1000} for i in range(n)]

def test_breakout_true_when_above_range_high_and_volume():
    d = _rising_daily()
    # 現價遠高於任何 range_high，量達 5日均×1.5
    assert _strong_breakout_state(_ed(d, vt=2000, v5=1000), price_f=999) is True

def test_breakout_false_when_volume_insufficient():
    d = _rising_daily()
    assert _strong_breakout_state(_ed(d, vt=1200, v5=1000), price_f=999) is False

def test_breakout_false_when_price_below_range_high():
    d = _rising_daily()
    assert _strong_breakout_state(_ed(d, vt=2000, v5=1000), price_f=5) is False

def test_breakout_false_on_bad_input():
    assert _strong_breakout_state({'daily_bars': []}, price_f=None) is False
    assert _strong_breakout_state(_ed(_rising_daily(), vt=2000, v5='--'), price_f=999) is False
```

- [ ] **Step 2: 跑測試確認失敗** — `python -m pytest tests/test_strong_breakout.py -q`，預期 ImportError。

- [ ] **Step 3: 實作 `_strong_breakout_state`**

```python
def _strong_breakout_state(enriched_data: dict, price_f) -> bool:
    """優化2：現價放量站上 swing range_high（前高）→ 強勢突破，解鎖「追進」選項。
    現價 > range_high 且 今日量 ≥ 5日均量 × 1.5（=突破量門檻）才成立。"""
    if price_f is None:
        return False
    from modules.candlestick import calc_swing_levels
    sl = calc_swing_levels(enriched_data.get('daily_bars', []), 'long', price_f)
    if not sl or sl.get('range_high') is None:
        return False
    vt = enriched_data.get('volume_zhang')
    v5 = enriched_data.get('volume_5d_avg_zhang')
    try:
        return (float(price_f) > float(sl['range_high'])
                and vt is not None and v5 not in (None, '--', 0)
                and float(vt) >= float(v5) * 1.5)
    except (TypeError, ValueError):
        return False
```

- [ ] **Step 4: 跑測試確認通過** — `python -m pytest tests/test_strong_breakout.py -q`，預期 4 passed。

- [ ] **Step 5: commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_strong_breakout.py
git commit -m "feat(breakout): 優化2 Task1 — _strong_breakout_state 純函式 + 測試"
```

### Task 2：注入旗標 + long 操作框架條件分支

**Files:**
- Modify: `modules/ai_analyzer_v2.py` — `analyze_market_only`：dynamic_block（line ~1134 量能門檻區後）注入旗標；static_block long 操作框架模板（line ~1104-1109）改條件分支。

- [ ] **Step 1: dynamic_block 注入旗標**

於 `analyze_market_only` 內、`_swing_block` 取得後算旗標，並在 dynamic_block 的【量能門檻】區塊後加一行：

```python
_breakout = _strong_breakout_state(enriched_data, _price_f)
_breakout_line = ('【強勢突破狀態】成立（現價已放量站上前高）— long 操作框架啟用「追進」分支'
                  if _breakout else
                  '【強勢突破狀態】未成立 — long 操作框架用標準「回測進場」')
```
dynamic_block 字串內（`【量能門檻...】` 區塊後）插入 `{_breakout_line}`。

- [ ] **Step 2: static_block long 操作框架模板改條件分支**

將 line ~1104-1109 的【long 模板】替換為：

```
【long 模板】（依【波段操作錨點】鎖定值）
▸ 若 dynamic_block 標【強勢突破狀態】未成立 → 輸出標準 3 bullet：
<ul>
  <li>▶ 進場價：[entry_zone 區間] 元（觸發須量 ≥ 突破量門檻）</li>
  <li><span class="stop-loss">▶ 停損：[invalidation] 元 — 跌破即論點作廢</span></li>
  <li>▶ 目標：<span class="target-price">[target] 元（P&F 等幅量度）</span></li>
</ul>
▸ 若標【強勢突破狀態】成立 → 改輸出（追進與回測並陳）：
<ul>
  <li>▶ 強勢突破追蹤：現價已放量站上前高 [range_high] 元，可順勢追進；追進停損＝[range_high] 元（跌回前高即假突破）</li>
  <li>▶ 回測進場（保守）：[entry_zone] 元 — 不追高者待回測此區再進</li>
  <li>▶ 目標：<span class="target-price">[target] 元（P&F 等幅量度）</span></li>
</ul>
```

- [ ] **Step 3: 驗證 prompt 組裝**

於 `tests/test_strong_breakout.py` 加：

```python
from modules.ai_analyzer_v2 import analyze_market_only
import inspect

def test_long_template_has_breakout_branch():
    # static_block long 模板須含「強勢突破追蹤」與「回測進場（保守）」兩分支字串
    src = inspect.getsource(analyze_market_only)
    assert '強勢突破追蹤' in src
    assert '回測進場（保守）' in src
```

- [ ] **Step 4: 跑全套** — `python -m pytest -q` 全綠；`python -m py_compile modules/ai_analyzer_v2.py`。

- [ ] **Step 5: commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_strong_breakout.py
git commit -m "feat(breakout): 優化2 Task2 — 強勢突破狀態注入 + long 操作框架追進分支"
```

---

## 優化1 — 持倉部位建議

### Task 3：`analyze_market_only` 加 `holding_ctx` + 六、持倉部位建議

**Files:**
- Modify: `modules/ai_analyzer_v2.py` — `analyze_market_only` 簽章 + static_block + dynamic_block。

- [ ] **Step 1: 簽章加 optional 參數**

```python
def analyze_market_only(
    name: str,
    symbol: str,
    enriched_data: dict,
    news_list: list = None,
    holding_ctx: dict | None = None,   # 優化1：{'avg_cost','pnl_pct','qty_zhang'}；None=觀察股
) -> dict:
```

- [ ] **Step 2: dynamic_block 注入持股資訊**

於 dynamic_block 組裝前：

```python
if holding_ctx:
    _hold_line = (f"\n【持倉狀態（你目前持有此股）】成本 {holding_ctx.get('avg_cost')} 元"
                  f" ｜ 損益 {holding_ctx.get('pnl_pct')}%"
                  f" ｜ 部位 {holding_ctx.get('qty_zhang')} 張")
else:
    _hold_line = ''
```
插入 dynamic_block（現價區後）。

- [ ] **Step 3: static_block 加條件式「六、持倉部位建議」**

static_block 為固定字串（cache）；「六」一律寫入模板，但加指示：「僅當 dynamic_block 出現【持倉狀態】時才輸出第六節，否則跳過」。於「五、操作框架」schema 後加：

```
### 六、持倉部位建議（僅當 dynamic_block 有【持倉狀態】時輸出，否則整節跳過）
你正分析一位「已持有此股」的投資人，無論 DIRECTION 為 long/short/neutral，都須輸出 3 bullet：
<ul>
  <li>▶ 整體判斷：（只選一個）續抱 / 減碼 / 出場 / 觀望持有 — 結合損益與結構說明理由（≤40字）</li>
  <li>▶ 部位處理觸發價：跌破 [失效/翻空價] 元減碼；站回/守穩 [反轉或續抱條件價] 元為續抱依據（價位引用上方錨點，禁另算）</li>
  <li><span class="stop-loss">▶ 持倉停損：[失效價] 元 — 跌破請執行</span></li>
</ul>
⚠️ neutral 持股即使「五、操作框架」為「區間不操作」，第六節仍須給具體續抱/減碼價位。
```

- [ ] **Step 4: 加 prompt 組裝測試**

`tests/test_holding_advice.py`（新建）：

```python
import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import analyze_market_only

def test_signature_has_holding_ctx():
    assert 'holding_ctx' in inspect.signature(analyze_market_only).parameters

def test_static_block_has_section_six():
    src = inspect.getsource(analyze_market_only)
    assert '六、持倉部位建議' in src
    assert '持倉停損' in src
```

- [ ] **Step 5: 跑測試 + py_compile** — `python -m pytest tests/test_holding_advice.py -q` 綠；`python -m py_compile modules/ai_analyzer_v2.py`。

- [ ] **Step 6: commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_holding_advice.py
git commit -m "feat(holding): 優化1 Task3 — analyze_market_only 加 holding_ctx + 六、持倉部位建議"
```

### Task 4：`api_analyze_stock` 傳入 holding_ctx

**Files:**
- Modify: `app.py` — `api_analyze_stock`（line ~693 `analyze_market_only(...)` 呼叫）。

- [ ] **Step 1: 組 holding_ctx 並傳入**

於 line ~688 `result = analyze_market_only(...)` 前組裝：

```python
        _hctx = None
        if stock.status == 'holding' and stock.trades and stock.avg_cost:
            _cost = float(stock.avg_cost)
            _pnl = None
            if enriched.get('price') not in (None, '--') and _cost > 0:
                _pnl = round((float(enriched['price']) - _cost) / _cost * 100, 1)
            _hctx = {'avg_cost': _cost, 'pnl_pct': _pnl,
                     'qty_zhang': float(stock.total_zhang) if stock.total_zhang else 0.0}
```
呼叫改為 `analyze_market_only(name=..., symbol=..., enriched_data=enriched, news_list=[], holding_ctx=_hctx)`。

- [ ] **Step 2: py_compile + 全套測試** — `python -m py_compile app.py`；`python -m pytest -q` 全綠。

- [ ] **Step 3: commit**

```bash
git add app.py
git commit -m "feat(holding): 優化1 Task4 — api_analyze_stock 傳入 holding_ctx"
```

### Task 5：`run_daily_report` 傳入 holding_ctx

**Files:**
- Modify: `run_daily_report.py` — `cache_market_analysis` 加 optional `holding_ctx` 參數並轉傳；其呼叫端（批次迴圈）由 Stock 組 holding_ctx。

- [ ] **Step 1: `cache_market_analysis` 加參數轉傳**

```python
def cache_market_analysis(db, symbol: str, name: str, holding_ctx: dict | None = None) -> bool:
    ...
    result = analyze_market_only(name=name, symbol=symbol,
                                 enriched_data=enriched, holding_ctx=holding_ctx)
```

- [ ] **Step 2: 呼叫端由 Stock 組 holding_ctx**

找 `cache_market_analysis(` 呼叫處（批次迴圈，迴圈變數為 Stock 物件），比照 Task4 組 `holding_ctx`（持股才組，觀察股 None）後傳入。若該迴圈無 quote 可算 pnl，`pnl_pct` 給 None（prompt 仍可運作）。

- [ ] **Step 3: py_compile + 全套測試** — `python -m py_compile run_daily_report.py`；`python -m pytest -q` 全綠。

- [ ] **Step 4: commit**

```bash
git add run_daily_report.py
git commit -m "feat(holding): 優化1 Task5 — run_daily_report 傳入 holding_ctx"
```

---

## 驗收

- pytest 全綠（新增 test_strong_breakout.py / test_holding_advice.py）、py_compile 全綠。
- ⚠️ 兩者皆 prompt 行為改動，需 deploy + 燒 ~$0.6 重跑一鍵分析驗：
  1. 持股（晶心科/創惟）報表出現「六、持倉部位建議」3 bullet；neutral 持股也有續抱/減碼價位；觀察股無第六節。
  2. 強勢突破股（現價放量站上前高）long 操作框架出現「強勢突破追蹤」追進選項 + 並陳「回測進場（保守）」；非突破 long 股維持標準 3 bullet。
- 回滾：純加性（optional 參數 + 條件式 prompt 分支 + 新純函式），單 commit 可 revert。

## Self-Review

- спец coverage：優化1 spec 決策1-4 → Task3-5；優化2 spec 決策1-3 → Task1-2 ✅
- 型別一致：`holding_ctx` dict keys（avg_cost/pnl_pct/qty_zhang）Task3/4/5 一致；`_strong_breakout_state(enriched_data, price_f)` 簽章 Task1/2 一致 ✅
- 無 placeholder：各 Step 含實際程式碼 ✅
