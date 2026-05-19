# 中長期波段框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把個股/大盤/個人建議從「當日短線翻來覆去」改為「程式鎖定錨點 + 2週-1個月穩定波段論點」。

**Architecture:** `candlestick.py` 新增純加性 `calc_swing_levels()`（復用既有 `_find_local_peaks/_troughs` + `calc_pnf_target`）。`ai_analyzer_v2.py` 三函式注入鎖定錨點（鏡像既有 `_dual_pnf` 模式）、移除短線段換波段框架、加穩定鐵律。零 DB schema 變更、零經常性 AI 成本。

**Tech Stack:** Python 3.14、pytest、現有 `modules/candlestick.py` / `modules/ai_analyzer_v2.py`。

設計來源：`docs/superpowers/specs/2026-05-19-midterm-swing-framework-design.md`

---

## 檔案結構

| 檔案 | 責任 | 動作 |
|------|------|------|
| `modules/candlestick.py` | 程式錨點計算（資料地基）| 新增 `calc_swing_levels()`，不改既有函式 |
| `tests/test_swing_levels.py` | 錨點 helper 單元 + 穩定性回歸 | 新建 |
| `modules/ai_analyzer_v2.py` | AI prompt：注入錨點 + 波段框架 + 穩定鐵律 | 修改 3 函式 + 新增 `_dual_swing_block` |
| `plan.md` | 架構決策紀錄 | 新增 §二十三 |

---

## Task 1: `calc_swing_levels()` — 程式錨點 helper

**Files:**
- Modify: `modules/candlestick.py`（在 `_find_local_troughs` 後、`detect_patterns` 前，約 line 34 後插入）
- Test: `tests/test_swing_levels.py`（新建）

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_swing_levels.py`：

```python
"""calc_swing_levels — 程式錨點 + 穩定性回歸（spec 2026-05-19）"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.candlestick import calc_swing_levels


def _bars(seq):
    """seq: list of (o,h,l,c) → bars dicts（volume 不影響 swing 計算）"""
    return [{'open': o, 'high': h, 'low': l, 'close': c, 'volume_zhang': 1000}
            for (o, h, l, c) in seq]


def _ramp_with_swings():
    """造一段含明確局部峰谷的 40 根日K：
    谷在 idx~10（low=90）、峰在 idx~25（high=130），尾端回落到 ~115"""
    seq = []
    for i in range(40):
        if i < 10:
            base = 100 - i          # 100→91 下行
        elif i < 25:
            base = 90 + (i - 10) * 2.7  # 90→~130 上行
        else:
            base = 130 - (i - 25) * 1.0  # 130→115 回落
        seq.append((base, base + 2, base - 2, base + 0.5))
    return _bars(seq)


def test_long_anchors():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'long', current_price=118.0)
    assert r is not None
    # 失效=最近波段低點（跌破→多方論點作廢），加碼=最近波段高點
    assert r['invalidation'] < r['add_trigger']
    assert r['invalidation'] == pytest.approx(r['range_low'], abs=1e-6)
    assert r['add_trigger'] == pytest.approx(r['range_high'], abs=1e-6)
    lo, hi = r['entry_zone']
    mid = (r['range_low'] + r['range_high']) / 2
    assert lo == pytest.approx(r['range_low'], abs=1e-6)
    assert hi == pytest.approx(mid, abs=1e-6)
    assert r['direction'] == 'long'


def test_short_anchors_mirror_long():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'short', current_price=118.0)
    assert r is not None
    # short 鏡像：失效=波段高（站回→回補），加碼=波段低（跌破→加空）
    assert r['invalidation'] > r['add_trigger']
    assert r['invalidation'] == pytest.approx(r['range_high'], abs=1e-6)
    assert r['add_trigger'] == pytest.approx(r['range_low'], abs=1e-6)
    lo, hi = r['entry_zone']
    mid = (r['range_low'] + r['range_high']) / 2
    assert lo == pytest.approx(mid, abs=1e-6)
    assert hi == pytest.approx(r['range_high'], abs=1e-6)


def test_neutral_range_and_flips():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'neutral', current_price=118.0)
    assert r is not None
    assert r['range_low'] < r['range_high']
    assert r['flip_long'] == pytest.approx(r['range_high'], abs=1e-6)
    assert r['flip_short'] == pytest.approx(r['range_low'], abs=1e-6)
    assert r['invalidation'] is None
    assert r['add_trigger'] is None
    assert r['entry_zone'] is None


def test_insufficient_bars_returns_none():
    assert calc_swing_levels(_bars([(100, 102, 98, 101)] * 10), 'long', 100) is None
    assert calc_swing_levels([], 'long', 100) is None
    assert calc_swing_levels(None, 'long', 100) is None


def test_no_local_peak_returns_none():
    # 純單調上行，無左右確認的局部峰谷
    seq = [(100 + i, 100 + i + 1, 100 + i - 1, 100 + i) for i in range(40)]
    assert calc_swing_levels(_bars(seq), 'long', 140) is None


def test_bad_direction_returns_none():
    assert calc_swing_levels(_ramp_with_swings(), 'sideways', 118) is None


def test_stability_same_bars_byte_identical():
    bars = _ramp_with_swings()
    a = calc_swing_levels(bars, 'long', 118.0)
    b = calc_swing_levels(bars, 'long', 118.0)
    assert a == b


def test_stability_appending_non_breaking_bar_keeps_anchors():
    """尾端加一根『未觸及失效價』的 bar，錨點不變 → 翻來覆去根治實證"""
    bars = _ramp_with_swings()
    base = calc_swing_levels(bars, 'long', 118.0)
    # 加一根仍在 invalidation 之上、未創新高的 bar
    safe = base['invalidation'] + 5
    bars2 = bars + [{'open': safe, 'high': safe + 1, 'low': safe - 1,
                     'close': safe, 'volume_zhang': 1000}]
    after = calc_swing_levels(bars2, 'long', safe)
    assert after['invalidation'] == pytest.approx(base['invalidation'], abs=1e-6)
    assert after['add_trigger'] == pytest.approx(base['add_trigger'], abs=1e-6)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_swing_levels.py -q`
Expected: FAIL — `ImportError: cannot import name 'calc_swing_levels'`

- [ ] **Step 3: 實作 `calc_swing_levels`**

在 `modules/candlestick.py` 的 `_find_local_troughs` 函式結束後（line 33 之後、`def detect_patterns` 之前）插入：

```python
def calc_swing_levels(bars: list, direction: str,
                       current_price: float = None) -> dict | None:
    """波段操作錨點（程式計算，AI 禁改）— spec 2026-05-19。

    取最後 60 根日K（不足 60 用全部，<20 回 None）的真實局部峰谷，
    取窗口內『最近一個』局部峰=波段高、最近一個局部谷=波段低。
    波段高低點僅在新局部峰谷形成時才變（=失效事件本身），故價格未
    觸及失效線時每日重跑錨點不動 → 論點不漂移（根治翻來覆去）。

    回傳 dict（資料不足回 None）：
      long :  invalidation=波段低  add_trigger=波段高  entry_zone=(波段低, mid)
      short:  invalidation=波段高  add_trigger=波段低  entry_zone=(mid, 波段高)
      neutral: range_low/range_high + flip_long(=波段高)/flip_short(=波段低)
      target: long/short 串 calc_pnf_target 對應方向；neutral=None
    """
    if direction not in ('long', 'short', 'neutral'):
        return None
    if not bars or len(bars) < 20:
        return None
    try:
        window = bars[-60:]
        highs = [float(b['high']) for b in window]
        lows  = [float(b['low'])  for b in window]
        peaks   = _find_local_peaks(highs, min_gap=3)
        troughs = _find_local_troughs(lows, min_gap=3)
        if not peaks or not troughs:
            return None
        swing_high = peaks[-1][1]      # 最近一個局部峰
        swing_low  = troughs[-1][1]    # 最近一個局部谷
        if swing_high <= swing_low:
            return None
        mid = (swing_low + swing_high) / 2.0

        if direction == 'neutral':
            return {
                'direction':   'neutral',
                'range_low':   swing_low,
                'range_high':  swing_high,
                'flip_long':   swing_high,
                'flip_short':  swing_low,
                'invalidation': None,
                'add_trigger':  None,
                'entry_zone':   None,
                'target':       None,
            }

        target = calc_pnf_target(bars, lookback=20,
                                 current_price=current_price,
                                 direction=direction)
        if direction == 'long':
            return {
                'direction':    'long',
                'range_low':    swing_low,
                'range_high':   swing_high,
                'invalidation': swing_low,
                'add_trigger':  swing_high,
                'entry_zone':   (swing_low, mid),
                'flip_long':    None,
                'flip_short':   None,
                'target':       target,
            }
        # short（long 幾何鏡像）
        return {
            'direction':    'short',
            'range_low':    swing_low,
            'range_high':   swing_high,
            'invalidation': swing_high,
            'add_trigger':  swing_low,
            'entry_zone':   (mid, swing_high),
            'flip_long':    None,
            'flip_short':   None,
            'target':       target,
        }
    except (KeyError, TypeError, ValueError, IndexError) as e:
        print(f'[candlestick] calc_swing_levels 失敗: {e}')
        return None
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_swing_levels.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 跑既有 candlestick 測試確認零退化**

Run: `python -m pytest tests/test_candlestick.py -q`
Expected: PASS（既有全綠，`calc_swing_levels` 純加性未改 `calc_pnf_target`）

- [ ] **Step 6: Commit**

```bash
git add modules/candlestick.py tests/test_swing_levels.py
git commit -m "feat(candlestick): calc_swing_levels 程式錨點（spec 2026-05-19 §1）

復用 _find_local_peaks/_troughs + calc_pnf_target；long/short 鏡像、
neutral 區間+雙向 flip；穩定性回歸驗證（未觸及失效→錨點不變）。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `_dual_swing_block` + `analyze_stock_three_masters` 注入

**Files:**
- Modify: `modules/ai_analyzer_v2.py`：新增 `_dual_swing_block`（在 `_dual_pnf` 後，約 line 206 後）；`analyze_stock_three_masters` 的 `action_section`（line 356-368）、`dynamic_block`（line 453 後）

- [ ] **Step 1: 新增 `_dual_swing_block` helper**

在 `ai_analyzer_v2.py` `_dual_pnf` 函式結束（line 206 `return pnf_long, pnf_short, block`）之後插入：

```python
def _dual_swing_block(enriched_data: dict, price_f) -> str:
    """波段操作錨點注入塊（鏡像 _dual_pnf）：同時算 long/short/neutral
    三組程式鎖定錨點，AI 依其判定的 DIRECTION 取對應組。資料不足→誠實提示。"""
    from modules.candlestick import calc_swing_levels
    dk = enriched_data.get('daily_bars', [])
    sl_long  = calc_swing_levels(dk, 'long',    price_f)
    sl_short = calc_swing_levels(dk, 'short',   price_f)
    sl_neu   = calc_swing_levels(dk, 'neutral', price_f)
    if not (sl_long or sl_short or sl_neu):
        return "【波段操作錨點】本期資料不足，不給波段框架（誠實 > 錯誤）。"

    def _f(v):
        return f'{v:.2f}' if isinstance(v, (int, float)) else '—'

    lines = ["【波段操作錨點（程式計算，禁止更改）｜依你判定的 DIRECTION 取對應組】"]
    if sl_long:
        ez = sl_long['entry_zone']
        lines.append(
            f"· long：失效/停損 {_f(sl_long['invalidation'])} ｜ 加碼觸發 "
            f"{_f(sl_long['add_trigger'])} ｜ 進場區 {_f(ez[0])}~{_f(ez[1])} ｜ "
            f"波段目標 {_f(sl_long['target'])}")
    if sl_short:
        ez = sl_short['entry_zone']
        lines.append(
            f"· short：失效/回補 {_f(sl_short['invalidation'])} ｜ 加空觸發 "
            f"{_f(sl_short['add_trigger'])} ｜ 放空區 {_f(ez[0])}~{_f(ez[1])} ｜ "
            f"下行目標 {_f(sl_short['target'])}")
    if sl_neu:
        lines.append(
            f"· neutral：區間 {_f(sl_neu['range_low'])}~{_f(sl_neu['range_high'])}"
            f"（突破上緣+量轉多 / 跌破下緣+量轉空，區間內不操作）")
    return "\n".join(lines)
```

- [ ] **Step 2: 在 `analyze_stock_three_masters` 算出 swing block**

`ai_analyzer_v2.py` line 339（`_rs_section = ...` 之後）新增一行。原文：

```python
    _rs_section = f"\n\n{_rs_block}" if _rs_block else ""
```

改為：

```python
    _rs_section = f"\n\n{_rs_block}" if _rs_block else ""
    _swing_block = _dual_swing_block(enriched_data, _price_f)
```

- [ ] **Step 3: 把 swing block 注入 dynamic_block**

`ai_analyzer_v2.py` line 453。原文：

```python
{pnf_block}{_rs_section}
```

改為：

```python
{pnf_block}{_rs_section}

{_swing_block}
```

- [ ] **Step 4: action_section 移除短線段、換波段框架**

`ai_analyzer_v2.py` line 356-368。完整原文：

```python
    if status == 'holding':
        action_section = f"""### 五、操作建議（已持有，依 DIRECTION）
- long：續抱/加碼/減碼；short：減碼/出場/反手放空（依方向擇一）
- <span class="short-term-title">▶ 短期（1-5日）</span>：依方向給具體進出場
- long 加碼：突破壓力且量 > {_vol_breakout} 張（5日均量×1.5，程式計算，禁止更改）
- short 進場：跌破撐位或回測壓力線放空，量能引用上方門檻
- <span class="stop-loss">停損：long 跌破撐位停損 / short 站回壓力線回補（XX 元，不要猶豫）</span>"""
    else:
        action_section = f"""### 五、操作建議（觀察中，依 DIRECTION）
- <span class="short-term-title">▶ 短線進場條件（1-5日）</span>：long 突破 XX 元做多 / short 跌破 XX 元放空，量 > {_vol_breakout} 張（程式計算，禁止更改）
- <span class="mid-term-title">▶ 中線布局（月線角度）</span>：long 積累完成 Spring 縮量需達 {_vol_spring} 張 / short 派發確認反彈無量
- <span class="stop-loss">預設停損：long 跌破 XX 元出場 / short 站回 XX 元回補</span>
- 依 DIRECTION 說明目前是否適合進場（做多或放空）及理由"""
```

整段替換為：

```python
    if status == 'holding':
        action_section = f"""### 五、波段操作框架（2週-1個月+，依 DIRECTION）
⚠️ 所有價位必須引用上方【波段操作錨點】鎖定值，禁止自行估算或改數字。
- 波段論點：一句話說明本波段做多/做空/觀望的核心理由（≤30字）
- long：續抱/加碼/減碼擇一；short：減碼/出場/反手放空擇一（依方向）
- <span class="stop-loss">▶ 失效/停損價：[錨點 invalidation] 元 — 跌破(long)/站回(short)即論點作廢，執行不猶豫</span>
- ▶ 加碼觸發：突破[錨點 add_trigger](long) / 跌破[錨點 add_trigger](short) 且量 > {_vol_breakout} 張（程式計算，禁止更改）
- ▶ 波段目標：[錨點 target] 元（等幅量度，可能為 — 表示尚無）
- neutral：明講無波段方向，[range_low]~[range_high] 區間內不操作，僅標突破/跌破轉向條件"""
    else:
        action_section = f"""### 五、波段操作框架（2週-1個月+，依 DIRECTION）
⚠️ 所有價位必須引用上方【波段操作錨點】鎖定值，禁止自行估算或改數字。
- 波段論點：一句話說明本波段做多/做空/觀望的核心理由（≤30字）
- ▶ 進場區：[錨點 entry_zone] 元；觸發須量 > {_vol_breakout} 張（程式計算，禁止更改）
- <span class="stop-loss">▶ 失效/停損價：[錨點 invalidation] 元 — 跌破(long)/站回(short)即論點作廢</span>
- ▶ 加碼觸發：[錨點 add_trigger] 元　▶ 波段目標：[錨點 target] 元
- long/short：說明目前是否到進場區及理由（波段角度，非當日）
- neutral：明講無波段方向，[range_low]~[range_high] 區間內不操作，僅標突破[range_high]+量轉多 / 跌破[range_low]+量轉空"""
```

- [ ] **Step 5: static_block 加穩定鐵律**

`ai_analyzer_v2.py` line 400-401。原文：

```python
## ⚠️ 交易原則（融入操作判斷）
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。
```

改為：

```python
## ⚠️ 交易原則（融入操作判斷）
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。

## ⚠️ 波段論點穩定性（最高紀律，凌駕單日盤面）
本框架為 2 週-1 個月以上波段定位，不做當沖。失效價未被觸及前，方向與
進出場價維持不變；每日重跑只更新「現價距失效價還有多遠」，禁止因單日
紅綠或漲跌改變方向或重設價位。禁止輸出「今日宜/不宜進場」這類當日結論。
```

- [ ] **Step 6: py_compile + 既有測試零退化**

Run: `python -m py_compile modules/ai_analyzer_v2.py && python -m pytest -q`
Expected: py_compile 無輸出（OK）；pytest 全綠（119 既有 + 8 新 = 127 passed）

- [ ] **Step 7: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(ai): analyze_stock_three_masters 波段框架取代短線段（spec §2）

_dual_swing_block 注入鎖定錨點（鏡像 _dual_pnf）；action_section
移除▶短期(1-5日)/▶短線進場(1-5日)換波段框架；加波段穩定鐵律。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `analyze_market_only` 對齊

**邊界說明**：`analyze_market_only` 明示「不含操作建議」（line 692）。為不破壞此邊界，本函式**只**做：注入錨點 + `今日時機`→波段定位語言 + 穩定鐵律。**不**加 entry/add 操作段（那屬 Task 2 / Task 4）。

**Files:**
- Modify: `modules/ai_analyzer_v2.py`：`analyze_market_only`（line 608 後注入；line 720 換語言；交易原則區加鐵律）

- [ ] **Step 1: 算 swing block 並注入 dynamic_block**

`ai_analyzer_v2.py` line 608 區域。先確認 `analyze_market_only` 內 `_rs_block` / `price_f` 變數名（line 608 `_rs_block = _market_rs_block(...)`）。在 `_rs_section`（line 608-609 對應）定義後新增：

```python
    _swing_block = _dual_swing_block(enriched_data, _price_f)
```

（若該函式內價格變數名非 `_price_f`，用該函式既有的 price float 變數；對照 Task 2 Step 2 同模式。）

dynamic_block line 741 原文：

```python
{pnf_block}{_rs_section}
```

改為：

```python
{pnf_block}{_rs_section}

{_swing_block}
```

- [ ] **Step 2: `今日時機` 換波段定位**

`ai_analyzer_v2.py` line 719-720。原文：

```python
- 等待條件：需等待什麼才適合行動（量能引用【突破最低量能門檻】欄位數值/價格/K棒）
- 今日時機：**立刻可行動 / 等待確認 / 不宜行動**；short 時「行動」指賣空進場或回測壓力線放空，非做多
```

改為：

```python
- 波段確認條件：需等什麼結構訊號才確立波段（量能引用【突破最低量能門檻】+【波段操作錨點】價位/K棒）
- 波段定位：依【波段操作錨點】說明距失效價多遠、是否在進場區；short 指放空/回測壓力。禁輸出「今日宜/不宜」當日結論
```

- [ ] **Step 3: 加穩定鐵律**

`ai_analyzer_v2.py` `analyze_market_only` static_block 的交易原則/結構方向區。定位 line 665 原文：

```python
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。
```

改為（與 Task 2 Step 5 同文字，保持兩函式一致）：

```python
不預測只依訊號行動；沒突破不追價；沒設停損不進場；風險優先於報酬。

## ⚠️ 波段論點穩定性（最高紀律，凌駕單日盤面）
本分析為 2 週-1 個月以上波段定位，不做當沖。失效價未被觸及前，方向與
關鍵價位維持不變；每日重跑只更新「現價距失效價還有多遠」，禁止因單日
紅綠或漲跌改變方向或重設價位。禁止輸出「今日宜/不宜」這類當日結論。
```

- [ ] **Step 4: py_compile + 全測試**

Run: `python -m py_compile modules/ai_analyzer_v2.py && python -m pytest -q`
Expected: OK；pytest 全綠（127 passed）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(ai): analyze_market_only 波段對齊（spec §2，守不含操作建議邊界）

注入錨點 + 今日時機→波段定位 + 穩定鐵律；不加 entry/add 操作段。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `generate_personal_recommendation` 對齊

**Files:**
- Modify: `modules/ai_analyzer_v2.py`：`generate_personal_recommendation`（line 841-945）

- [ ] **Step 1: 注入鎖定錨點到 market_summary**

`ai_analyzer_v2.py` line 841-844。原文：

```python
    market_summary = (
        f"威科夫階段：{wyckoff_phase} | 風險係數：{risk_pct}%\n"
        f"關鍵支撐：{support or '--'} 元 | 關鍵壓力：{resistance or '--'} 元 | P&F目標：{target_pnf or '--'} 元"
    )

    _direction = phase_to_direction(wyckoff_phase)
```

改為（`_direction` 已知 → 直接算對應方向錨點）：

```python
    _direction = phase_to_direction(wyckoff_phase)

    from modules.candlestick import calc_swing_levels
    try:
        _cp = float(current_price)
    except (TypeError, ValueError):
        _cp = None
    _sl = calc_swing_levels(recent_bars or [], _direction, _cp)
    if _sl and _direction in ('long', 'short'):
        _ez = _sl['entry_zone']
        _tg = f"{_sl['target']:.2f}" if isinstance(_sl['target'], (int, float)) else '—'
        _swing_line = (
            f"\n【波段錨點（程式計算，禁止更改，價位須引用）】"
            f"失效/停損 {_sl['invalidation']:.2f} ｜ 加碼觸發 {_sl['add_trigger']:.2f} ｜ "
            f"進場區 {_ez[0]:.2f}~{_ez[1]:.2f} ｜ 波段目標 {_tg}"
        )
    elif _sl and _direction == 'neutral':
        _swing_line = (
            f"\n【波段錨點】無波段方向，區間 {_sl['range_low']:.2f}~"
            f"{_sl['range_high']:.2f}（突破上緣轉多/跌破下緣轉空，區間內不操作）"
        )
    else:
        _swing_line = "\n【波段錨點】資料不足，本期不給波段框架（誠實 > 錯誤）"

    market_summary = (
        f"威科夫階段：{wyckoff_phase} | 風險係數：{risk_pct}%\n"
        f"關鍵支撐：{support or '--'} 元 | 關鍵壓力：{resistance or '--'} 元 | P&F目標：{target_pnf or '--'} 元"
        f"{_swing_line}"
    )
```

- [ ] **Step 2: 模板標題去當沖化（4 處 replace）**

對 `ai_analyzer_v2.py` line 855-945 的 action_template 字串做以下精確字串替換（逐一）：

| 原字串 | 新字串 |
|--------|--------|
| `<h3>▶ 短線放空條件（1-5日）</h3>` | `<h3>▶ 波段放空框架（2週-1個月+）</h3>` |
| `<h3>▶ 短線介入條件（1-5日）</h3>` | `<h3>▶ 波段介入框架（2週-1個月+）</h3>` |
| `<p>（只選一個）<span class="short-term-title"><strong>立刻可入 / 等待確認 / 不建議進場</strong></span>` | `<p>（只選一個）<span class="short-term-title"><strong>可布局 / 等突破確認 / 條件未到不進場</strong></span>` |
| `<p>（只選一個）<span class="short-term-title"><strong>可伺機放空 / 等待確認 / 不建議放空</strong></span>` | `<p>（只選一個）<span class="short-term-title"><strong>可布局放空 / 等跌破確認 / 條件未到不放空</strong></span>` |
| `<h3>▶ 今日K棒提醒</h3>` | `<h3>▶ 盤面提醒（不構成當日進出依據）</h3>` |

（`▶ 今日K棒提醒` 在 short-holding 與 long-holding 兩模板各出現一次 → 用 `replace`/全域替換確保兩處都改。其餘各 1 處。）

- [ ] **Step 3: prompt 加穩定鐵律 + 引用錨點要求**

`ai_analyzer_v2.py` line 947-948。原文：

```python
    prompt = f"""你是台股操作顧問，提供具體、有數字、可執行的操作策略。
每個建議都必須有具體價格數字，絕不說「視情況而定」。
```

改為：

```python
    prompt = f"""你是台股操作顧問，提供具體、有數字、可執行的波段操作策略。
每個建議都必須有具體價格數字，絕不說「視情況而定」。
⚠️ 波段紀律：建議為 2 週-1 個月以上定位，不做當沖。所有價位必須引用
market_summary 中【波段錨點】的鎖定值，禁自行估算。失效價未破前論點
不變，禁因單日漲跌翻轉方向或重設價位，禁輸出「今日宜/不宜」當日結論。
```

- [ ] **Step 4: py_compile + 全測試**

Run: `python -m py_compile modules/ai_analyzer_v2.py && python -m pytest -q`
Expected: OK；pytest 全綠（127 passed）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(ai): generate_personal_recommendation 波段對齊（spec §3）

注入 calc_swing_levels 鎖定錨點到 market_summary；模板標題去當沖化；
prompt 加波段穩定鐵律 + 引用錨點要求。short禁加碼/neutral模板不動。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 本機 DB raw 推演驗證 + plan.md §二十三

依 CLAUDE.md「修改 AI 功能的紀律」：prompt 改動須先用 DB 真實 raw 在本機推演 cleanup/解析管道零退化，再讓用戶燒 token 重跑。

**Files:**
- Create: 臨時驗證腳本（驗證後刪除，不進 commit）
- Modify: `plan.md`（新增 §二十三）

- [ ] **Step 1: 撈 DB raw 跑 cleanup/解析管道**

建立臨時腳本 `verify_swing.py`（專案根目錄）：

```python
"""一次性：用 DB 既有 StockAnalysis raw 驗證解析端零退化（驗證後刪）"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from modules.database import SessionLocal
from modules.models import StockAnalysis
from modules.ai_analyzer_v2 import _clean_html_output, _parse_tagged

db = SessionLocal()
rows = (db.query(StockAnalysis)
        .filter(StockAnalysis.html_content.isnot(None))
        .order_by(StockAnalysis.analysis_date.desc())
        .limit(8).all())
for r in rows:
    raw = r.html_content
    cleaned = _clean_html_output(raw)
    rp = _parse_tagged(raw, 'RISK_PCT', None)
    sp = _parse_tagged(raw, 'SUPPORT', None)
    rs = _parse_tagged(raw, 'RESISTANCE', None)
    wp = _parse_tagged(raw, 'WYCKOFF_PHASE', None)
    dr = _parse_tagged(raw, 'DIRECTION', None)
    print(f"{r.symbol}: RISK={rp} SUP={sp} RES={rs} WY={wp} DIR={dr} "
          f"clean_len={len(cleaned)} has_html={'<' in cleaned}")
db.close()
```

Run: `python verify_swing.py`
Expected: 每支股印出 RISK/SUP/RES/WY/DIR 皆能解析（非全 None），證明 Task 2-4 未動第一行標記/解析端。若 DB 連線本機不可用（Flask deps 缺），改用 git diff 靜態證明：標記區（ai_analyzer_v2.py:372-378、491-503、775-785）與 `_parse_tagged`/`_clean_html_output` 函式體逐字未變。

- [ ] **Step 2: git diff 靜態確認標記/解析端未動**

Run: `git diff main -- modules/ai_analyzer_v2.py | grep -E "RISK_PCT:|SUPPORT:|RESISTANCE:|_parse_tagged|_clean_html_output"`
Expected: 無輸出（這些 token 不在 diff 的增刪行中）→ 證解析端零退化

- [ ] **Step 3: 刪臨時腳本**

```bash
rm -f verify_swing.py
```

- [ ] **Step 4: plan.md 新增 §二十三**

在 `plan.md` 末尾（§二十二 之後）追加：

```markdown

---

## 二十三、中長期波段框架 — 穩定論點 + 程式鎖定錨點（2026-05-19）

### 緣起
用戶 5/18 報表回饋：(1) 缺雙向支撐壓力（做多/做空各自停損點/加碼點）(2) 太短期翻來覆去「今天宜/不宜」(3) 不做當沖，要 2週-1個月波段。

### 根因
`ai_analyzer_v2.py:359/365/720` prompt 寫死短線(1-5日)/今日時機；支撐壓力 AI 每日推斷 → 漂移 → 論點漂移。

### 三骨架決策（用戶 2026-05-19 拍板）
| # | 決策 |
|---|------|
| D1 | 穩定論點 + 失效價位（失效未破論點不變）|
| D2 | 程式鎖定錨點（復用 candlestick.py，非 AI 推斷）|
| D3 | neutral → 誠實不操作 + 雙向條件觸發 |

方案 A：新增 `calc_swing_levels()`（純加性，復用 `_find_local_peaks/_troughs`+`calc_pnf_target`）+ 三函式注入錨點+波段框架取代短線段+穩定鐵律。零 DB schema、零經常性 AI 成本。

### 涉及
`candlestick.py`(+calc_swing_levels)、`ai_analyzer_v2.py`(+_dual_swing_block，analyze_stock_three_masters/analyze_market_only/generate_personal_recommendation)、`tests/test_swing_levels.py`。`analyze_market_only` 守「不含操作建議」邊界只做語言+錨點+鐵律。

### 驗證
pytest 127 全綠；DB raw 推演證標記/解析端零退化；⚠️ AI 行為須用戶重跑(~$0.6)驗 6 點（見 spec §4c）。
```

- [ ] **Step 5: Commit**

```bash
git add plan.md
git commit -m "docs: plan §二十三 中長期波段框架架構決策（spec 2026-05-19）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 驗證交付（用戶真實重跑）

⚠️ 此 Task 不由 worker 執行 — prompt 改動無法靜態證明 AI 遵守，須用戶 deploy 後燒 ~$0.6 重跑一鍵分析驗證。

驗收 6 點（spec §4c）：
1. 報表出現「波段操作框架（2週-1個月+）」，無「短期（1-5日）」/「今日時機」
2. long/short 各有明確失效(停損)+加碼觸發價，與 dynamic_block【波段操作錨點】鎖定值一致
3. neutral 股寫「無波段方向+區間+雙向 flip」，非「等回檔買進」
4. 個人建議去當沖化、價位與分析錨點一致
5. 連兩日重跑同股（失效未破）→ 方向與價位不變（翻來覆去根治實證）
6. 第一行結構化標記/pill/方向 badge 全正常

回滾：純 prompt + 加性 helper，無 migration → AI 不遵守則 revert 對應 commit，無資料污染。

---

## Self-Review（已執行）

- **Spec 覆蓋**：§1→Task1；§2→Task2(個股)+Task3(大盤)；§3→Task4(個人建議)+退化面 Task5；§4→各 Task pytest + Task5 DB推演 + Task6 用戶重跑。無缺口。
- **Placeholder 掃描**：prompt 內 `[錨點 invalidation]` 等為「給 AI 看的取值指示」非計畫 placeholder（AI 從 dynamic_block 鎖定值取代），刻意保留。無 TBD/TODO。
- **型別一致**：`calc_swing_levels` 回傳 key（`invalidation/add_trigger/entry_zone(tuple)/range_low/range_high/flip_long/flip_short/target/direction`）Task1 定義，Task2/4 消費名稱一致；`entry_zone` 為 `(下界,上界)` tuple，Task1 測試與 Task2/4 解包一致。
- **市場函式邊界**：Task3 明確不加操作段（守 line 692「不含操作建議」），與 spec §2 一致並加註說明，非矛盾。
