"""Bug-J 修法測試（plan §三十六, 2026-05-28 Round 3）。

瑞耘 6532 5/28 場景：phase=再積累 (long phase) / 收 96.2 < entry_low 96.8
→ WATCH long path 走到 default '⚪ 觀望' + 同段顯示「停損 96.80（已跌穿）」邏輯矛盾。

修法：WATCH long path 加判斷「price < entry_low」→ 新 pill「🟡 跌穿觀察」
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action


def _swing_long(rl=100, rh=120):
    mid = (rl + rh) / 2
    return {'range_low': rl, 'range_high': rh, 'entry_zone': (rl, mid),
            'invalidation': rl, 'target': None}


# ============ Bug-J：WATCH long 跌穿 entry_low ============

def test_watch_long_below_entry_low_returns_new_pill():
    """瑞耘場景：WATCH long + 結構未轉弱 + price < entry_low → 🟡 跌穿觀察。"""
    # entry_zone (96.8, 109.65)；price 96.2 < 96.8
    sl = _swing_long(rl=96.8, rh=122.5)
    pill = _decide_action(
        status='watch', direction='long', structure_flag='結構未轉弱',
        swing_levels=sl, breakout=False, price=96.2,
    )
    assert pill == '🟡 跌穿觀察'


def test_watch_long_in_entry_zone_unchanged():
    """既有正常：在 entry_zone 內 → 🟢 進場區可佈（不退化）。"""
    sl = _swing_long(rl=100, rh=120)
    pill = _decide_action(
        status='watch', direction='long', structure_flag='結構未轉弱',
        swing_levels=sl, breakout=False, price=105,
    )
    assert pill == '🟢 進場區可佈'


def test_watch_long_above_entry_zone_unchanged():
    """既有正常：現價在 entry_zone 上方 → 🟡 等回測（不退化）。"""
    sl = _swing_long(rl=100, rh=120)
    pill = _decide_action(
        status='watch', direction='long', structure_flag='結構未轉弱',
        swing_levels=sl, breakout=False, price=115,
    )
    assert pill == '🟡 等回測'


def test_watch_long_below_entry_when_structure_weakened():
    """結構已轉弱 + 跌穿 entry → 仍是 🔴 不宜進（已轉弱優先）。"""
    sl = _swing_long(rl=100, rh=120)
    pill = _decide_action(
        status='watch', direction='long', structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False, price=95,
    )
    assert pill == '🔴 不宜進'  # 結構已轉弱優先於跌穿
