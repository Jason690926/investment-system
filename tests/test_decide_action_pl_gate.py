"""Bug-1 + Bug-3 修法測試（plan §三十四, 2026-05-28）。

Bug-1：HOLD + P/L < -20% 抑制「🟢 加碼」改「🟡 觀望持有」
Bug-3：WATCH short 加 boundary buffer（zlo × 1.005）
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action


def _swing_long(rl=100, rh=120, target=130):
    mid = (rl + rh) / 2
    return {'range_low': rl, 'range_high': rh, 'entry_zone': (rl, mid),
            'invalidation': rl, 'target': target}


def _swing_short(rl=100, rh=120, target=80):
    mid = (rl + rh) / 2
    return {'range_low': rl, 'range_high': rh, 'entry_zone': (mid, rh),
            'invalidation': rh, 'target': target}


# ============ Bug-1：HOLD P/L gate ============

def test_bug1_hold_in_entry_zone_pl_minus34_suppresses_jiama():
    """晶心科場景：HOLD + 在進場區 + 虧 -34% → 不可標🟢加碼。"""
    # 進場區 100-110，現價 105（在區內）
    pill = _decide_action(
        status='hold', direction='long', structure_flag='結構未轉弱',
        swing_levels=_swing_long(100, 120), breakout=False, price=105,
        pl_pct=-34.0,
    )
    assert pill != '🟢 加碼'  # 主訴求：不能標加碼
    assert pill == '🟡 觀望持有'


def test_bug1_hold_in_entry_zone_pl_minus20_boundary():
    """虧損 -20% 邊界仍抑制（< -20 抑制；==-20 也抑制以利用戶保守）。"""
    pill = _decide_action(
        status='hold', direction='long', structure_flag='結構未轉弱',
        swing_levels=_swing_long(100, 120), breakout=False, price=105,
        pl_pct=-20.0,
    )
    assert pill == '🟡 觀望持有'


def test_bug1_hold_in_entry_zone_pl_minus15_still_jiama():
    """虧損 -15%（未過門檻）仍可標🟢加碼（沿用既有邏輯）。"""
    pill = _decide_action(
        status='hold', direction='long', structure_flag='結構未轉弱',
        swing_levels=_swing_long(100, 120), breakout=False, price=105,
        pl_pct=-15.0,
    )
    assert pill == '🟢 加碼'


def test_bug1_hold_breakout_pl_minus30_no_jiama_qiang():
    """強勢突破 + 虧 -30% → 也不能標🟢加碼💪（家人讀者深虧不應重壓）。"""
    pill = _decide_action(
        status='hold', direction='long', structure_flag='結構未轉弱',
        swing_levels=_swing_long(100, 120), breakout=True, price=125,
        pl_pct=-30.0,
    )
    assert pill == '🟡 觀望持有'


def test_bug1_hold_pl_none_unchanged():
    """無 pl_pct（None / 觀察股）→ 沿用既有邏輯不影響。"""
    pill = _decide_action(
        status='hold', direction='long', structure_flag='結構未轉弱',
        swing_levels=_swing_long(100, 120), breakout=False, price=105,
        pl_pct=None,
    )
    assert pill == '🟢 加碼'  # 既有行為不退化


# ============ Bug-3：WATCH short boundary buffer ============

def test_bug3_short_at_zlo_boundary_now_classified_as_wait_rebound():
    """撼訊場景：short 現價 = 空進區下緣（70.0 vs zlo 69.60）→ 加 buffer 後判等反彈。"""
    # 空進區 (69.60, 74.70)；現價 70.0 = zlo 上方僅 +0.57%
    sl = _swing_short(rl=60, rh=74.70)
    sl['entry_zone'] = (69.60, 74.70)
    sl['invalidation'] = 74.70
    pill = _decide_action(
        status='watch', direction='short', structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False, price=70.0,
    )
    # buffer = zlo × 1.005 = 69.95 → 70.0 ≥ 69.95 仍算「在區內」
    # 但若 < 69.95 → 改判「🟡 等反彈佈空」
    # 本 case 70.0 ≥ 69.95 → 仍「🔴 分批佈空」（用 ≥ 嚴格邊界）
    assert pill == '🔴 分批佈空'


def test_bug3_short_within_buffer_classified_as_wait_rebound():
    """short 現價在 buffer 內（zlo < price < zlo × 1.005）→ 改判等反彈。"""
    sl = _swing_short(rl=60, rh=74.70)
    sl['entry_zone'] = (69.60, 74.70)
    sl['invalidation'] = 74.70
    # 現價 69.65 = zlo+0.07% < zlo×1.005=69.95 → 太靠下緣，等反彈
    pill = _decide_action(
        status='watch', direction='short', structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False, price=69.65,
    )
    assert pill == '🟡 等反彈佈空'


def test_bug3_short_above_buffer_still_short():
    """short 現價在 zlo × 1.005 上方且 ≤ zhi → 仍「分批佈空」。"""
    sl = _swing_short(rl=60, rh=74.70)
    sl['entry_zone'] = (69.60, 74.70)
    sl['invalidation'] = 74.70
    # 現價 72.0（清楚在區內）
    pill = _decide_action(
        status='watch', direction='short', structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False, price=72.0,
    )
    assert pill == '🔴 分批佈空'
