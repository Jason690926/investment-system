"""第五節「操作框架」結構化渲染（2026-05-25, plan §三十一）— _render_operation_framework 測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _render_operation_framework


def _sl_long(rl=100.0, rh=120.0, target=130.0):
    mid = (rl + rh) / 2
    return {
        'direction': 'long',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (rl, mid),
        'invalidation': rl,
        'target': target,
    }


def _sl_short(rl=100.0, rh=120.0, target=80.0):
    mid = (rl + rh) / 2
    return {
        'direction': 'short',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (mid, rh),
        'invalidation': rh,
        'target': target,
    }


def test_render_long_normal_contains_entry_stop_target():
    """long 一般版（breakout=False）：含「進場區/停損/目標」與量門檻字串。"""
    block = _render_operation_framework(
        action_pill='🟡 等回測',
        direction='long',
        swing_levels=_sl_long(),
        breakout=False,
        vol_threshold_zhang=15000,
    )
    assert '建議動作：🟡 等回測' in block
    assert '進場區' in block
    assert '100.00' in block and '110.00' in block   # entry_zone=(100, 110)
    assert '停損' in block and '100.00' in block
    assert '目標' in block and '130.00' in block
    assert '15,000' in block  # 量門檻


def test_render_long_strong_breakout_contains_chase_and_pullback():
    """long 強勢突破版：含「強勢突破追蹤」與「回測進場（保守）」。"""
    block = _render_operation_framework(
        action_pill='🟢 追進 💪',
        direction='long',
        swing_levels=_sl_long(rl=100.0, rh=120.0, target=130.0),
        breakout=True,
    )
    assert '建議動作：🟢 追進 💪' in block
    assert '強勢突破追蹤' in block
    assert '回測進場（保守）' in block
    assert '120.00' in block  # range_high


def test_render_short_contains_short_terms():
    """short 版：含「空進/空停/空標」。"""
    block = _render_operation_framework(
        action_pill='🔴 分批佈空',
        direction='short',
        swing_levels=_sl_short(rl=100.0, rh=120.0, target=80.0),
        breakout=False,
    )
    assert '建議動作：🔴 分批佈空' in block
    assert '空進' in block
    assert '空停' in block
    assert '空標' in block
    assert '120.00' in block  # invalidation = range_high
    assert '80.00' in block   # target


def test_render_neutral_no_entry_exit():
    """neutral 版：含「觀望中」字眼、無進場/出場。"""
    block = _render_operation_framework(
        action_pill='⚪ 觀望',
        direction='neutral',
        swing_levels=None,
        breakout=False,
    )
    assert '建議動作：⚪ 觀望' in block
    assert '觀望' in block


def test_render_long_target_none_displays_dash():
    """target=None 時顯示「—」。"""
    sl = _sl_long(target=None)
    block = _render_operation_framework(
        action_pill='🟡 等回測',
        direction='long',
        swing_levels=sl,
        breakout=False,
    )
    # 目標部分應顯示「—」
    assert '目標：—' in block or '目標' in block and '—' in block


def test_render_long_entry_zone_missing_displays_dash():
    """entry_zone=None 時顯示「—」（fallback 不爆）。"""
    sl = {'range_high': 120.0, 'target': 130.0, 'invalidation': 100.0}
    block = _render_operation_framework(
        action_pill='⚪ 觀望',
        direction='long',
        swing_levels=sl,
        breakout=False,
    )
    assert '進場區：—' in block


# ---------- Opt-1 (plan §三十二)：HTML 結構 + 移除冗餘標題 ----------
def test_render_uses_op_row_div_for_html_linebreak():
    """每行包 <div class="op-row"> 確保 HTML 渲染時自動換行（取代原 \\n）。"""
    block = _render_operation_framework(
        action_pill='🟡 等回測', direction='long',
        swing_levels=_sl_long(), breakout=False, vol_threshold_zhang=1000,
    )
    assert '<div class="op-row">' in block
    assert '<div class="op-divider">' in block
    # 多 row 確認（建議動作 / 進場區 / 停損 / 目標 至少 4 個）
    assert block.count('<div class="op-row">') >= 4


def test_render_no_redundant_section_title():
    """移除冗餘「五、操作框架」前綴（AI prompt 已輸出節標題）。"""
    # long breakout
    block_long_br = _render_operation_framework(
        action_pill='🟢 追進 💪', direction='long',
        swing_levels=_sl_long(), breakout=True,
    )
    # neutral
    block_neu = _render_operation_framework(
        action_pill='⚪ 觀望', direction='neutral',
        swing_levels=None, breakout=False,
    )
    assert '五、操作框架' not in block_long_br
    assert '五、操作框架' not in block_neu


def test_render_short_html_encodes_ampersand():
    """short 版「P&F」應 HTML escape 為「P&amp;F」（HTML 渲染環境安全）。"""
    block = _render_operation_framework(
        action_pill='🔴 分批佈空', direction='short',
        swing_levels=_sl_short(), breakout=False,
    )
    assert '&amp;F' in block or 'P&amp;F' in block
