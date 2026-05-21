# 威科夫派發判定門檻（結構閘）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 分析 prompt 加一道程式計算的「結構閘」，月線結構未轉弱時硬禁 AI 標派發/再派發/下跌，修系統性偏空。

**Architecture:** `data_enricher.py` 新增 `compute_monthly_structure()` 從 12 月K + 26 週K + MA60 算出【月線結構客觀事實】dict；`ai_analyzer_v2.py` 新增 `_structure_block()` 把它格式化注入兩個市場分析函式的 dynamic prompt，並在兩個 static prompt 加結構閘規則。純加性變更，無 DB/migration。

**Tech Stack:** Python 3.12、pytest、無新依賴。

**Spec:** `docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md`

---

## 檔案結構

| 檔案 | 責任 | 變更 |
|------|------|------|
| `modules/data_enricher.py` | 資料擴充層 | 新增 `_hl_trend()`、`_consecutive_bear()`、`compute_monthly_structure()` |
| `modules/ai_analyzer_v2.py` | AI prompt 組裝 | 新增 import + `_structure_block()`；改 2 個函式的 dynamic/static block |
| `tests/test_monthly_structure.py` | 測試 | 新建 |

---

## Task 1: 結構判定純函式 `_hl_trend` + `_consecutive_bear`

**Files:**
- Modify: `modules/data_enricher.py`（接在 `_ohlcv_to_list` 之後，約 line 64 後）
- Test: `tests/test_monthly_structure.py`（新建）

- [ ] **Step 1: Write the failing test**

建立 `tests/test_monthly_structure.py`：

```python
"""威科夫結構閘（2026-05-21）— 月線結構客觀事實計算測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.data_enricher import _hl_trend, _consecutive_bear


def _bar(o, h, l, c, date='2026-01-01', vol=1000):
    return {'date': date, 'open': o, 'high': h, 'low': l,
            'close': c, 'volume_zhang': vol}


# ---------- _hl_trend ----------
def test_hl_trend_rising():
    bars = [_bar(10, 12, 8, 11), _bar(11, 15, 10, 14), _bar(14, 18, 13, 17)]
    assert _hl_trend(bars) == '升'


def test_hl_trend_falling():
    bars = [_bar(17, 18, 13, 14), _bar(14, 15, 10, 11), _bar(11, 12, 8, 9)]
    assert _hl_trend(bars) == '跌'


def test_hl_trend_inflection():
    # 高點墊高、低點下降 → 轉折
    bars = [_bar(10, 12, 9, 11), _bar(11, 14, 8, 10), _bar(10, 16, 7, 12)]
    assert _hl_trend(bars) == '轉折'


def test_hl_trend_sideways():
    # 高點 12,11,13 與低點 8,9,7 皆非單調 → 橫
    bars = [_bar(10, 12, 8, 11), _bar(11, 11, 9, 10), _bar(10, 13, 7, 12)]
    assert _hl_trend(bars) == '橫'


def test_hl_trend_insufficient():
    assert _hl_trend([_bar(10, 12, 8, 11)]) == '資料不足'


# ---------- _consecutive_bear ----------
def test_consecutive_bear_counts_from_newest():
    bars = [_bar(10, 12, 8, 11), _bar(11, 13, 9, 9), _bar(9, 10, 6, 7)]
    # 最新兩根 close<open → 2
    assert _consecutive_bear(bars) == 2


def test_consecutive_bear_stops_at_bull():
    bars = [_bar(10, 12, 8, 9), _bar(9, 13, 8, 12), _bar(12, 14, 9, 10)]
    # 最新一根陰、前一根陽 → 1
    assert _consecutive_bear(bars) == 1


def test_consecutive_bear_zero_when_newest_bull():
    bars = [_bar(10, 12, 8, 9), _bar(9, 13, 8, 12)]
    assert _consecutive_bear(bars) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: FAIL — `ImportError: cannot import name '_hl_trend'`

- [ ] **Step 3: Write minimal implementation**

在 `modules/data_enricher.py` 的 `_ohlcv_to_list` 函式之後加入：

```python
def _hl_trend(bars: list) -> str:
    """3 根 K 棒的高低點趨勢 → 升 / 跌 / 轉折 / 橫。bars 由舊到新。"""
    if not bars or len(bars) < 3:
        return '資料不足'
    h = [float(b['high']) for b in bars]
    l = [float(b['low']) for b in bars]
    highs_up = h[2] >= h[1] >= h[0]
    highs_dn = h[2] <= h[1] <= h[0]
    lows_up  = l[2] >= l[1] >= l[0]
    lows_dn  = l[2] <= l[1] <= l[0]
    if highs_up and lows_up:
        return '升'
    if highs_dn and lows_dn:
        return '跌'
    if highs_up or highs_dn or lows_up or lows_dn:
        return '轉折'
    return '橫'


def _consecutive_bear(bars: list) -> int:
    """從最新一根往回數，連續收陰（close<open）的根數。"""
    cnt = 0
    for b in reversed(bars):
        if float(b['close']) < float(b['open']):
            cnt += 1
        else:
            break
    return cnt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS（8 個 test 全綠）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_monthly_structure.py
git commit -m "feat(structure): 結構判定純函式 _hl_trend + _consecutive_bear

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `compute_monthly_structure` 主函式

**Files:**
- Modify: `modules/data_enricher.py`（接在 `_consecutive_bear` 之後）
- Test: `tests/test_monthly_structure.py`（追加）

- [ ] **Step 1: Write the failing test**

在 `tests/test_monthly_structure.py` 末尾追加：

```python
# ---------- compute_monthly_structure ----------
from modules.data_enricher import compute_monthly_structure


def _mbars(specs):
    """specs: list of (o,h,l,c)；自動補日期。回傳月K bar list。"""
    out = []
    for i, (o, h, l, c) in enumerate(specs):
        out.append(_bar(o, h, l, c, date=f'2026-{i+1:02d}-01'))
    return out


def test_compute_jingxinke_uptrend_pullback_not_weak():
    """臻鼎型：月K升、僅末根收陰、現價在 MA60 上 → 結構未轉弱。"""
    # 3 根已收盤（升、末根陰）+ 1 根進行中
    completed = _mbars([
        (200, 234, 157, 220),   # 陽
        (300, 421, 213, 400),   # 陽
        (429, 471, 372, 408),   # 陰（close<open）
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300)
    assert r['monthly_structure'] == '升'
    assert r['consecutive_bear_months'] == 1
    assert r['price_vs_ma60'] == '在上'
    assert r['structure_flag'] == '結構未轉弱'


def test_compute_downtrend_is_weak():
    """晶心科型：月K跌、現價跌破 MA60 → 結構已轉弱。"""
    completed = _mbars([
        (260, 270, 230, 240),
        (240, 245, 210, 219),
        (235, 240, 170, 200),
    ])
    inprogress = [_bar(214, 221, 213, 216, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=216, ma60=250)
    assert r['monthly_structure'] == '跌'
    assert r['price_vs_ma60'] == '在下'
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_two_bear_months_forces_weak():
    """月K升、現價在 MA60 上，但連 2 月陰 → 仍判結構已轉弱。"""
    completed = _mbars([
        (200, 234, 157, 230),   # 陽
        (300, 421, 213, 280),   # 陰
        (429, 471, 372, 408),   # 陰
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300)
    assert r['consecutive_bear_months'] == 2
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_excludes_inprogress_month():
    """進行中月份（最後一根）不參與月K結構判定。"""
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    # 進行中月份是暴跌，但應被排除
    inprogress = [_bar(408, 410, 100, 110, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=110, ma60=300)
    assert r['monthly_structure'] == '升'   # 仍用已收盤 3 根


def test_compute_weekly_hold_support_true():
    """週K收盤 401/401/408.5（離散<3%、墊高）→ 守穩支撐=是。"""
    wcompleted = [
        _bar(400, 410, 390, 401, date='2026-05-03'),
        _bar(401, 405, 396, 401, date='2026-05-10'),
        _bar(401, 415, 372, 408.5, date='2026-05-17'),
    ]
    winprogress = [_bar(408, 420, 405, 415, date='2026-05-20')]
    r = compute_monthly_structure([], wcompleted + winprogress, price=415, ma60=None)
    assert r['weekly_hold_support'] is True


def test_compute_weekly_hold_support_false_when_declining():
    wcompleted = [
        _bar(420, 425, 410, 420, date='2026-05-03'),
        _bar(415, 418, 400, 405, date='2026-05-10'),
        _bar(400, 405, 380, 385, date='2026-05-17'),
    ]
    winprogress = [_bar(385, 390, 375, 380, date='2026-05-20')]
    r = compute_monthly_structure([], wcompleted + winprogress, price=380, ma60=None)
    assert r['weekly_hold_support'] is False


def test_compute_insufficient_data():
    r = compute_monthly_structure([], [], price=100, ma60=90)
    assert r['monthly_structure'] == '資料不足'
    assert r['structure_flag'] == '資料不足'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_monthly_structure'`

- [ ] **Step 3: Write minimal implementation**

在 `modules/data_enricher.py` 的 `_consecutive_bear` 之後加入：

```python
def _structure_flag(monthly_structure: str, price_vs_ma60: str,
                    consecutive_bear: int) -> str:
    """綜合三項 → 結構旗標。判定順序：已轉弱 > 未轉弱 > 轉折中。"""
    if monthly_structure == '資料不足':
        return '資料不足'
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    if (price_vs_ma60 == '在上' and monthly_structure in ('升', '橫')
            and consecutive_bear <= 1):
        return '結構未轉弱'
    return '結構轉折中'


def compute_monthly_structure(monthly_bars: list, weekly_bars: list,
                              price, ma60) -> dict:
    """從 12 月K + 26 週K + MA60 算出【月線結構客觀事實】。

    spec: docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md
    月K/週K 的最後一根視為進行中，結構一律用其前 3 根已收盤 bar。
    """
    result = {
        'monthly_structure':       '資料不足',
        'consecutive_bear_months': 0,
        'drawdown_from_peak':      None,
        'price_vs_ma60':           '未知',
        'structure_flag':          '資料不足',
        'weekly_momentum':         '資料不足',
        'weekly_hold_support':     False,
    }

    # 月K：需 >= 4 根（3 已收盤 + 1 進行中）
    if monthly_bars and len(monthly_bars) >= 4:
        completed = monthly_bars[:-1]
        result['monthly_structure']       = _hl_trend(completed[-3:])
        result['consecutive_bear_months'] = _consecutive_bear(completed)
        closes = [float(b['close']) for b in completed]
        peak = max(closes) if closes else 0
        if peak > 0 and price is not None:
            result['drawdown_from_peak'] = round((peak - float(price)) / peak * 100, 1)

    # 現價 vs 季線 MA60
    if price is not None and ma60:
        result['price_vs_ma60'] = '在上' if float(price) >= float(ma60) else '在下'

    # 週K 動能（唯讀）
    if weekly_bars and len(weekly_bars) >= 4:
        wcompleted = weekly_bars[:-1]
        w3 = wcompleted[-3:]
        result['weekly_momentum'] = _hl_trend(w3)
        wc = [float(b['close']) for b in w3]
        if len(wc) == 3 and min(wc) > 0:
            dispersion = (max(wc) - min(wc)) / (sum(wc) / 3)
            result['weekly_hold_support'] = bool(
                dispersion < 0.03 and wc[2] >= wc[1] and wc[2] >= wc[0]
            )

    result['structure_flag'] = _structure_flag(
        result['monthly_structure'],
        result['price_vs_ma60'],
        result['consecutive_bear_months'],
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS（全 15 個 test 綠）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_monthly_structure.py
git commit -m "feat(structure): compute_monthly_structure 主函式 + 結構旗標

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `_structure_block` 格式化函式（ai_analyzer_v2.py）

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（import 區 line 11 後；helper 接在 `_oversold_warning_block` 之後，約 line 459 前）
- Test: `tests/test_monthly_structure.py`（追加）

- [ ] **Step 1: Write the failing test**

在 `tests/test_monthly_structure.py` 末尾追加：

```python
# ---------- _structure_block 格式化 ----------
from modules.ai_analyzer_v2 import _structure_block


def test_structure_block_not_weak_contains_ban():
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    enriched = {'monthly_bars': completed + inprogress, 'weekly_bars': [],
                'ma60': 300}
    block = _structure_block(enriched, 439)
    assert '月線結構客觀事實' in block
    assert '結構未轉弱' in block
    assert '禁止標派發' in block


def test_structure_block_empty_when_insufficient():
    enriched = {'monthly_bars': [], 'weekly_bars': [], 'ma60': None}
    assert _structure_block(enriched, 100) == ''
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monthly_structure.py -k structure_block -v`
Expected: FAIL — `ImportError: cannot import name '_structure_block'`

- [ ] **Step 3: Write minimal implementation**

在 `modules/ai_analyzer_v2.py` 的 import 區（line 11 `from modules.candlestick ...` 之後）加一行：

```python
from modules.data_enricher import compute_monthly_structure
```

在 `_oversold_warning_block` 函式結束後、`analyze_stock_three_masters` 之前加入：

```python
def _structure_block(enriched_data: dict, price_f) -> str:
    """【月線結構客觀事實】prompt 區塊（結構閘）。

    spec: docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md
    資料不足回 '' （誠實 > 錯誤）。
    """
    ms = compute_monthly_structure(
        enriched_data.get('monthly_bars', []),
        enriched_data.get('weekly_bars', []),
        price_f,
        enriched_data.get('ma60'),
    )
    flag = ms['structure_flag']
    if flag == '資料不足':
        return ''
    gate_hint = {
        '結構未轉弱': '→ 禁止標派發/再派發/下跌，相位只能在 積累/上漲/再積累/不明',
        '結構轉折中': '→ 可標派發，但須在分析附具體量價證據',
        '結構已轉弱': '→ 允許標空方相位（仍須量價證據佐證）',
    }.get(flag, '')
    dd = ms['drawdown_from_peak']
    dd_txt = f'{dd:+.1f}%' if dd is not None else '—'
    hold = '是' if ms['weekly_hold_support'] else '否'
    return (
        "【月線結構客觀事實】（程式計算，禁止 AI 推翻）\n"
        f"- 月K結構（近3根已收盤）：{ms['monthly_structure']}\n"
        f"- 連續月陰線：{ms['consecutive_bear_months']}\n"
        f"- 距峰值回落：{dd_txt}\n"
        f"- 現價 vs 季線MA60：{ms['price_vs_ma60']}\n"
        f"- 結構旗標：{flag} {gate_hint}\n"
        f"- 週K近期動能（唯讀，供時機判斷）：{ms['weekly_momentum']}"
        f" ｜ 守穩支撐：{hold}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS（全 17 個 test 綠）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_monthly_structure.py
git commit -m "feat(structure): _structure_block 格式化結構閘 prompt 區塊

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 注入 `analyze_stock_three_masters`（dynamic + static 結構閘）

**Files:**
- Modify: `modules/ai_analyzer_v2.py` — `analyze_stock_three_masters` 函式（dynamic_block 約 line 676、static_block 結構方向判定段約 line 571-587）

- [ ] **Step 1: dynamic_block 注入結構區塊**

在 `analyze_stock_three_masters` 內，找到 `_swing_block = _dual_swing_block(enriched_data, _price_f)` 那行（約 line 525），其下一行加入：

```python
    _structure_block_text = _structure_block(enriched_data, _price_f)
```

接著找到 `dynamic_block` 的這段（約 line 676-678）：

```python
{_swing_block}

{monthly_text}
```

改成：

```python
{_swing_block}

{_structure_block_text}

{monthly_text}
```

- [ ] **Step 2: static_block 加結構閘規則**

在 `analyze_stock_three_masters` 的 `static_block` 中，找到「結構方向判定」段尾端這行（約 line 581）：

```
- 若上方資料區出現【短期超賣警示】或【進場區距現價過近】，**優先標 neutral**
```

在其**下方**插入一段空行後加入：

```
⚠️ **結構閘（硬護欄，最優先，凌駕一切短線訊號）**：下方股票資料含【月線結構客觀事實】，其「結構旗標」由程式計算，**禁止 AI 推翻**：
- 結構旗標=`結構未轉弱` → **禁止**標派發/再派發/下跌，WYCKOFF_PHASE 只能在 積累/上漲/再積累/不明 之中選
- 結構旗標=`結構轉折中` → 可標派發，但須在「一、威科夫骨幹分析」列出具體派發訊號（高位量增不漲／高位放量收長黑或長上影／跌破前波明顯低點伴隨放量），**不得僅憑單月收陰+量縮**判派發
- 結構旗標=`結構已轉弱` → 允許標空方相位，仍須量價證據佐證
⚠️ **正向型態**：若【月線結構客觀事實】「守穩支撐=是」且回測時量縮、反彈時量增 → 屬吸籌/再積累的次級測試(SOT)，偏多，禁標派發。
```

- [ ] **Step 3: 驗證語法**

Run: `python -m py_compile modules/ai_analyzer_v2.py`
Expected: 無輸出（成功）

- [ ] **Step 4: 確認注入字串存在**

Run: `python -c "import modules.ai_analyzer_v2 as m; import inspect; src=inspect.getsource(m.analyze_stock_three_masters); print('OK' if '_structure_block_text' in src and '結構閘' in src else 'MISSING')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(structure): analyze_stock_three_masters 注入結構閘

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 注入 `analyze_market_only`（dynamic + static 結構閘）+ 全量測試

**Files:**
- Modify: `modules/ai_analyzer_v2.py` — `analyze_market_only` 函式（dynamic_block 約 line 1022、static_block 結構方向判定段約 line 873-878）

- [ ] **Step 1: dynamic_block 注入結構區塊**

在 `analyze_market_only` 內，找到 `_swing_block = _dual_swing_block(enriched_data, _price_f)` 那行（約 line 838），其下一行加入：

```python
    _structure_block_text = _structure_block(enriched_data, _price_f)
```

接著找到該函式 `dynamic_block` 的這段（約 line 1020-1022）：

```python
{_swing_block}

{monthly_text}
```

改成：

```python
{_swing_block}

{_structure_block_text}

{monthly_text}
```

- [ ] **Step 2: static_block 加結構閘規則 + 移除義務化空方框架**

在 `analyze_market_only` 的 `static_block` 中，找到「結構方向判定」段這行（約 line 878）：

```
⚠️ 派發/下跌相位禁止只寫「不宜行動」，必須給出空方操作框架（賣空進場價、回補停損、下行目標）。
```

將該行**整行取代**為：

```
⚠️ 派發/下跌相位若已確立，須給出空方操作框架（賣空進場價、回補停損、下行目標）；但相位判定須先過下方結構閘。

⚠️ **結構閘（硬護欄，最優先，凌駕一切短線訊號）**：下方股票資料含【月線結構客觀事實】，其「結構旗標」由程式計算，**禁止 AI 推翻**：
- 結構旗標=`結構未轉弱` → **禁止**標派發/再派發/下跌，WYCKOFF_PHASE 只能在 積累/上漲/再積累/不明 之中選
- 結構旗標=`結構轉折中` → 可標派發，但須在「一、威科夫骨幹分析」列出具體派發訊號（高位量增不漲／高位放量收長黑或長上影／跌破前波明顯低點伴隨放量），**不得僅憑單月收陰+量縮**判派發
- 結構旗標=`結構已轉弱` → 允許標空方相位，仍須量價證據佐證
⚠️ **正向型態**：若【月線結構客觀事實】「守穩支撐=是」且回測時量縮、反彈時量增 → 屬吸籌/再積累的次級測試(SOT)，偏多，禁標派發。
```

- [ ] **Step 3: 驗證語法**

Run: `python -m py_compile modules/ai_analyzer_v2.py modules/data_enricher.py`
Expected: 無輸出（成功）

- [ ] **Step 4: 確認注入字串存在**

Run: `python -c "import modules.ai_analyzer_v2 as m; import inspect; src=inspect.getsource(m.analyze_market_only); print('OK' if '_structure_block_text' in src and '結構閘' in src else 'MISSING')"`
Expected: `OK`

- [ ] **Step 5: 全量測試**

Run: `python -m pytest -q`
Expected: PASS — 既有 158 + 新增 17 = 175 全綠

- [ ] **Step 6: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "feat(structure): analyze_market_only 注入結構閘 + 解除義務化空方框架

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 驗收標準（部署後人工驗，非本計畫自動範圍）

1. ✅ `python -m pytest -q` 全綠（177）。
2. ⚠️ 使用者 deploy 後燒 ~$0.6 重跑一鍵分析：
   - 臻鼎、合晶、瑞軒、南亞科（月K結構=升、現價在 MA60 上）**不再出現「派發/再派發」字樣**。
   - 晶心科、創惟（真實下跌結構）**仍可標空方相位** → 驗證閘門不對稱、未誤殺真派發。
   - 報表凡【月線結構客觀事實】結構旗標=`結構未轉弱` 的股，WYCKOFF_PHASE 不為派發/再派發/下跌。

## 回滾

純加性變更，無 DB/migration。若 AI 不遵守結構閘，`git revert` Task 4 / Task 5 的 commit 即恢復原 prompt；helper 保留不影響其他流程。
