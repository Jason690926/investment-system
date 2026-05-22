"""優化2（2026-05-22）— 強勢突破狀態判定。

spec: docs/superpowers/specs/2026-05-22-strong-breakout-tracking-design.md
"""
import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strong_breakout_state, analyze_market_only


def _swingy_daily():
    """峰-谷-升形狀（40 根）：0-9 升至峰、10-19 跌至谷、20-39 再升。
    calc_swing_levels 取得 range_high ≈ idx9 峰高。"""
    closes = ([10, 13, 16, 19, 22, 24, 26, 28, 29, 30,   # 0-9 升（峰）
               28, 26, 24, 22, 20, 18, 17, 16, 15, 14,   # 10-19 跌（谷）
               16, 18, 21, 24, 27, 30, 33, 36, 39, 42,   # 20-29 反彈再升
               44, 46, 48, 49, 50, 51, 52, 53, 54, 55])  # 30-39 續升
    return [{'date': f'2026-{(i // 28) + 3:02d}-{(i % 28) + 1:02d}',
             'open': c - 1, 'high': c + 1, 'low': c - 2,
             'close': c, 'volume_zhang': 1000} for i, c in enumerate(closes)]


def _ed(daily, vt, v5):
    return {'daily_bars': daily, 'volume_zhang': vt, 'volume_5d_avg_zhang': v5}


def test_breakout_true_when_above_range_high_and_volume():
    # 現價遠高於 range_high（≈31），今日量 2000 ≥ 5日均1000×1.5
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5=1000), price_f=999) is True


def test_breakout_false_when_volume_insufficient():
    # 量 1200 < 1000×1.5=1500
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=1200, v5=1000), price_f=999) is False


def test_breakout_false_when_price_below_range_high():
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5=1000), price_f=5) is False


def test_breakout_false_on_bad_input():
    assert _strong_breakout_state({'daily_bars': []}, price_f=None) is False
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5='--'), price_f=999) is False


def test_long_template_has_breakout_branch():
    """static_block long 模板須含「強勢突破追蹤」與「回測進場（保守）」兩分支。"""
    src = inspect.getsource(analyze_market_only)
    assert '強勢突破追蹤' in src
    assert '回測進場（保守）' in src
