"""§三十八 強漲回測誠實揭露狀態 — _strong_pullback_state 純函式測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strong_pullback_state


def test_heji_wide_above_zone_detaches():
    """合晶型：price 80 > entry_high 76.8、區寬 30.9% → 脫離原箱。"""
    r = _strong_pullback_state(80.0, (52.1, 76.8))
    assert r is not None
    assert r['symptom'] == '脫離原箱'
    assert r['width_pct'] == 31


def test_silergy_wide_in_zone_too_wide():
    """矽力型：price 524 在區內、區寬 28.8% → 區間過寬。"""
    r = _strong_pullback_state(524.0, (391.0, 542.0))
    assert r is not None
    assert r['symptom'] == '區間過寬'
    assert r['width_pct'] == 29


def test_msi_tight_above_zone_returns_none():
    """微星型：price 139.5 > 上緣但區僅 10.9% → 不觸發（交給等回測）。"""
    assert _strong_pullback_state(139.5, (122.0, 137.25)) is None


def test_ruixuan_tight_in_zone_returns_none():
    """瑞軒型：price 43.6 在區內、區僅 17% → 不觸發。"""
    assert _strong_pullback_state(43.6, (37.5, 45.0)) is None


def test_boundary_exactly_25pct_not_triggered():
    """恰 25%：width=(125-100)/100=25% → 不觸發（用 <= threshold）。"""
    assert _strong_pullback_state(100.0, (100.0, 125.0)) is None


def test_boundary_just_over_25pct_triggered():
    """25.5%：width=(125.5-100)/100 → 觸發。"""
    assert _strong_pullback_state(100.0, (100.0, 125.5)) is not None


def test_below_entry_low_returns_none():
    """跌穿（price < entry_low）→ None（交給 跌穿觀察）。"""
    assert _strong_pullback_state(50.0, (52.1, 76.8)) is None


def test_invalid_inputs_return_none():
    assert _strong_pullback_state(None, (1, 2)) is None
    assert _strong_pullback_state(80, None) is None
    assert _strong_pullback_state(80, (76.8, 52.1)) is None  # ehi<=elo
