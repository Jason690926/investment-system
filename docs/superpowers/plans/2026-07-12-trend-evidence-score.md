# 趨勢判斷加權證據評分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `_structure_flag()` 的證據層判斷從「疊加布林 OR」改成「加權評分 + 門檻」，否決層完全不動；新增均線排列與週K動能兩個已算出但未使用的訊號；附帶修 `_apply_structure_safety_net` 的 short 方向鏡像防護缺口。

**Architecture:** 兩階段設計。Stage 1（否決層）逐字保留。Stage 2 新增純函式 `_trend_evidence_score()` 計算加權分數，四個既有觸發條件權重與門檻相等（1.5=1.5）保證零退化，兩個新訊號（均線多頭排列 +1.0、週K動能升/橫 +0.5/+0.2）權重恆低於門檻、只加分不扣分。對外 `structure_flag` 三態字串介面完全不變。

**Tech Stack:** Python 3、pytest（TDD，測試先行）。

**Spec:** `docs/superpowers/specs/2026-07-12-trend-evidence-score-design.md`

---

## Task 1: `_trend_evidence_score()` 純函式

**Files:**
- Modify: `modules/data_enricher.py`（在 `_structure_flag` 定義前新增函式，約第 204 行前）
- Test: `tests/test_monthly_structure.py`（在檔案結尾新增一個測試區塊）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_monthly_structure.py` 檔案結尾（第 303 行之後）加入：

```python
# ---------- _trend_evidence_score（2026-07-12, plan §三十九）----------
from modules.data_enricher import _trend_evidence_score


def test_trend_evidence_score_monthly_up_alone_reaches_threshold():
    assert _trend_evidence_score(monthly_structure='升') == 1.5


def test_trend_evidence_score_monthly_sideways_alone_reaches_threshold():
    assert _trend_evidence_score(monthly_structure='橫') == 1.5


def test_trend_evidence_score_close_strict_up_alone_reaches_threshold():
    assert _trend_evidence_score(monthly_structure='轉折', close_strict_up_3=True) == 1.5


def test_trend_evidence_score_bull_count_alone_reaches_threshold():
    assert _trend_evidence_score(monthly_structure='轉折', bull_count_6=4) == 1.5


def test_trend_evidence_score_bull_count_below_4_no_score():
    assert _trend_evidence_score(monthly_structure='轉折', bull_count_6=3) == 0.0


def test_trend_evidence_score_inprogress_strong_up_alone_reaches_threshold():
    assert _trend_evidence_score(monthly_structure='轉折', inprogress_strong_up=True) == 1.5


def test_trend_evidence_score_ma_alignment_alone_below_threshold():
    score = _trend_evidence_score(monthly_structure='轉折', ma_alignment=True)
    assert score == 1.0
    assert score < 1.5


def test_trend_evidence_score_weekly_up_alone_below_threshold():
    score = _trend_evidence_score(monthly_structure='轉折', weekly_momentum='升')
    assert score == 0.5
    assert score < 1.5


def test_trend_evidence_score_weekly_sideways_alone_below_threshold():
    score = _trend_evidence_score(monthly_structure='轉折', weekly_momentum='橫')
    assert score == 0.2
    assert score < 1.5


def test_trend_evidence_score_weekly_falling_or_inflection_no_score():
    assert _trend_evidence_score(monthly_structure='轉折', weekly_momentum='跌') == 0.0
    assert _trend_evidence_score(monthly_structure='轉折', weekly_momentum='轉折') == 0.0
    assert _trend_evidence_score(monthly_structure='轉折', weekly_momentum='資料不足') == 0.0


def test_trend_evidence_score_ma_alignment_plus_weekly_up_reaches_threshold():
    score = _trend_evidence_score(monthly_structure='轉折', ma_alignment=True, weekly_momentum='升')
    assert score == 1.5


def test_trend_evidence_score_ma_alignment_plus_weekly_sideways_below_threshold():
    score = _trend_evidence_score(monthly_structure='轉折', ma_alignment=True, weekly_momentum='橫')
    assert score == 1.2
    assert score < 1.5


def test_trend_evidence_score_no_evidence_zero():
    assert _trend_evidence_score(monthly_structure='轉折') == 0.0
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest tests/test_monthly_structure.py -k trend_evidence_score -v`
Expected: FAIL（`ImportError: cannot import name '_trend_evidence_score'`）

- [ ] **Step 3: 實作最小程式碼**

在 `modules/data_enricher.py`，緊接在第 203 行（`_consecutive_bear` 函式結尾）之後、`_structure_flag` 定義（第 204 行）之前，插入：

```python
def _trend_evidence_score(monthly_structure: str,
                          close_strict_up_3: bool = False,
                          bull_count_6: int = 0,
                          inprogress_strong_up: bool = False,
                          ma_alignment: bool = False,
                          weekly_momentum: str = '資料不足') -> float:
    """Stage 2 證據層加權評分（2026-07-12, plan §三十九）。

    取代原本的 OR 疊加布林邏輯。四個既有觸發條件權重與門檻（1.5）相等，
    保證無新訊號時輸出與舊版逐位元組相容；新訊號權重恆低於門檻，只能
    聯手推升分數，不會單獨觸發、也不會扣分拉低既有觸發條件的判定。

    spec: docs/superpowers/specs/2026-07-12-trend-evidence-score-design.md
    """
    score = 0.0
    if monthly_structure in ('升', '橫'):
        score += 1.5
    if close_strict_up_3:
        score += 1.5
    if bull_count_6 >= 4:
        score += 1.5
    if inprogress_strong_up:
        score += 1.5
    if ma_alignment:
        score += 1.0
    if weekly_momentum == '升':
        score += 0.5
    elif weekly_momentum == '橫':
        score += 0.2
    return score


_TREND_SCORE_THRESHOLD = 1.5
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest tests/test_monthly_structure.py -k trend_evidence_score -v`
Expected: PASS（13 個測試全過）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_monthly_structure.py
git commit -m "feat(structure): 新增 _trend_evidence_score 加權評分純函式 (plan §三十九)"
```

---

## Task 2: 把 `_structure_flag()` 的 OR 邏輯改成呼叫加權評分

**Files:**
- Modify: `modules/data_enricher.py:204-230`（`_structure_flag` 函式本體）
- Test: `tests/test_monthly_structure.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_monthly_structure.py` 檔案結尾（緊接 Task 1 新增的測試之後）加入：

```python
# ---------- _structure_flag 加權評分整合（2026-07-12, plan §三十九）----------
def test_structure_flag_existing_triggers_still_byte_compatible():
    """既有 4 個觸發條件單獨仍各自成立（零退化直接證明，byte-compat）。"""
    assert _structure_flag('升', '在上', 0) == '結構未轉弱'
    assert _structure_flag('橫', '在上', 0) == '結構未轉弱'
    assert _structure_flag('轉折', '在上', 0, close_strict_up_3=True) == '結構未轉弱'
    assert _structure_flag('轉折', '在上', 0, bull_count_6=4) == '結構未轉弱'
    assert _structure_flag('轉折', '在上', 0, inprogress_strong_up=True) == '結構未轉弱'
    assert _structure_flag('轉折', '在上', 0) == '結構轉折中'


def test_structure_flag_ma_alignment_plus_weekly_up_promotes_inflection():
    """轉折中 + 均線多頭排列 + 週K動能升 → 聯手達門檻 1.5 → 結構未轉弱（新案例）。"""
    flag = _structure_flag('轉折', '在上', 1, ma_alignment=True, weekly_momentum='升')
    assert flag == '結構未轉弱'


def test_structure_flag_ma_alignment_alone_not_enough():
    """僅均線多頭排列（無其他證據）→ 分數 1.0 < 門檻 → 仍轉折中。"""
    flag = _structure_flag('轉折', '在上', 1, ma_alignment=True)
    assert flag == '結構轉折中'


def test_structure_flag_weekly_up_alone_not_enough():
    """僅週K動能升（無其他證據）→ 分數 0.5 < 門檻 → 仍轉折中。"""
    flag = _structure_flag('轉折', '在上', 1, weekly_momentum='升')
    assert flag == '結構轉折中'


def test_structure_flag_veto_not_overridden_by_new_signals():
    """否決層優先於證據層：即使均線多頭排列+週K動能升，價跌破MA60 仍判已轉弱。"""
    flag = _structure_flag('轉折', '在下', 0, ma_alignment=True, weekly_momentum='升')
    assert flag == '結構已轉弱'


def test_structure_flag_new_signal_params_default_no_change():
    """不傳新參數時（呼叫端尚未升級）行為與升級前完全一致。"""
    assert _structure_flag('升', '在上', 0) == '結構未轉弱'
    assert _structure_flag('跌', '在上', 0) == '結構已轉弱'
    assert _structure_flag('轉折', '在下', 0) == '結構已轉弱'
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest tests/test_monthly_structure.py -k "structure_flag_ma_alignment or structure_flag_weekly_up_alone or structure_flag_veto_not_overridden" -v`
Expected: FAIL（`TypeError: _structure_flag() got an unexpected keyword argument 'ma_alignment'`）

- [ ] **Step 3: 實作**

把 `modules/data_enricher.py` 第 204-230 行的 `_structure_flag` 函式整個替換成：

```python
def _structure_flag(monthly_structure: str, price_vs_ma60: str,
                    consecutive_bear: int,
                    close_strict_up_3: bool = False,
                    bull_count_6: int = 0,
                    inprogress_strong_up: bool = False,
                    ma_alignment: bool = False,
                    weekly_momentum: str = '資料不足') -> str:
    """綜合 → 結構旗標。判定順序：已轉弱（否決層，不可被推翻）> 未轉弱/轉折中
    （證據層，加權評分 + 門檻 1.5）。

    2026-07-12 plan §三十九：證據層從 OR 疊加布林改為呼叫
    `_trend_evidence_score()` 加權評分。四個既有觸發條件（monthly_structure
    升/橫、close_strict_up_3、bull_count_6≥4、inprogress_strong_up）權重
    與門檻相等，無新訊號時逐位元組相容舊版。ma_alignment/weekly_momentum
    為新增訊號，權重恆低於門檻，只能聯手推升分數，不會單獨觸發。

    否決層（已轉弱三條件）完全不受本次改動影響，任何訊號都無法推翻。
    """
    if monthly_structure == '資料不足':
        return '資料不足'
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    if price_vs_ma60 == '在上' and consecutive_bear <= 1:
        score = _trend_evidence_score(
            monthly_structure,
            close_strict_up_3=close_strict_up_3,
            bull_count_6=bull_count_6,
            inprogress_strong_up=inprogress_strong_up,
            ma_alignment=ma_alignment,
            weekly_momentum=weekly_momentum,
        )
        if score >= _TREND_SCORE_THRESHOLD:
            return '結構未轉弱'
    return '結構轉折中'
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS 全部（既有 21 個 + Task 1 的 13 個 + Task 2 新增的 6 個，逐一確認既有 21 個測試名稱都在輸出裡且為 PASS，證明零退化）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_monthly_structure.py
git commit -m "feat(structure): _structure_flag 證據層改加權評分，否決層不動 (plan §三十九)"
```

---

## Task 3: `compute_monthly_structure()` 加 ma5/ma20 參數與 ma_alignment 訊號

**Files:**
- Modify: `modules/data_enricher.py:233-310`（`compute_monthly_structure` 函式本體）
- Test: `tests/test_monthly_structure.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_monthly_structure.py` 檔案結尾加入：

```python
# ---------- compute_monthly_structure ma5/ma20 整合（2026-07-12, plan §三十九）----------
def test_compute_monthly_structure_ma_alignment_true_when_bullish_order():
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300,
                                   ma5=440, ma20=380)
    assert r['ma_alignment'] is True


def test_compute_monthly_structure_ma_alignment_false_when_not_bullish_order():
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300,
                                   ma5=370, ma20=380)
    assert r['ma_alignment'] is False


def test_compute_monthly_structure_ma_alignment_false_when_ma_missing():
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300)
    assert r['ma_alignment'] is False


def test_compute_monthly_structure_ma_alignment_promotes_inflection_to_not_weak():
    """示範案例（非真實歷史 cross-check 還原）：monthly_structure=轉折、四個舊觸發皆
    不成立，但均線多頭排列(ma5>ma20>ma60)+週K動能升 聯手達門檻 1.5 → 結構未轉弱。"""
    completed = _mbars([
        (8, 10, 6, 9),     # 陽
        (9, 12, 5, 8),     # 陰（lows 5<6 不單調升 → highs 單調但 lows 不單調 → 轉折）
        (8, 15, 7, 11),    # 陽
    ])
    inprogress = [_bar(11, 13, 10, 11.5, date='2026-04-01')]
    wcompleted = [
        _bar(9, 10, 8, 9.5, date='2026-03-01'),
        _bar(9.5, 11, 9, 10.5, date='2026-03-08'),
        _bar(10.5, 12, 10, 11.5, date='2026-03-15'),
    ]
    winprogress = [_bar(11.5, 13, 11, 12, date='2026-03-22')]
    r = compute_monthly_structure(
        completed + inprogress, wcompleted + winprogress,
        price=11.5, ma60=10, ma5=11.5, ma20=10.5,
    )
    assert r['monthly_structure'] == '轉折'
    assert r['monthly_close_strict_up_3'] is False
    assert r['monthly_bull_count_6'] < 4
    assert r['monthly_inprogress_strong_up'] is False
    assert r['price_vs_ma60'] == '在上'
    assert r['ma_alignment'] is True
    assert r['weekly_momentum'] == '升'
    assert r['structure_flag'] == '結構未轉弱'
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest tests/test_monthly_structure.py -k ma_alignment -v`
Expected: FAIL（`TypeError: compute_monthly_structure() got an unexpected keyword argument 'ma5'`）

- [ ] **Step 3: 實作**

在 `modules/data_enricher.py`，`compute_monthly_structure` 函式簽章（第 233-234 行）改為：

```python
def compute_monthly_structure(monthly_bars: list, weekly_bars: list,
                              price, ma60, ma5=None, ma20=None) -> dict:
```

在初始 `result = {...}` dict（第 240-253 行）裡加一個欄位，改成：

```python
    result = {
        'monthly_structure':       '資料不足',
        'consecutive_bear_months': 0,
        'drawdown_from_peak':      None,
        'price_vs_ma60':           '未知',
        'structure_flag':          '資料不足',
        'weekly_momentum':         '資料不足',
        'weekly_hold_support':     False,
        # 強勢上漲否決指標（2026-05-25, plan §三十 Bug A）
        'monthly_close_strict_up_3': False,
        'monthly_bull_count_6':      0,
        # F7 §三十二 Bug-5：進行中月強勢否決
        'monthly_inprogress_strong_up': False,
        # 均線多頭排列（2026-07-12, plan §三十九）
        'ma_alignment': False,
    }
```

在「現價 vs 季線 MA60」區塊（第 272-274 行）之後、「F7 §三十二 Bug-5」區塊（第 276 行）之前，插入：

```python
    # 均線多頭排列（2026-07-12, plan §三十九）：MA5 > MA20 > MA60
    if ma5 is not None and ma20 is not None and ma60:
        try:
            result['ma_alignment'] = bool(float(ma5) > float(ma20) > float(ma60))
        except (TypeError, ValueError):
            result['ma_alignment'] = False
```

最後把 `result['structure_flag'] = _structure_flag(...)` 呼叫（第 302-309 行）改為：

```python
    result['structure_flag'] = _structure_flag(
        result['monthly_structure'],
        result['price_vs_ma60'],
        result['consecutive_bear_months'],
        close_strict_up_3=result['monthly_close_strict_up_3'],
        bull_count_6=result['monthly_bull_count_6'],
        inprogress_strong_up=result['monthly_inprogress_strong_up'],
        ma_alignment=result['ma_alignment'],
        weekly_momentum=result['weekly_momentum'],
    )
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS 全部（既有 21 個 + Task 1/2/3 新增，全綠，既有 21 個逐一確認未變動）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_monthly_structure.py
git commit -m "feat(structure): compute_monthly_structure 加 ma5/ma20 參數 + ma_alignment 訊號 (plan §三十九)"
```

---

## Task 4: `_structure_block()` 呼叫端補傳 ma5/ma20

**Files:**
- Modify: `modules/ai_analyzer_v2.py:1093-1098`
- Test: `tests/test_monthly_structure.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_monthly_structure.py` 檔案結尾加入：

```python
# ---------- _structure_block 呼叫端 ma5/ma20 wiring（2026-07-12, plan §三十九）----------
def test_structure_block_ma_alignment_promotes_inflection_to_not_weak():
    """_structure_block 呼叫端正確傳遞 ma5/ma20 → 均線排列可影響最終結構旗標文字。"""
    completed = _mbars([
        (8, 10, 6, 9),
        (9, 12, 5, 8),
        (8, 15, 7, 11),
    ])
    inprogress = [_bar(11, 13, 10, 11.5, date='2026-04-01')]
    wcompleted = [
        _bar(9, 10, 8, 9.5, date='2026-03-01'),
        _bar(9.5, 11, 9, 10.5, date='2026-03-08'),
        _bar(10.5, 12, 10, 11.5, date='2026-03-15'),
    ]
    winprogress = [_bar(11.5, 13, 11, 12, date='2026-03-22')]
    enriched = {
        'monthly_bars': completed + inprogress,
        'weekly_bars': wcompleted + winprogress,
        'ma60': 10, 'ma5': 11.5, 'ma20': 10.5,
    }
    block = _structure_block(enriched, 11.5)
    assert '結構未轉弱' in block


def test_structure_block_without_ma_fields_falls_back_to_old_behavior():
    """enriched_data 沒有 ma5/ma20 key（呼叫端尚未升級的舊資料）→ .get 回 None，行為與升級前一致。"""
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    enriched = {'monthly_bars': completed + inprogress, 'weekly_bars': [], 'ma60': 300}
    block = _structure_block(enriched, 439)
    assert '結構未轉弱' in block
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest tests/test_monthly_structure.py -k structure_block_ma_alignment -v`
Expected: FAIL（`assert '結構未轉弱' in block` 失敗，因為呼叫端還沒傳 ma5/ma20，`ma_alignment` 恆 False，分數只有週K動能升 0.5 < 門檻，結果是「結構轉折中」）

- [ ] **Step 3: 實作**

在 `modules/ai_analyzer_v2.py` 第 1093-1098 行，把：

```python
    ms = compute_monthly_structure(
        enriched_data.get('monthly_bars', []),
        enriched_data.get('weekly_bars', []),
        price_f,
        enriched_data.get('ma60'),
    )
```

改成：

```python
    ms = compute_monthly_structure(
        enriched_data.get('monthly_bars', []),
        enriched_data.get('weekly_bars', []),
        price_f,
        enriched_data.get('ma60'),
        enriched_data.get('ma5'),
        enriched_data.get('ma20'),
    )
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest tests/test_monthly_structure.py -v`
Expected: PASS 全部

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_monthly_structure.py
git commit -m "feat(structure): _structure_block 呼叫端補傳 ma5/ma20 (plan §三十九)"
```

---

## Task 5: `_apply_structure_safety_net` 加 short 方向鏡像防護

**Files:**
- Modify: `modules/ai_analyzer_v2.py:734-750`
- Test: `tests/test_structure_safety_net.py`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_structure_safety_net.py` 檔案結尾（第 47 行之後）加入：

```python
def test_safety_net_not_weakened_short_overridden_to_neutral():
    """結構未轉弱 + AI 標 short → 強制 neutral（2026-07-12 plan §三十九 short 鏡像修法）。"""
    assert _apply_structure_safety_net('結構未轉弱', 'short') == 'neutral'


def test_safety_net_inflection_short_unchanged():
    """結構轉折中 + AI 標 short → 不變（允許 AI 判斷邊界 case，鏡像不誤殺）。"""
    assert _apply_structure_safety_net('結構轉折中', 'short') == 'short'


def test_safety_net_insufficient_data_short_unchanged():
    """資料不足 + AI 標 short → 不變（無依據覆寫，鏡像不誤殺）。"""
    assert _apply_structure_safety_net('資料不足', 'short') == 'short'
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python -m pytest tests/test_structure_safety_net.py -k not_weakened_short -v`
Expected: FAIL（`assert 'short' == 'neutral'`，因為目前函式對 short 完全不覆寫）

- [ ] **Step 3: 實作**

在 `modules/ai_analyzer_v2.py` 第 734-750 行，把 `_apply_structure_safety_net` 函式整個替換成：

```python
def _apply_structure_safety_net(structure_flag: str, direction: str) -> str:
    """F8 §三十二 Bug-3 + F9 §三十九：結構閘安全網（純函式 testable）。

    AI 違反 prompt 鐵律時的最後防線，雙向對稱：
    - 結構已轉弱 + AI 標 long → 強制 neutral（撼訊 5/25 報表案例）
    - 結構未轉弱 + AI 標 short → 強制 neutral（2026-07-12 補上的鏡像防護，
      避免下游 dashboard 方向 badge / _dual_pnf 選邊 / 錨點選取 出現與
      pill 矛盾的空方污染）

    輸入：structure_flag（'結構已轉弱' / '結構轉折中' / '結構未轉弱' / '資料不足'）、
          direction（'long' / 'short' / 'neutral'）
    回傳：safe direction（與輸入相同或被覆寫為 'neutral'）
    """
    if structure_flag == '結構已轉弱' and direction == 'long':
        return 'neutral'
    if structure_flag == '結構未轉弱' and direction == 'short':
        return 'neutral'
    return direction
```

- [ ] **Step 4: 執行測試確認通過**

Run: `python -m pytest tests/test_structure_safety_net.py -v`
Expected: PASS 全部（既有 7 個 + 新增 3 個）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_structure_safety_net.py
git commit -m "fix(structure): _apply_structure_safety_net 加 short 方向鏡像防護 (plan §三十九)"
```

---

## Task 6: 全量回歸驗證

**Files:** 無新檔案，純驗證步驟。

- [ ] **Step 1: 全量 pytest**

Run: `python -m pytest -q`
Expected: 全綠，測試數 = 375（現行）+ 13（Task1）+ 6（Task2）+ 4（Task3）+ 2（Task4）+ 3（Task5）= 403

- [ ] **Step 2: py_compile 靜態檢查**

Run: `python -m py_compile modules/data_enricher.py modules/ai_analyzer_v2.py`
Expected: 無輸出（成功，無語法錯誤）

- [ ] **Step 3: 確認既有 21 個 test_monthly_structure.py 測試逐字未改動**

Run: `git diff HEAD~5 -- tests/test_monthly_structure.py`（回看 Task 1-4 累積的 diff，確認只有新增區塊，原本第 1-303 行內容零修改，只有 import 行如有需要調整）
Expected: diff 只顯示新增的 `+` 行，沒有任何 `-` 刪除既有斷言

此 Task 為驗證關卡，無 commit（沒有程式碼變更）。若任一步驟失敗，回到對應 Task 修正後重新走 Step 1-5。

---

## 完成後

實作完成、pytest 全綠後，下一步是使用者燒 ~$0.6 重跑一鍵分析，用真實股票資料 cross-check：
1. 既有結構旗標判斷不應出現任何案例翻轉（與修法前同一批股票同一天對照）
2. 觀察下次 cross-check 是否有「轉折中」股票因均線+週K聯手證據被正確拉入「未轉弱」

這屬於 spec 第七節「驗收標準」第 3-4 項，不在本 plan 範圍內（需要真實市場資料與使用者操作，plan 只負責把程式碼寫對、測試綠燈）。
