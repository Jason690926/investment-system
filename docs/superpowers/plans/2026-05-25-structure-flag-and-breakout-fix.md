# 結構閘漏洞 + 強勢突破門檻過嚴：實作計畫

> **For agentic workers:** 逐 Task 執行，每 Task 走 TDD（紅→綠→commit）。

**Goal:** 修兩個結構性 bug：(A) `_structure_flag`「結構轉折中」漏洞讓強勢上漲股被誤判（東捷 short 漲停穿停損）；(B) `_strong_breakout_state` 量門檻被自己拉高的均量打死（矽力/瑞軒突破前高卻被判「不宜追進」）。

**Architecture:** D1 改 `data_enricher.py`（`compute_monthly_structure` 加 2 欄位 + `_structure_flag` 加 2 參數及強勢上漲分支）；D2 改 `ai_analyzer_v2.py`（`_strong_breakout_state` 從 1 條件擴為 3 條件擇一）。兩個函式都是純函式 → TDD 直接。

**Tech Stack:** Python / pytest；spec：`docs/superpowers/specs/2026-05-25-structure-flag-and-breakout-fix-design.md`

---

## D1 — 結構閘加「強勢上漲否決」分支

### Task 1：`compute_monthly_structure` 新增 2 欄位 + `_structure_flag` 強勢上漲分支

**Files:**
- Modify: `modules/data_enricher.py`
- Test: `tests/test_monthly_structure.py`（追加）

- [ ] **Step 1: 寫失敗測試**（5 新 case）

```python
# 追加到 tests/test_monthly_structure.py
# ---------- 強勢上漲否決（2026-05-25, plan §三十 Bug A）----------
def test_structure_flag_close_strict_up_overrides_inflection():
    """東捷型：_hl_trend 因 lows 不嚴格升回「轉折」，但 close 嚴格上揚 → 結構未轉弱。"""
    completed = _mbars([
        (52.3, 57.5, 44.80, 48.85),  # 2 月陰，close=48.85
        (47.1, 77.6, 43.30, 63.30),  # 3 月陽，close=63.30
        (67.2, 104.0, 63.80, 104.0), # 4 月陽，close=104.0
    ])
    inprogress = [_bar(114, 143.5, 103.5, 120.5, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=132.5, ma60=58)
    assert r['monthly_structure'] == '轉折'
    assert r['monthly_close_strict_up_3'] is True
    assert r['structure_flag'] == '結構未轉弱'


def test_structure_flag_bull_count_6_overrides_inflection():
    """近 6 月陽月數 ≥ 4 強勢上漲：即使 _hl_trend 回「轉折」也判結構未轉弱。"""
    completed = _mbars([
        (10, 12, 8, 11),    # 陽
        (11, 14, 10, 13),   # 陽
        (13, 16, 11, 15),   # 陽
        (15, 14, 12, 13),   # 陰（close<open）讓 _hl_trend 不純升
        (13, 18, 11, 17),   # 陽
    ])
    inprogress = [_bar(17, 20, 16, 18, date='2026-06-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=18, ma60=10)
    assert r['monthly_bull_count_6'] >= 4
    assert r['structure_flag'] == '結構未轉弱'


def test_structure_flag_below_ma60_not_overridden_by_strong_up():
    """價在 MA60 之下：強勢上漲否決不可逆轉（仍判結構已轉弱）。"""
    completed = _mbars([
        (10, 12, 8, 9),     # 陰
        (9, 14, 8, 13),     # 陽
        (13, 16, 11, 15),   # 陽
    ])
    inprogress = [_bar(15, 17, 14, 16, date='2026-05-01')]
    # 價 16 < ma60 20 → 在下，必須仍是已轉弱
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=20)
    assert r['price_vs_ma60'] == '在下'
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_monthly_structure_close_strict_up_3_field():
    """compute_monthly_structure 回 dict 含 monthly_close_strict_up_3。"""
    completed = _mbars([
        (10, 12, 8, 11),
        (11, 14, 10, 13),
        (13, 16, 11, 15),
    ])
    inprogress = [_bar(15, 17, 14, 16, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=10)
    assert r['monthly_close_strict_up_3'] is True


def test_compute_monthly_structure_bull_count_6_field():
    """compute_monthly_structure 回 dict 含 monthly_bull_count_6。"""
    completed = _mbars([
        (10, 12, 8, 11),
        (11, 14, 10, 13),
        (13, 14, 12, 12),  # 陰
    ])
    inprogress = [_bar(12, 15, 11, 14, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=14, ma60=10)
    assert r['monthly_bull_count_6'] == 2  # 2 個陽月（不含進行中）
```

- [ ] **Step 2: 跑測試確認失敗** — `python -m pytest tests/test_monthly_structure.py -q`，預期 5 fail（新欄位不存在 / 旗標仍走原邏輯）。

- [ ] **Step 3: 實作 `compute_monthly_structure` 加欄位**

修改 `modules/data_enricher.py` `compute_monthly_structure`：

```python
# 在原 result dict 加兩個欄位（預設值）
result = {
    'monthly_structure':       '資料不足',
    'consecutive_bear_months': 0,
    'drawdown_from_peak':      None,
    'price_vs_ma60':           '未知',
    'structure_flag':          '資料不足',
    'weekly_momentum':         '資料不足',
    'weekly_hold_support':     False,
    'monthly_close_strict_up_3': False,  # 新增
    'monthly_bull_count_6':     0,         # 新增
}

# 在「月K：需 >= 4 根」區塊內、計算月結構之後加：
if monthly_bars and len(monthly_bars) >= 4:
    completed = monthly_bars[:-1]
    result['monthly_structure']       = _hl_trend(completed[-3:])
    result['consecutive_bear_months'] = _consecutive_bear(completed)
    closes = [float(b['close']) for b in completed]
    peak = max(closes) if closes else 0
    if peak > 0 and price is not None:
        result['drawdown_from_peak'] = round((peak - float(price)) / peak * 100, 1)
    # 強勢上漲否決指標（2026-05-25, plan §三十 Bug A）
    if len(completed) >= 3:
        c3 = closes[-3:]
        result['monthly_close_strict_up_3'] = (c3[0] < c3[1] < c3[2])
    result['monthly_bull_count_6'] = sum(
        1 for b in completed[-6:] if float(b['close']) > float(b['open'])
    )
```

- [ ] **Step 4: 實作 `_structure_flag` 加分支**

```python
def _structure_flag(monthly_structure: str, price_vs_ma60: str,
                    consecutive_bear: int,
                    close_strict_up_3: bool = False,
                    bull_count_6: int = 0) -> str:
    """綜合 → 結構旗標。判定順序：已轉弱 > 未轉弱（含強勢上漲否決）> 轉折中。

    強勢上漲否決（2026-05-25, plan §三十 Bug A）：即使 _hl_trend 因 lows
    不嚴格升回「轉折」，只要 close 嚴格上揚或近 6 月陽月數 ≥ 4，仍視為
    結構未轉弱（東捷型強勢起漲股）。
    """
    if monthly_structure == '資料不足':
        return '資料不足'
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    if price_vs_ma60 == '在上' and consecutive_bear <= 1 and (
        monthly_structure in ('升', '橫')
        or close_strict_up_3
        or bull_count_6 >= 4
    ):
        return '結構未轉弱'
    return '結構轉折中'
```

並修改 `compute_monthly_structure` 內呼叫 `_structure_flag` 的地方，傳入新參數：

```python
result['structure_flag'] = _structure_flag(
    result['monthly_structure'],
    result['price_vs_ma60'],
    result['consecutive_bear_months'],
    close_strict_up_3=result['monthly_close_strict_up_3'],
    bull_count_6=result['monthly_bull_count_6'],
)
```

- [ ] **Step 5: 跑測試確認通過** — `python -m pytest tests/test_monthly_structure.py -q`，預期 5 新 + 8 原 = 13 passed。

- [ ] **Step 6: commit D1**
  ```
  feat(structure): _structure_flag 加強勢上漲否決分支 (Bug A, plan §三十)
  ```

---

## D2 — 強勢突破狀態改 3 條件擇一

### Task 2：`_strong_breakout_state` 新增條件 B + C

**Files:**
- Modify: `modules/ai_analyzer_v2.py`
- Test: `tests/test_strong_breakout.py`（追加）

- [ ] **Step 1: 寫失敗測試**（5 新 case）

```python
# 追加到 tests/test_strong_breakout.py
# ---------- 條件 B：突破後續強勢（2026-05-25, plan §三十 Bug B） ----------
def _matrix_daily(closes, vols=None):
    """給 close list 自動補成 daily_bars（open/high/low 算簡單）。"""
    if vols is None:
        vols = [1000] * len(closes)
    out = []
    for i, c in enumerate(closes):
        out.append({
            'date': f'2026-05-{i+1:02d}',
            'open': c - 0.5, 'high': c + 0.5, 'low': c - 1,
            'close': c, 'volume_zhang': vols[i]
        })
    return out


def test_breakout_true_via_condition_b_continuous_high_close():
    """條件 B：突破 range_high × 1.05 且 近 5 日 close 都 > range_high。"""
    # 40 根日K：前 35 根構成 range_high≈30，後 5 根 close 都 > 30 且最後一根 > 31.5
    closes = list(range(10, 30)) + [25, 22, 28, 30, 27,   # 谷
                                     32, 33, 34, 35, 36]   # 最後 5 根都 > 30
    daily = _matrix_daily(closes)
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # 量不過 A，但 close 嚴格站上 range_high
    assert _strong_breakout_state(ed, price_f=36) is True


def test_breakout_false_when_recent_close_dips_below_range_high():
    """條件 B 失效：近 5 日有任一 close ≤ range_high → 不成立。"""
    closes = list(range(10, 30)) + [25, 22, 28, 30, 27,
                                     29, 33, 34, 35, 36]   # 5 日前的第 1 根 29 < 30
    daily = _matrix_daily(closes)
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A: 量不過、C: 漲幅僅 36/35-1=2.86% 不過 → 應 False
    assert _strong_breakout_state(ed, price_f=36) is False


# ---------- 條件 C：一字漲停型突破（2026-05-25, plan §三十 Bug B） ----------
def test_breakout_true_via_condition_c_one_word_limit_up():
    """條件 C：今日漲幅 9.8% 且 close=high（瑞軒 5/22 型）。"""
    closes = list(range(10, 35))
    daily = _matrix_daily(closes)
    # 最後一根改為跳空一字漲停：昨日 close=33，今日漲幅 9.85% → 36.25
    # close=high=36.25, low=open=36.25（一字）
    daily[-1] = {
        'date': '2026-05-25',
        'open': 36.25, 'high': 36.25, 'low': 36.25, 'close': 36.25,
        'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A 量不過、B 近 5 日 close 都過 range_high 但取決於 range_high；
    # 重點是 C 條件單獨成立
    assert _strong_breakout_state(ed, price_f=36.25) is True


def test_breakout_false_when_limit_up_but_below_range_high():
    """漲停但價未過 range_high → 不誤判反彈。"""
    closes = [10, 30, 28, 25, 22, 20, 18, 16] + [10] * 10 + [11, 12, 13, 14]   # range_high 在前
    daily = _matrix_daily(closes)
    # 最後一根改漲停：昨日 14，今日 15.4
    daily[-1] = {
        'date': '2026-05-25',
        'open': 15.4, 'high': 15.4, 'low': 15.4, 'close': 15.4,
        'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # range_high≈30，現價 15.4 << 30，所有條件都不過
    assert _strong_breakout_state(ed, price_f=15.4) is False


def test_breakout_false_when_close_not_at_high():
    """漲幅夠但 close < high × 0.99（有顯著上影）→ 條件 C 不成立。"""
    closes = list(range(10, 35))
    daily = _matrix_daily(closes)
    # 最後一根：昨日 33，今日漲幅 9.85% 至 36.25，但 high=38 → close/high=0.954 < 0.99
    daily[-1] = {
        'date': '2026-05-25',
        'open': 34, 'high': 38, 'low': 34, 'close': 36.25,
        'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A 量不過、B 取決於 range_high、C 因 close<high×0.99 不過
    # 假設 range_high≈30，C 不過即可（B 也許過，這 case 想 isolate C）
    # 簡化：手動把前 N 根 close 拉低讓 range_high 在更早期
    daily[10] = {**daily[10], 'high': 100, 'close': 50}   # 強制造一個歷史高峰=100
    ed['daily_bars'] = daily
    assert _strong_breakout_state(ed, price_f=36.25) is False
```

- [ ] **Step 2: 跑測試確認失敗** — `python -m pytest tests/test_strong_breakout.py -q`，預期 5 fail。

- [ ] **Step 3: 實作 3 條件擇一**

修改 `modules/ai_analyzer_v2.py` `_strong_breakout_state`：

```python
def _strong_breakout_state(enriched_data: dict, price_f) -> bool:
    """三條件擇一即視為強勢突破（2026-05-25, plan §三十 Bug B）：
    A. 量價齊揚：現價 > range_high 且 今日量 ≥ 5日均×1.5（原條件）
    B. 突破後續強勢：現價 > range_high × 1.05 且 近 5 日收盤都 > range_high
    C. 一字漲停型：現價 > range_high 且 漲幅 ≥ 9% 且 close ≥ high × 0.99
    """
    if price_f is None:
        return False
    from modules.candlestick import calc_swing_levels
    sl = calc_swing_levels(enriched_data.get('daily_bars', []), 'long', price_f)
    if not sl or sl.get('range_high') is None:
        return False
    try:
        range_high = float(sl['range_high'])
        price = float(price_f)
        daily_bars = enriched_data.get('daily_bars', [])

        # A. 量價齊揚
        vt = enriched_data.get('volume_zhang')
        v5 = enriched_data.get('volume_5d_avg_zhang')
        if (price > range_high and vt is not None and v5 not in (None, '--', 0)
                and float(vt) >= float(v5) * 1.5):
            return True

        # B. 突破後續強勢（近 5 日 close 都站高 + 突破≥5%）
        if price > range_high * 1.05 and len(daily_bars) >= 5:
            recent_5_closes = [float(b['close']) for b in daily_bars[-5:]]
            if all(c > range_high for c in recent_5_closes):
                return True

        # C. 一字漲停型（漲幅≥9% + close 接近 high）
        if price > range_high and len(daily_bars) >= 2:
            today_close = float(daily_bars[-1]['close'])
            today_high = float(daily_bars[-1]['high'])
            yest_close = float(daily_bars[-2]['close'])
            if (yest_close > 0
                    and (today_close - yest_close) / yest_close >= 0.09
                    and today_close >= today_high * 0.99):
                return True
        return False
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        return False
```

- [ ] **Step 4: 跑測試確認通過** — `python -m pytest tests/test_strong_breakout.py -q`，預期 5 新 + 5 原 = 10 passed。

- [ ] **Step 5: commit D2**
  ```
  feat(breakout): _strong_breakout_state 改 3 條件擇一 (Bug B, plan §三十)
  ```

---

## 最後驗證

- [ ] **Step F1: 跑全 pytest** — `python -m pytest tests/ -q`，預期 239 + 10 = 249 passed。
- [ ] **Step F2: py_compile**
  - `python -m py_compile modules/data_enricher.py`
  - `python -m py_compile modules/ai_analyzer_v2.py`
- [ ] **Step F3: 更新 CLAUDE.md 進度快照** — 把 §三十 修法寫進當前進度，標 D1+D2 commit hash。
- [ ] **Step F4: push origin/main** → Render auto-deploy。
- [ ] **Step F5: deploy 後燒 ~$0.6 重跑 5/22 報表** + 對照 5/25 收盤實機驗：
  1. 東捷 8064 結構旗標 = 「結構未轉弱」，方向 = long
  2. 矽力 6415 = 「強勢突破成立」(條件 B 觸發)
  3. 瑞軒 2489 = 「強勢突破成立」(條件 C 觸發)
  4. 合晶 6182 = 「強勢突破成立」(條件 A 觸發，不退化)
  5. 其他 10 支 long 股無誤判（旗標與方向不變）

## 回滾策略

D1 / D2 各自純加性：
- D1: `compute_monthly_structure` 加 dict 欄位向後相容；`_structure_flag` 簽名加 default 參數
- D2: `_strong_breakout_state` 加並聯條件，原條件 A 行為 byte-identical

任一有問題 `git revert <commit>` 即可獨立回滾，互不影響。
