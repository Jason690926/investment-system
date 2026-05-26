# 強勢突破回測區異常 + P&F 目標缺失：實作計畫

> **For agentic workers:** 逐 Task 執行，每 Task 走 TDD（紅→綠→commit）。

**Goal:** 修強勢突破股 5 檔共病的兩個 bug：(1) 回測進場區顯示舊箱型範圍（東捷 -25%~-48% 距現價）；(2) P&F 目標「— 元」缺失。

**Architecture:** 新增純函式 `_breakout_overrides(swing_levels, daily_bars, price)` 在 `ai_analyzer_v2.py`；`analyze_stock_three_masters` / `analyze_market_only` 既有 post-process 區段算完 `_breakout` 後若 True 則覆寫 `_sl['entry_zone']` 與 `['target']`，同步 `result['target_pnf']`。

**Tech Stack:** Python / pytest；spec：`docs/superpowers/specs/2026-05-26-strong-breakout-retest-and-target-design.md`

---

## F1 — TDD 測試紅燈

### Task 1：新增 `tests/test_breakout_overrides.py`

**Files:**
- Create: `tests/test_breakout_overrides.py`

- [ ] **Step 1: 寫失敗測試**（8 case）

```python
"""_breakout_overrides 測試（plan §三十二, spec 2026-05-26）。

覆蓋 happy path（5 檔真實數字）+ cap 觸發 + 退讓邊界。
"""
import pytest
from modules.ai_analyzer_v2 import _breakout_overrides


def _bars(lows: list) -> list:
    """組 daily_bars，high/open/close 用 low+1 簡化（測試只看 low）。"""
    return [
        {'date': f'2026-03-{i+1:02d}',
         'open': l + 0.5, 'high': l + 1, 'low': l, 'close': l + 0.5,
         'volume_zhang': 1000}
        for i, l in enumerate(lows)
    ]


# ---------- happy path（5 檔真實值）----------
def test_overrides_dongjie_8064():
    """東捷：rh=143.5, deep_low_60d=43.25, price=145.5 → target=243.75"""
    sl = {'range_high': 143.5, 'range_low': 75, 'entry_zone': (75, 109.25),
          'target': None, 'invalidation': 75}
    daily = _bars([43.25] + [80] * 30 + [120] * 28 + [140])  # 60 根，最低 43.25
    ov = _breakout_overrides(sl, daily, price=145.5)
    assert ov['target'] == pytest.approx(243.75, rel=1e-3)
    assert ov['entry_zone'][0] == pytest.approx(143.5 * 0.97, rel=1e-3)  # 139.195
    assert ov['entry_zone'][1] == pytest.approx(143.5, rel=1e-3)


def test_overrides_hejing_6182():
    """合晶：rh=59.3, deep_low_60d=28.25, price=76.8 → target=90.35"""
    sl = {'range_high': 59.3, 'range_low': 37.5, 'entry_zone': (37.5, 55.7),
          'target': None, 'invalidation': 37.5}
    daily = _bars([28.25] + [40] * 58 + [55])
    ov = _breakout_overrides(sl, daily, price=76.8)
    # etmm = 59.3 + (59.3 - 28.25) = 90.35
    # cap = 76.8 * 2 = 153.6 → 不踩
    assert ov['target'] == pytest.approx(90.35, rel=1e-3)
    assert ov['entry_zone'] == (pytest.approx(57.521, rel=1e-3),
                                  pytest.approx(59.3, rel=1e-3))


# ---------- cap 觸發 ----------
def test_overrides_cap_triggered():
    """cap=price×2 生效：deep_low 太低算出超大 etmm 應被 cap 截斷。"""
    sl = {'range_high': 100, 'range_low': 50, 'entry_zone': (50, 75),
          'target': None, 'invalidation': 50}
    daily = _bars([1] + [60] * 58 + [80])  # deep_low = 1 → etmm = 199
    ov = _breakout_overrides(sl, daily, price=50)
    # etmm = 100 + 99 = 199, cap = 50 * 2 = 100 → 取 100
    assert ov['target'] == pytest.approx(100, rel=1e-3)


def test_overrides_cap_not_triggered_when_price_high():
    """現價接近 etmm 時，cap 不踩。"""
    sl = {'range_high': 100, 'range_low': 50, 'entry_zone': (50, 75),
          'target': None, 'invalidation': 50}
    daily = _bars([10] + [60] * 58 + [80])  # deep_low = 10 → etmm = 190
    ov = _breakout_overrides(sl, daily, price=100)
    # etmm = 100 + 90 = 190, cap = 100 * 2 = 200 → 取 etmm
    assert ov['target'] == pytest.approx(190, rel=1e-3)


# ---------- 邊界退讓（回 {}） ----------
def test_overrides_returns_empty_when_swing_levels_none():
    """swing_levels=None → 回 {}（呼叫端不覆寫）。"""
    assert _breakout_overrides(None, _bars([10] * 5), price=20) == {}


def test_overrides_returns_empty_when_daily_bars_empty():
    """daily_bars 為空 → 回 {}。"""
    sl = {'range_high': 100, 'range_low': 50}
    assert _breakout_overrides(sl, [], price=110) == {}


def test_overrides_returns_empty_when_deep_low_ge_range_high():
    """deep_low ≥ range_high（資料邏輯不通）→ 回 {}。"""
    sl = {'range_high': 50, 'range_low': 30}
    daily = _bars([60] * 30)  # deep_low = 60 > rh=50
    assert _breakout_overrides(sl, daily, price=55) == {}


def test_overrides_returns_empty_when_price_none():
    """price=None → 回 {}。"""
    sl = {'range_high': 100, 'range_low': 50}
    assert _breakout_overrides(sl, _bars([10] * 30), price=None) == {}
```

- [ ] **Step 2: 跑測試確認失敗** — `python -m pytest tests/test_breakout_overrides.py -q`，預期 8 fail（`_breakout_overrides` 尚不存在 → ImportError）。

---

## F2 — 實作 `_breakout_overrides` + 整合到 post-process

### Task 2：新增純函式 + 兩處覆寫點

**Files:**
- Modify: `modules/ai_analyzer_v2.py`

- [ ] **Step 1: 加入 `_breakout_overrides` helper**

插入位置：`modules/ai_analyzer_v2.py`，緊接 `_strong_breakout_state` 之後（line 621 後、`_decide_action` 之前 line 624）。

```python
def _breakout_overrides(swing_levels: dict, daily_bars: list,
                         price) -> dict:
    """強勢突破成立時覆寫 entry_zone 與 target（plan §三十二, spec 2026-05-26）。

    既有 calc_swing_levels 的 entry_zone / target 對「箱型整理 → 等回測」場景
    設計；強勢突破中該箱型已被穿過，需用「被突破前高」作 retest 錨點、
    「過去 60 日絕對最低」作 base_low 重算等幅量度目標。

    輸入：
      - swing_levels: calc_swing_levels 結果（含 range_high）
      - daily_bars: 日 K bars（取最後 60 根）
      - price: 現價（float-able）

    回傳：
      - 成功：{'entry_zone': (rh*0.97, rh), 'target': bounded_etmm}
      - 輸入不足/邏輯不通：{}（呼叫端不覆寫）
    """
    if not swing_levels or not daily_bars or price is None:
        return {}
    rh = swing_levels.get('range_high')
    if rh is None:
        return {}
    try:
        rh_f = float(rh)
        price_f = float(price)
        window = daily_bars[-60:] if len(daily_bars) >= 60 else daily_bars
        deep_low = min(float(b['low']) for b in window)
        if deep_low >= rh_f:
            return {}
        etmm = rh_f + (rh_f - deep_low)
        target = min(etmm, price_f * 2.0)
        retest_zone = (rh_f * 0.97, rh_f)
        return {'entry_zone': retest_zone, 'target': target}
    except (TypeError, ValueError, KeyError):
        return {}
```

- [ ] **Step 2: 跑測試確認通過** — `python -m pytest tests/test_breakout_overrides.py -q`，預期 8 passed。

- [ ] **Step 3: 整合到 `analyze_stock_three_masters` post-process（line 1124 後）**

```python
        _breakout = _strong_breakout_state(enriched_data, _price_f)
        # F2 §三十二：強勢突破成立 → 覆寫 entry_zone（retest）與 target
        if _breakout and _sl:
            _ov = _breakout_overrides(
                _sl, enriched_data.get('daily_bars', []), _price_f
            )
            if _ov:
                _sl = {**_sl, **_ov}  # 不變動原 dict 避免副作用
                if result.get('direction') == 'long':
                    result['target_pnf'] = _ov['target']
```

- [ ] **Step 4: 整合到 `analyze_market_only` post-process（line 1525 後）** — 鏡像 Step 3 同樣的 5 行覆寫邏輯。

- [ ] **Step 5: 退化檢查** — 跑完整測試套件
  ```
  python -m pytest tests/ -q
  ```
  預期：269 原 + 8 新 = 277 passed，零退化。

- [ ] **Step 6: py_compile 檢查**
  ```
  python -m py_compile modules/ai_analyzer_v2.py
  ```

- [ ] **Step 7: commit F2**
  ```
  feat(breakout): _breakout_overrides retest 區 + target 重算 (plan §三十二)
  ```

---

## F3 — 文件 + plan.md

### Task 3：文件齊備

**Files:**
- Already exists: `docs/superpowers/specs/2026-05-26-strong-breakout-retest-and-target-design.md`
- Already exists: `docs/superpowers/plans/2026-05-26-strong-breakout-retest-and-target.md`（本檔）
- Already exists: `plan.md` §三十二

- [ ] **Step 1: 確認 spec + impl plan + plan.md §三十二 三份齊全**
- [ ] **Step 2: commit F3**
  ```
  docs: plan.md §三十二 + spec + impl plan (5/26 強勢突破 retest+target)
  ```

---

## 驗收 checklist

執行完 F1+F2+F3 後：

- [ ] `git log --oneline -3` 顯示 3 個新 commit（test → feat → docs）
- [ ] `python -m pytest tests/ -q` 全綠（277 passed）
- [ ] `python -m py_compile modules/ai_analyzer_v2.py` 無 syntax error
- [ ] 既有 `tests/test_strong_breakout.py` / `tests/test_operation_framework.py` / `tests/test_decide_action.py` 共 25 case 零退化
- [ ] git push origin main 觸發 Render auto-deploy
- [ ] **⚠️ 待用戶 deploy 後燒 ~$0.6 重跑驗 5 檔強勢突破股**：

  | 股 | 期望 retest zone | 期望 target |
  |----|-----------------|------------|
  | 東捷 | 139.20 ~ 143.50 | 243.75 |
  | 矽力 | 442.32 ~ 456.00 | 728.50 |
  | 合晶 | 57.52 ~ 59.30 | 90.35 |
  | 瑞軒 | 47.38 ~ 48.85 | 67.70 |
  | 微星 | 120.28 ~ 124.00 | 163.00 |

  非強勢突破股（晶心科 / 創惟 / 華星光 / 南亞科 / 撼訊 / 技嘉 / 華擎 / 大聯大 / 瑞耘）零變動。

---

## 回滾策略

純加性 helper + 單一覆寫點，無 DB migration、無既有函式簽名改動。任一 commit 出問題 `git revert <hash>` 即可。

最壞情況：helper 內部 bug → 回 `{}` 退讓 → 沿用原 `calc_swing_levels` 值（= bug 修法前狀態），不會 crash。
