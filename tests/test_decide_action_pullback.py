"""§三十八 _decide_action WATCH long 強漲回測 gate 整合測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action


def _swing(elo, ehi, rh=None, inv=None):
    """WATCH long swing_levels；entry_zone=(elo, ehi)。"""
    return {
        'direction': 'long',
        'range_low': elo, 'range_high': rh if rh is not None else ehi,
        'entry_zone': (elo, ehi),
        'invalidation': inv if inv is not None else elo,
        'target': None,
    }


def test_heji_wide_above_returns_pullback():
    """合晶：price 80 / zone 52.1-76.8（寬+脫離）→ 強漲回測觀望。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=101.5),
                       breakout=False, price=80.0)
    assert a == '🟡 強漲回測觀望'


def test_silergy_wide_in_zone_returns_pullback():
    """矽力：price 524 / zone 391-542（寬+在內）→ 強漲回測觀望。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(391.0, 542.0, rh=693.0),
                       breakout=False, price=524.0)
    assert a == '🟡 強漲回測觀望'


def test_msi_tight_above_still_wait_retest():
    """微星：price 139.5 / zone 122-137.25（窄+脫離）→ 維持 等回測。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(122.0, 137.25, rh=152.5),
                       breakout=False, price=139.5)
    assert a == '🟡 等回測'


def test_ruixuan_tight_in_zone_still_deployable():
    """瑞軒：price 43.6 / zone 37.5-45（窄+在內）→ 維持 進場區可佈。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(37.5, 45.0, rh=52.5),
                       breakout=False, price=43.6)
    assert a == '🟢 進場區可佈'


def test_below_entry_low_still_breakdown_watch():
    """跌穿優先：price < entry_low 即使區寬 → 跌穿觀察（不被 gate 攔）。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=101.5),
                       breakout=False, price=50.0)
    assert a == '🟡 跌穿觀察'


def test_breakout_still_chase():
    """新鮮突破不誤觸 gate：breakout=True → 追進 💪。"""
    a = _decide_action(status='watch', direction='long',
                       structure_flag='結構未轉弱',
                       swing_levels=_swing(52.1, 76.8, rh=76.8),
                       breakout=True, price=80.0)
    assert a == '🟢 追進 💪'
