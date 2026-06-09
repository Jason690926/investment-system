# §三十八 強漲回測股誠實揭露 + 看板即時離區 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 強漲後回測的觀察股（合晶/矽力）報表不再給出不可操作的寬進場區 + 「—」目標，改誠實揭露「強漲回測觀望」狀態；看板對即時價漂出進場區的卡片加灰標。

**Architecture:** 後端純函式 `_strong_pullback_state` 判定「區間過寬(>25%÷現價)」→ `_decide_action` 回新 pill `🟡 強漲回測觀望` + `_render_operation_framework` 改寫第五節（保留客觀失效價、砍假進場區/目標）。PDF 第五節與建議 pill 經既有 `[[OPERATION_FRAMEWORK]]` 注入 + `action_pill` DB 欄位**自動同步**，app.py 零改動。前端 `renderAnchorStrip` 加 #2 誠實 strip + #1 即時離區灰標，於 `updateCardPrice` 價載入後重繪。

**Tech Stack:** Python 3 / pytest（純函式 TDD）、vanilla JS（dashboard.js）、CSS（app.css）。零 DB migration。

**Spec:** `docs/superpowers/specs/2026-06-09-strong-pullback-honest-disclosure-design.md`

---

## 設計定案（brainstorming 決議）

- Q1=選項4 誠實揭露（不硬縮區間/不湊目標）
- Q2=選項1 兩症狀，但收斂為：**gate=②區間過寬**，①脫離原箱當 strip 標籤
- Q3=選項B 保留客觀失效價、砍假進場區/目標
- Q4=選項A 看板即時離區灰標 + ↑/↓ 微標；PDF 同步（經既有注入自動達成）
- Q5=選項1 單一 pill `🟡 強漲回測觀望`；門檻 **(entry_high−entry_low)÷price > 25%**
- 範圍：**僅 long**；零 migration；新 pill 沿用既有 🟡 amber class

## File Structure

| 檔案 | 責任 | 改動 |
|------|------|------|
| `modules/ai_analyzer_v2.py` | 後端判定 + 渲染 | 新增 `_strong_pullback_state`；`_decide_action` WATCH long 插 gate；`_render_operation_framework` 加 `price` 參數 + 誠實 long 分支；兩 call site 傳 `price=_price_f` |
| `static/js/dashboard.js` | 看板 strip | `renderAnchorStrip` 加 #2 誠實 strip + #1 離區灰標；`updateCardPrice` 價載入後重繪 strip |
| `static/css/app.css` | 視覺 | `.card-anchor-strip.drift-out` 灰 + `.anchor-drift-tag` 微標 |
| `tests/test_strong_pullback.py` | 純函式測試 | 新建 |
| `tests/test_decide_action_pullback.py` | gate 整合測試 | 新建 |
| `tests/test_operation_framework_pullback.py` | 渲染測試 | 新建 |

**app.py 不改**：PDF 第五節由 `_render_operation_framework` 注入 `[[OPERATION_FRAMEWORK]]`、PDF 建議 pill 讀 DB `action_pill`，兩者隨後端改動自動同步。#1 即時離區為看板限定（PDF 是分析時靜態快照，無「即時漂移」概念）。

---

## Task 1: `_strong_pullback_state` 純函式

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（在 `_decide_action` 定義前，約 line 789 前插入）
- Test: `tests/test_strong_pullback.py`（新建）

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_strong_pullback.py`：

```python
"""§三十八 強漲回測誠實揭露狀態 — _strong_pullback_state 純函式測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strong_pullback_state


def test_heji_wide_above_zone_detaches():
    """合晶型：price 80 > entry_high 76.8、區寬 30.9% → 脫離原箱。"""
    r = _strong_pullback_state(80.0, (52.1, 76.8))
    assert r is not None
    assert r['symptom'] == '脫離原箱'
    assert r['width_pct'] == 31


def test_silergy_wide_in_zone_too_wide():
    """矽力型：price 524 在區內、區寬 28.8% → 區間過寬。"""
    r = _strong_pullback_state(524.0, (391.0, 542.0))
    assert r is not None
    assert r['symptom'] == '區間過寬'
    assert r['width_pct'] == 29


def test_msi_tight_above_zone_returns_none():
    """微星型：price 139.5 > 上緣但區僅 10.9% → 不觸發（交給等回測）。"""
    assert _strong_pullback_state(139.5, (122.0, 137.25)) is None


def test_ruixuan_tight_in_zone_returns_none():
    """瑞軒型：price 43.6 在區內、區僅 17% → 不觸發。"""
    assert _strong_pullback_state(43.6, (37.5, 45.0)) is None


def test_boundary_exactly_25pct_not_triggered():
    """恰 25%：width=(125-100)/100=25% → 不觸發（用 <= threshold）。"""
    assert _strong_pullback_state(100.0, (100.0, 125.0)) is None


def test_boundary_just_over_25pct_triggered():
    """25.5%：width=(125.5-100)/100 → 觸發。"""
    assert _strong_pullback_state(100.0, (100.0, 125.5)) is not None


def test_below_entry_low_returns_none():
    """跌穿（price < entry_low）→ None（交給 跌穿觀察）。"""
    assert _strong_pullback_state(50.0, (52.1, 76.8)) is None


def test_invalid_inputs_return_none():
    assert _strong_pullback_state(None, (1, 2)) is None
    assert _strong_pullback_state(80, None) is None
    assert _strong_pullback_state(80, (76.8, 52.1)) is None  # ehi<=elo
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_strong_pullback.py -q`
Expected: FAIL — `ImportError: cannot import name '_strong_pullback_state'`

- [ ] **Step 3: 實作純函式**

在 `modules/ai_analyzer_v2.py` 的 `def _decide_action(` 定義前插入：

```python
def _strong_pullback_state(price, entry_zone, threshold=0.25):
    """強漲回測誠實揭露狀態判定（純函式，§三十八 2026-06-09）。

    強漲後回測股 _breakout_overrides 未觸發 → 沿用 calc_swing_levels 大箱
    （停損價~箱頂），進場區過寬到不可操作。此函式偵測該狀態。

    觸發條件（僅 long 場景使用）：
      entry_zone 有效 + price >= entry_low（非跌穿，跌穿交給「跌穿觀察」）
      + (entry_high - entry_low) / price > threshold（區間過寬）
    回傳 None（不觸發）或：
      {'symptom': '脫離原箱'（price > entry_high）| '區間過寬'（price 在區內）,
       'width_pct': <int 寬度÷現價的百分比>}
    """
    if price is None or not entry_zone:
        return None
    try:
        price_f = float(price)
        elo = float(entry_zone[0])
        ehi = float(entry_zone[1])
    except (TypeError, ValueError, IndexError):
        return None
    if price_f <= 0 or ehi <= elo:
        return None
    if price_f < elo:            # 跌穿 → 不觸發（讓 _decide_action 走跌穿觀察）
        return None
    width_ratio = (ehi - elo) / price_f
    if width_ratio <= threshold:
        return None
    symptom = '脫離原箱' if price_f > ehi else '區間過寬'
    return {'symptom': symptom, 'width_pct': round(width_ratio * 100)}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_strong_pullback.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: Commit**

```bash
git add tests/test_strong_pullback.py modules/ai_analyzer_v2.py
git commit -m "feat(pullback): §三十八 _strong_pullback_state 純函式 — 區間過寬偵測"
```

---

## Task 2: `_decide_action` WATCH long 插 gate

**Files:**
- Modify: `modules/ai_analyzer_v2.py:871-884`（WATCH long 的 `if entry_zone:` 區塊）
- Test: `tests/test_decide_action_pullback.py`（新建）

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_decide_action_pullback.py`：

```python
"""§三十八 _decide_action WATCH long 強漲回測 gate 整合測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action


def _swing(elo, ehi, rh=None, inv=None):
    """WATCH long swing_levels；entry_zone=(elo, ehi)。"""
    return {
        'direction': 'long',
        'range_low': elo, 'range_high': rh if rh is not None else ehi,
        'entry_zone': (elo, ehi),
        'invalidation': inv if inv is not None else elo,
        'target': None,
    }


def test_heji_wide_above_returns_pullback():
    """合晶：price 80 / zone 52.1-76.8（寬+脫離）→ 強漲回測觀望。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=101.5),
                       breakout=False, price=80.0)
    assert a == '🟡 強漲回測觀望'


def test_silergy_wide_in_zone_returns_pullback():
    """矽力：price 524 / zone 391-542（寬+在內）→ 強漲回測觀望。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(391.0, 542.0, rh=693.0),
                       breakout=False, price=524.0)
    assert a == '🟡 強漲回測觀望'


def test_msi_tight_above_still_wait_retest():
    """微星：price 139.5 / zone 122-137.25（窄+脫離）→ 維持 等回測。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(122.0, 137.25, rh=152.5),
                       breakout=False, price=139.5)
    assert a == '🟡 等回測'


def test_ruixuan_tight_in_zone_still_deployable():
    """瑞軒：price 43.6 / zone 37.5-45（窄+在內）→ 維持 進場區可佈。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(37.5, 45.0, rh=52.5),
                       breakout=False, price=43.6)
    assert a == '🟢 進場區可佈'


def test_below_entry_low_still_breakdown_watch():
    """跌穿優先：price < entry_low 即使區寬 → 跌穿觀察（不被 gate 攔）。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=101.5),
                       breakout=False, price=50.0)
    assert a == '🟡 跌穿觀察'


def test_breakout_still_chase():
    """新鮮突破不誤觸 gate：breakout=True → 追進 💪。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=76.8),
                       breakout=True, price=80.0)
    assert a == '🟢 追進 💪'
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_decide_action_pullback.py -q`
Expected: FAIL — `test_heji_*` / `test_silergy_*` 回 `🟡 等回測` / `🟢 進場區可佈`（gate 未加）

- [ ] **Step 3: 改 `_decide_action` entry_zone 區塊**

把 `modules/ai_analyzer_v2.py` 現有（約 871-884）：

```python
            if entry_zone:
                try:
                    zlo, zhi = float(entry_zone[0]), float(entry_zone[1])
                    if zlo <= price_f <= zhi:
                        return '🟢 進場區可佈'
                    if price_f > zhi:
                        return '🟡 等回測'
                    # Bug-J §三十六：跌穿 entry_low（失效價）→ 「跌穿觀察」
                    # 瑞耘 5/28 場景：phase=再積累 但 price 96.2 < entry_low 96.8
                    # 既有 fall-through 到 '⚪ 觀望' 對「停損已被跌穿」語意太溫和
                    if price_f < zlo:
                        return '🟡 跌穿觀察'
                except (TypeError, ValueError, IndexError):
                    pass
            return '⚪ 觀望'
```

改為（跌穿提到最前保優先，插入 §三十八 寬區間 gate）：

```python
            if entry_zone:
                try:
                    zlo, zhi = float(entry_zone[0]), float(entry_zone[1])
                    # Bug-J §三十六：跌穿 entry_low（失效價）→ 「跌穿觀察」（最優先）
                    # 瑞耘 5/28 場景：phase=再積累 但 price 96.2 < entry_low 96.8
                    if price_f < zlo:
                        return '🟡 跌穿觀察'
                    # §三十八：區間過寬（強漲回測，箱沒跟上）→ 強漲回測觀望
                    # 合晶/矽力：_breakout_overrides 未觸發、沿用大箱不可操作
                    if _strong_pullback_state(price_f, (zlo, zhi)):
                        return '🟡 強漲回測觀望'
                    if zlo <= price_f <= zhi:
                        return '🟢 進場區可佈'
                    if price_f > zhi:
                        return '🟡 等回測'
                except (TypeError, ValueError, IndexError):
                    pass
            return '⚪ 觀望'
```

- [ ] **Step 4: 跑測試確認通過 + 回歸**

Run: `python -m pytest tests/test_decide_action_pullback.py tests/test_decide_action.py tests/test_decide_action_below_entry.py tests/test_decide_action_pl_gate.py -q`
Expected: PASS（新 6 + 既有全綠）

- [ ] **Step 5: Commit**

```bash
git add tests/test_decide_action_pullback.py modules/ai_analyzer_v2.py
git commit -m "feat(pullback): §三十八 _decide_action 寬區間 gate → 強漲回測觀望"
```

---

## Task 3: `_render_operation_framework` 誠實第五節

**Files:**
- Modify: `modules/ai_analyzer_v2.py:950-1014`（函式簽名加 `price`；long 分支加誠實前置）
- Modify: `modules/ai_analyzer_v2.py:1411-1417` 與 `1844-1850`（兩 call site 傳 `price=_price_f`）
- Test: `tests/test_operation_framework_pullback.py`（新建）

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_operation_framework_pullback.py`：

```python
"""§三十八 _render_operation_framework 強漲回測誠實第五節測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _render_operation_framework


def _swing(elo, ehi, inv):
    return {'entry_zone': (elo, ehi), 'invalidation': inv,
            'range_high': ehi, 'target': None}


def test_pullback_detach_honest_block():
    """合晶：脫離原箱 → 誠實第五節含失效價、無假進場區/目標。"""
    html = _render_operation_framework(
        action_pill='🟡 強漲回測觀望', direction='long',
        swing_levels=_swing(52.1, 76.8, 52.1), breakout=False,
        price=80.0)
    assert '🟡 強漲回測觀望' in html
    assert '脫離原箱' in html
    assert '失效（整波論點作廢）：52.10 元' in html
    assert '待新箱形成後估算' in html
    assert '進場區：' not in html          # 砍掉假進場區
    assert '52.10 ~ 76.80' not in html     # 砍掉假進場區數字


def test_pullback_toowide_honest_block():
    """矽力：區間過寬 → 含寬度百分比。"""
    html = _render_operation_framework(
        action_pill='🟡 強漲回測觀望', direction='long',
        swing_levels=_swing(391.0, 542.0, 391.0), breakout=False,
        price=524.0)
    assert '進場區過寬 29%' in html
    assert '失效（整波論點作廢）：391.00 元' in html


def test_normal_long_unchanged():
    """非強漲回測 pill → 維持原進場區區塊（不誤改）。"""
    html = _render_operation_framework(
        action_pill='🟢 進場區可佈', direction='long',
        swing_levels=_swing(37.5, 45.0, 37.5), breakout=False,
        price=43.6)
    assert '進場區：' in html
    assert '強漲後回測' not in html
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_operation_framework_pullback.py -q`
Expected: FAIL — `_render_operation_framework() got unexpected keyword argument 'price'`

- [ ] **Step 3a: 改函式簽名 + long 分支誠實前置**

`modules/ai_analyzer_v2.py:950` 簽名加 `price=None`：

```python
def _render_operation_framework(action_pill: str, direction: str,
                                 swing_levels: dict | None, breakout: bool,
                                 vol_threshold_zhang=None, price=None) -> str:
```

在 `if direction == 'long':`（約 line 991）**之後、`if breakout:` 之前**插入誠實前置：

```python
    if direction == 'long':
        # §三十八：強漲回測觀望 → 誠實第五節（保留客觀失效價、砍假進場區/目標）
        if '強漲回測觀望' in (action_pill or ''):
            _sp = _strong_pullback_state(price, ez)
            if _sp and _sp['symptom'] == '脫離原箱':
                _sym = _row('強漲後回測，現價已脫離原箱（原進場區已不適用）')
            elif _sp:
                _sym = _row(f"強漲後回測，進場區過寬 {_sp['width_pct']}%，停損距現價過遠")
            else:
                _sym = _row('強漲後回測，原進場區已不適用')
            return (
                _divider()
                + _row(f'建議動作：{action_pill}')
                + _sym
                + _row(f'失效（整波論點作廢）：{_fmt(inv)} 元 — 跌破即多頭翻空')
                + _row('目標：待新箱形成後估算（先前等幅量度已達成）')
                + _divider()
            )
        if breakout:
            ...  # 既有 breakout 分支不動
```

（`ez` / `inv` / `_fmt` / `_row` / `_divider` 都已在函式上文定義，line 963-989。）

- [ ] **Step 3b: 兩 call site 傳 `price=_price_f`**

`modules/ai_analyzer_v2.py:1411`（analyze_stock_three_masters）：

```python
        _op = _render_operation_framework(
            action_pill=_action,
            direction=result['direction'],
            swing_levels=_sl,
            breakout=_breakout,
            vol_threshold_zhang=_vol_thr,
            price=_price_f,
        )
```

`modules/ai_analyzer_v2.py:1844`（analyze_market_only）— 同樣加 `price=_price_f,`：

```python
        _op = _render_operation_framework(
            action_pill=_action,
            direction=result['direction'],
            swing_levels=_sl,
            breakout=_breakout,
            vol_threshold_zhang=_vol_thr,
            price=_price_f,
        )
```

- [ ] **Step 4: 跑測試確認通過 + 回歸**

Run: `python -m pytest tests/test_operation_framework_pullback.py tests/test_operation_framework.py tests/test_operation_framework_hierarchy.py -q`
Expected: PASS（新 3 + 既有全綠）

- [ ] **Step 5: py_compile + Commit**

```bash
python -m py_compile modules/ai_analyzer_v2.py
git add tests/test_operation_framework_pullback.py modules/ai_analyzer_v2.py
git commit -m "feat(pullback): §三十八 第五節誠實揭露 + call site 傳 price"
```

---

## Task 4: 看板 strip — #2 誠實 strip + #1 即時離區灰標

**Files:**
- Modify: `static/js/dashboard.js:223-249`（`renderAnchorStrip`）
- Modify: `static/js/dashboard.js:364-379`（`updateCardPrice` 價載入後重繪 strip）

- [ ] **Step 1: 改 `renderAnchorStrip`**

把現有 `renderAnchorStrip`（223-249）整段替換為：

```javascript
function renderAnchorStrip(s) {
  // 完全無分析資料（連 fallback 都沒命中）→ 不顯示
  if (s.risk_pct == null && !s.wyckoff_phase) return '';
  const dir = s.wyckoff_phase ? (phaseDirection(s.wyckoff_phase)?.t || null) : null;
  const fmt = (v) => (v != null ? `${v}` : '—');
  const noEntryData = (s.entry_low == null && s.entry_high == null);
  const pill = s.action_pill || '';
  const price = (s._loaded_price != null) ? Number(s._loaded_price) : null;
  let html = '';
  let extraCls = '';
  if (dir === '空' && !noEntryData) {
    // short: 空進(entry_high) | 空停(stop_loss) | 空標(target_pnf)
    html = `空進 ${fmt(s.entry_high)} <span class="anchor-sep">|</span> 空停 ${fmt(s.stop_loss)} <span class="anchor-sep">|</span> 空標 ${fmt(s.target_pnf)}`;
  } else if (dir === '多' && !noEntryData) {
    // §三十八 #2：強漲回測觀望 → 誠實 strip（失效 X · 症狀待新箱）
    if (pill.includes('強漲回測觀望')) {
      const stop = s.stop_loss != null ? s.stop_loss : s.entry_low;
      let sym = '強漲回測';
      if (price != null && s.entry_high != null) {
        sym = (price > Number(s.entry_high)) ? '脫離原箱' : '區間過寬';
      }
      html = `失效 ${fmt(stop)} <span class="anchor-sep">·</span> ${sym}待新箱`;
    } else {
      // 正常 long strip：進(entry_low-entry_high) | 停(entry_low) | 標(target_pnf)
      const entry = `${s.entry_low}-${s.entry_high}`;
      const stop = s.stop_loss != null ? s.stop_loss : s.entry_low;
      html = `進 ${entry} <span class="anchor-sep">|</span> 停 ${fmt(stop)} <span class="anchor-sep">|</span> 標 ${fmt(s.target_pnf)}`;
      // §三十八 #1：即時價漂出進場區（pill 為 🟢 actionable 且非追進）→ 變灰 + ↑/↓ 微標
      if (price != null && pill.startsWith('🟢') && !pill.includes('追進')) {
        const ehi = (s.entry_high != null) ? Number(s.entry_high) : null;
        const elo = (s.entry_low  != null) ? Number(s.entry_low)  : null;
        if (ehi != null && price > ehi) {
          extraCls = ' drift-out';
          html += ` <span class="anchor-drift-tag">↑ 價已離區</span>`;
        } else if (elo != null && price < elo) {
          extraCls = ' drift-out';
          html += ` <span class="anchor-drift-tag">↓ 跌穿</span>`;
        }
      }
    }
  } else {
    // neutral / fallback：區間 + 雙向標示
    const range = (s.support != null && s.resistance != null)
      ? `${s.support}-${s.resistance}`
      : '—';
    html = `區間 ${range} <span class="anchor-sep">|</span> 雙向`;
  }
  return `<div class="card-anchor-strip${extraCls}">${html}</div>`;
}
```

- [ ] **Step 2: `updateCardPrice` 價載入後重繪 strip**

`static/js/dashboard.js:366-368` 現有：

```javascript
    allStocks[idx]._loaded_price = q.close;
    const s = allStocks[idx];
    if (s.status === 'holding' && s.avg_cost && s.action_pill) {
```

在 `const s = allStocks[idx];` 之後、`if (s.status === 'holding'...` 之前插入：

```javascript
    allStocks[idx]._loaded_price = q.close;
    const s = allStocks[idx];
    // §三十八：即時價載入後重繪錨點 strip（#1 離區灰標 + #2 症狀標籤需 price）
    const stripEl = card.querySelector('.card-anchor-strip');
    if (stripEl) {
      const freshStrip = renderAnchorStrip(s);
      if (freshStrip) stripEl.outerHTML = freshStrip;
    }
    if (s.status === 'holding' && s.avg_cost && s.action_pill) {
```

- [ ] **Step 3: syntax 驗證**

Run: `node -c static/js/dashboard.js`
Expected: 無輸出（syntax OK）

- [ ] **Step 4: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat(pullback): §三十八 看板 #2 誠實 strip + #1 即時離區灰標"
```

---

## Task 5: app.css 離區灰標樣式

**Files:**
- Modify: `static/css/app.css`（在 `.card-anchor-strip` 既有規則附近新增）

- [ ] **Step 1: 加 CSS**

在 `static/css/app.css` 的 `.card-anchor-strip` 規則之後新增（`--muted` / 琥珀色 token 沿用既有；若無 `--risk-mid` 則用 fallback `#F59E0B`）：

```css
/* §三十八：即時價漂出進場區 → strip 變灰（過時提示）*/
.card-anchor-strip.drift-out {
  opacity: 0.55;
}
/* ↑ 價已離區 / ↓ 跌穿 微標 — 琥珀色、不隨 strip 變灰 */
.card-anchor-strip .anchor-drift-tag {
  opacity: 1;
  margin-left: 4px;
  font-weight: 600;
  color: var(--risk-mid, #F59E0B);
}
```

- [ ] **Step 2: Commit**

```bash
git add static/css/app.css
git commit -m "feat(pullback): §三十八 離區灰標 CSS"
```

---

## Task 6: 全量驗證 + plan.md 進度

**Files:**
- Modify: `plan.md`（§三十八 段落）
- Modify: `CLAUDE.md`（當前進度快照 — 由收工指令更新，本 task 可略）

- [ ] **Step 1: 全量 pytest**

Run: `python -m pytest -q`
Expected: PASS — 358（§三十七 baseline）+ 8（Task1）+ 6（Task2）+ 3（Task3）= 375 全綠

- [ ] **Step 2: py_compile + node 全綠**

```bash
python -m py_compile modules/ai_analyzer_v2.py app.py
node -c static/js/dashboard.js
```
Expected: 無錯誤

- [ ] **Step 3: 真實 6/8 資料 dry-run 驗證（成本紀律）**

依「修改 AI 功能的紀律」，用 6/8 報表已知值靜態核對（不需 AI 重跑）：
- 合晶 price 80 / zone (52.1, 76.8)：`_decide_action` → `🟡 強漲回測觀望`；`_strong_pullback_state` → symptom='脫離原箱', width_pct=31
- 矽力 price 524 / zone (391, 542)：→ `🟡 強漲回測觀望`；symptom='區間過寬', width_pct=29
- 微星 price 132 / zone (122, 137.25)：→ `🟢 進場區可佈`（6/8 在區內，未誤觸）
- 瑞軒 price 43.6 / zone (37.5, 45)：→ `🟢 進場區可佈`（未誤觸）

用一行 python 確認：

```bash
python -c "from modules.ai_analyzer_v2 import _strong_pullback_state as f; print(f(80,(52.1,76.8)), f(524,(391,542)), f(132,(122,137.25)), f(43.6,(37.5,45)))"
```
Expected: `{'symptom': '脫離原箱', 'width_pct': 31} {'symptom': '區間過寬', 'width_pct': 29} None None`

- [ ] **Step 4: 更新 plan.md §三十八**

在 `plan.md` 末尾新增 §三十八 段落，記：緣起（6/9 cross-check）、gate=區間過寬25%、①脫離原箱當標籤、Q3-B 誠實揭露、#1 即時離區、僅 long、零 migration、元件清單、回滾。

- [ ] **Step 5: Commit**

```bash
git add plan.md
git commit -m "docs: §三十八 plan.md 強漲回測誠實揭露進度"
```

---

## Self-Review（writing-plans 規定，已執行）

**1. Spec coverage：**
- gate=區間過寬25% → Task 1（純函式）+ Task 2（_decide_action）✓
- ①脫離原箱當 strip 標籤 → Task 1 symptom + Task 3 第五節 + Task 4 strip ✓
- Q3-B 誠實揭露（留失效價、砍假進場區/目標）→ Task 3 ✓
- #1 即時離區灰標 + ↑/↓ → Task 4 + Task 5 ✓
- PDF 同步 → 經 `[[OPERATION_FRAMEWORK]]` + `action_pill` 自動達成（File Structure 已註明 app.py 不改）✓
- 僅 long → Task 2/3/4 皆限 long 分支 ✓
- 零 migration → 無 DB 任務 ✓
- 跌穿觀察優先 / breakout 不誤觸 → Task 2 回歸測試 ✓
- 測試計畫 → Task 1/2/3 + Task 6 全量 ✓

**2. Placeholder scan：** 無 TBD/TODO；每步含實際 code/命令/預期輸出。

**3. Type consistency：** `_strong_pullback_state(price, entry_zone, threshold=0.25)` 回 `{'symptom', 'width_pct'}`；Task 2/3/4 一致引用 `symptom`（值 '脫離原箱'/'區間過寬'）與 `width_pct`。pill 字串 `'🟡 強漲回測觀望'` 三處（Task2 回傳 / Task3 `in` 判定 / Task4 `includes`）一致。call site 變數 `_price_f` / `_sl` 兩處皆驗證存在（1401/1411、1834/1844）。

**4. 範圍：** 單一可實作 plan，6 task 純加性。

---

## 回滾策略

純加性，任一 task `git revert` 可獨立回滾：
- Task 1 新函式無 caller 前不影響
- Task 2 revert → 合晶/矽力 回 `等回測`/`進場區可佈`（修法前）
- Task 3 revert → 第五節回原進場區區塊（pill 仍運作）
- Task 4/5 revert → 看板回原 strip（無誠實 strip / 無離區灰標）
- 無 migration、無既有函式破壞性簽名改動（`_render_operation_framework` 新增 `price=None` 為 optional）
