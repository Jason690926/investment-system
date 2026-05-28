"""Opt-1 §三十四：calc_pnf_target_relaxed 揭露假設條件測試。

當 strict 版（calc_pnf_target）Filter A/B 都失敗 → relaxed 版回 (target, gate_price)
讓 render 顯示「理論目標 X 元 — 需先突破 Y 元觸發」非「— 元」。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.candlestick import calc_pnf_target, calc_pnf_target_relaxed


def _box_bars(box_top, box_bottom, n_pre=2, n_after=6):
    """構造有效箱體 bars：n_pre 根前置 + 箱頂測試 + 3 根確認 + n_after 根後續。

    scan range = range(n - confirm - 2, 0, -1)，故箱頂位置需 ≥ 1，本函式放於 i=n_pre。
    """
    box_mid = (box_top + box_bottom) / 2
    bars = []
    # 前置 bars（high 不超過 box_top - 5）
    for _ in range(n_pre):
        bars.append({'open': box_mid - 2, 'high': box_top - 5, 'low': box_bottom - 2, 'close': box_mid - 2, 'volume_zhang': 1000})
    # 箱頂測試（i=n_pre）
    bars.append({'open': box_mid, 'high': box_top, 'low': box_mid, 'close': box_mid, 'volume_zhang': 1000})
    # 3 根確認 + 箱底（box_bottom 出現於這 3 根之一）
    bars.append({'open': box_mid, 'high': box_top - 1, 'low': box_bottom, 'close': box_mid, 'volume_zhang': 1000})
    for _ in range(2):
        bars.append({'open': box_mid, 'high': box_top - 1, 'low': box_bottom + 0.5, 'close': box_mid, 'volume_zhang': 1000})
    # 後續 bars（high 不超過 box_top, low 不跌破 box_bottom）
    for _ in range(n_after):
        bars.append({'open': box_mid, 'high': box_top - 0.5, 'low': box_bottom + 1, 'close': box_mid, 'volume_zhang': 1000})
    return bars


# ---------- Opt-1 核心：strict 失敗時 relaxed 仍回 (target, gate) ----------

def test_relaxed_returns_target_when_filter_a_fails():
    """現價未過箱頂（Filter A 失敗）→ strict 回 None；relaxed 仍回 (target, gate)。"""
    bars = _box_bars(100, 90)
    strict = calc_pnf_target(bars, lookback=20, current_price=95)
    relaxed = calc_pnf_target_relaxed(bars, lookback=20, current_price=95, direction='long')
    # strict 應 None（Filter A：cur 95 ≤ box_top × 1.02）
    assert strict is None
    # relaxed 應回 (target, gate) — 演算法取最近一個有效箱（rightmost）
    assert relaxed is not None
    target, gate = relaxed
    assert target > gate         # long target 必 > gate
    assert gate >= 95            # gate (= box_top) 為現價需突破才生效


def test_relaxed_short_when_strict_filter_a_fails():
    """short：現價未跌破箱底 → strict None；relaxed 回 (target, gate)。"""
    bars = _box_bars(100, 90)
    relaxed = calc_pnf_target_relaxed(bars, lookback=20, current_price=92, direction='short')
    # short target < gate（下行目標 < 需跌破價）
    assert relaxed is not None
    target, gate = relaxed
    assert target < gate
    assert gate <= 92            # gate (= box_bottom) 為現價需跌破才生效


def test_relaxed_returns_none_when_no_valid_box():
    """無有效箱體（趨勢段、波動率過大）→ relaxed 也回 None。"""
    # 線性上升趨勢、無箱體形成
    bars = [{'open': 10+i, 'high': 11+i, 'low': 9+i, 'close': 10.5+i, 'volume_zhang': 1000}
            for i in range(20)]
    assert calc_pnf_target_relaxed(bars, lookback=20, current_price=29, direction='long') is None


def test_strict_unchanged_when_filters_pass():
    """Filter A+B 都過時 strict 仍回 target（向後相容）。"""
    bars = _box_bars(100, 90)
    strict = calc_pnf_target(bars, lookback=20, current_price=103)
    # 任何 > 100 的合理 target 表示既有邏輯生效（具體值依 scan 找到的箱可能差異）
    assert strict is not None
    assert strict > 100
