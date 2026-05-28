"""Bug-D 修法測試（plan §三十五, 2026-05-28）。

5/28 報表多檔顯示「P&F理論目標：52.2 — 需先突破 46.4」但現價 133 早已超過 46.4
（矽力 / 東捷 / 合晶 / 瑞軒）→ Filter B 失敗（目標已達成）也走「需先突破」邏輯不通。

calc_pnf_target_relaxed 加 status 區分：
- 'pending' — 現價尚未突破/跌破 gate（Filter A 失敗）→ 維持「需先突破/跌破 Y」句
- 'reached' — 現價已超越 gate（Filter B 失敗）→ 改顯示「先前等幅量度已達成，等新箱形成」
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.candlestick import calc_pnf_target_relaxed


def _box_bars(box_top, box_bottom, n_pre=2, n_after=6):
    """構造有效箱體 bars，與 test_pnf_target_relaxed.py 同函式。"""
    box_mid = (box_top + box_bottom) / 2
    bars = []
    for _ in range(n_pre):
        bars.append({'open': box_mid - 2, 'high': box_top - 5, 'low': box_bottom - 2, 'close': box_mid - 2, 'volume_zhang': 1000})
    bars.append({'open': box_mid, 'high': box_top, 'low': box_mid, 'close': box_mid, 'volume_zhang': 1000})
    bars.append({'open': box_mid, 'high': box_top - 1, 'low': box_bottom, 'close': box_mid, 'volume_zhang': 1000})
    for _ in range(2):
        bars.append({'open': box_mid, 'high': box_top - 1, 'low': box_bottom + 0.5, 'close': box_mid, 'volume_zhang': 1000})
    for _ in range(n_after):
        bars.append({'open': box_mid, 'high': box_top - 0.5, 'low': box_bottom + 1, 'close': box_mid, 'volume_zhang': 1000})
    return bars


# ---------- Bug-D：status 區分 ----------

def test_long_pending_when_cur_below_box_top():
    """long：現價未過箱頂 → status='pending'（既有「需先突破」場景）。"""
    bars = _box_bars(100, 90)
    result = calc_pnf_target_relaxed(bars, lookback=20, current_price=95, direction='long')
    assert result is not None
    target, gate, status = result
    assert status == 'pending'
    assert target > gate


def test_long_reached_when_cur_above_box_top():
    """long：現價已遠超 gate（Filter B 失敗場景）→ status='reached'。"""
    bars = _box_bars(100, 90)
    # 現價 133（東捷 5/28 場景）→ 早已突破 box_top 100
    result = calc_pnf_target_relaxed(bars, lookback=20, current_price=133, direction='long')
    assert result is not None
    target, gate, status = result
    assert status == 'reached'


def test_short_pending_when_cur_above_box_bottom():
    """short：現價未跌破箱底 → status='pending'。"""
    bars = _box_bars(100, 90)
    result = calc_pnf_target_relaxed(bars, lookback=20, current_price=92, direction='short')
    assert result is not None
    target, gate, status = result
    assert status == 'pending'
    assert target < gate


def test_short_reached_when_cur_below_box_bottom():
    """short：現價已遠跌破 gate → status='reached'。"""
    bars = _box_bars(100, 90)
    result = calc_pnf_target_relaxed(bars, lookback=20, current_price=50, direction='short')
    assert result is not None
    target, gate, status = result
    assert status == 'reached'
