"""建議動作決定樹（2026-05-25, plan §三十一）— _decide_action 純函式測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action


def _swing_long(rl=100, rh=120, target=130):
    """構造 long swing_levels dict。entry_zone=(rl, mid)。"""
    mid = (rl + rh) / 2
    return {
        'direction': 'long',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (rl, mid),
        'invalidation': rl,
        'target': target,
    }


def _swing_short(rl=100, rh=120, target=80):
    """構造 short swing_levels dict。entry_zone=(mid, rh)。"""
    mid = (rl + rh) / 2
    return {
        'direction': 'short',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (mid, rh),
        'invalidation': rh,
        'target': target,
    }


# ---------- WATCH long（5 case）----------
def test_watch_long_structure_weak_returns_avoid():
    """結構已轉弱 → 🔴 不宜進。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構已轉弱',
        swing_levels=_swing_long(), breakout=False,
        price=110,
    )
    assert action == '🔴 不宜進'


def test_watch_long_breakout_returns_chase():
    """_strong_breakout_state=True → 🟢 追進 💪。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(), breakout=True,
        price=125,
    )
    assert action == '🟢 追進 💪'


def test_watch_long_above_range_high_not_breakout_returns_wait_breakout():
    """現價 > range_high 但 breakout=False（量未到）→ 🟡 突破未驗。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構轉折中',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=122,  # > range_high=120
    )
    assert action == '🟡 突破未驗'


def test_watch_long_in_entry_zone_returns_in_entry():
    """現價在 entry_zone 內 → 🟢 進場區可佈。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=105,  # entry_zone=(100, 110)，現價 105 在內
    )
    assert action == '🟢 進場區可佈'


def test_watch_long_above_entry_zone_upper_returns_wait_pullback():
    """現價 > entry_zone 上緣（mid 以上）→ 🟡 等回測。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構轉折中',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=115,  # entry_zone=(100, 110)，現價 115 > 110 但 < range_high=120
    )
    assert action == '🟡 等回測'


# ---------- WATCH short（3 case）----------
def test_watch_short_structure_strong_returns_neutral():
    """結構未轉弱（多方架構完好）→ ⚪ 觀望（不宜空）。"""
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構未轉弱',
        swing_levels=_swing_short(), breakout=False,
        price=110,
    )
    assert action == '⚪ 觀望（不宜空）'


def test_watch_short_above_stop_returns_invalid():
    """現價 > 空停 → 🔴 論點作廢。"""
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=125,  # > invalidation=120
    )
    assert action == '🔴 論點作廢'


def test_watch_short_in_entry_zone_returns_short_in():
    """現價在空進區內 → 🔴 分批佈空。"""
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構轉折中',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=115,  # entry_zone=(110, 120)
    )
    assert action == '🔴 分批佈空'


# ---------- HOLD（4 case）----------
def test_hold_below_cost_stop_returns_exit():
    """現價 < cost_stop_loss → 🔴 出場（個人停損優先）。"""
    action = _decide_action(
        status='hold', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=95, cost_stop_loss=98,
    )
    assert action == '🔴 出場'


def test_hold_structure_weak_returns_reduce():
    """結構已轉弱 → 🟠 減碼。"""
    action = _decide_action(
        status='hold', direction='long',
        structure_flag='結構已轉弱',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=110, cost_stop_loss=None,
    )
    assert action == '🟠 減碼'


def test_hold_breakout_returns_add_with_emoji():
    """強勢突破成立 → 🟢 加碼 💪。"""
    action = _decide_action(
        status='hold', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(rl=100, rh=120), breakout=True,
        price=125, cost_stop_loss=None,
    )
    assert action == '🟢 加碼 💪'


def test_hold_general_long_returns_keep():
    """一般多頭持倉（無強勢突破、現價在 entry_zone 外、結構未轉弱）→ 🟢 續抱。"""
    action = _decide_action(
        status='hold', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(rl=100, rh=120), breakout=False,
        price=115, cost_stop_loss=None,  # 在 entry_zone 上方但未過 range_high
    )
    assert action == '🟢 續抱'


# ---------- 邊界 case ----------
def test_decide_action_handles_missing_price():
    """price=None → ⚪ 觀望（資料不足）。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=_swing_long(), breakout=False,
        price=None,
    )
    assert action == '⚪ 觀望'


def test_decide_action_handles_missing_swing_levels():
    """swing_levels=None → ⚪ 觀望（fallback）。"""
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=None, breakout=False,
        price=110,
    )
    assert action == '⚪ 觀望'
