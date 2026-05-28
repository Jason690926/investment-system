"""Bug-2 + Bug-4 修法測試（plan §三十四, 2026-05-28）。

Bug-2：強勢突破首日反轉風險高 → 加 watermark 警示
Bug-4：強勢突破雙重停損 → 主停損 vs 次停損 label hierarchy 明確
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _render_operation_framework


def _sl_breakout(rh=143.5, rl=75.0, ez=(139.19, 143.5), target=243.75):
    """強勢突破 swing_levels（§三十二 _breakout_overrides 覆寫後值）。"""
    return {
        'direction': 'long',
        'range_low': rl, 'range_high': rh,
        'entry_zone': ez,
        'invalidation': rl,
        'target': target,
    }


# ---------- Bug-4：雙重停損 label hierarchy ----------

def test_bug4_breakout_main_stop_label_explicit():
    """強勢突破 framework 包含「主停損」字眼且對齊 range_high。"""
    html = _render_operation_framework(
        action_pill='🟢 追進 💪', direction='long',
        swing_levels=_sl_breakout(), breakout=True,
    )
    assert '主停損' in html
    # 主停損值 = range_high = 143.50
    assert '143.50' in html


def test_bug4_breakout_secondary_stop_label_explicit():
    """強勢突破 framework 包含「次停損」或「論點作廢」明確標示 = invalidation。"""
    html = _render_operation_framework(
        action_pill='🟢 追進 💪', direction='long',
        swing_levels=_sl_breakout(), breakout=True,
    )
    # 次停損 = invalidation = 75.00
    assert '次停損' in html or '論點作廢' in html
    assert '75.00' in html


def test_bug4_breakout_no_ambiguous_single_stop():
    """強勢突破 framework 不能有單純「停損：X 元」(無 hierarchy) 避免家人讀者混淆。

    必須是「主停損」或「次停損」hierarchy 之一，禁止直接「停損：」單字段。
    """
    html = _render_operation_framework(
        action_pill='🟢 追進 💪', direction='long',
        swing_levels=_sl_breakout(), breakout=True,
    )
    # 直接 "停損：75.00" 不該存在（會混淆是主還是次）
    assert '停損：75.00' not in html


# ---------- Bug-2：突破首日 watermark ----------

def test_bug2_breakout_has_warning_watermark():
    """強勢突破 framework 包含「首日」風險警示字眼。"""
    html = _render_operation_framework(
        action_pill='🟢 追進 💪', direction='long',
        swing_levels=_sl_breakout(), breakout=True,
    )
    # 警示提及「首日」「假突破」「反轉」其一
    assert '首日' in html or '假突破風險' in html or '反轉風險' in html


# ---------- 退化檢查：非 breakout long / short / neutral 不退化 ----------

def test_non_breakout_long_unchanged():
    """long 一般 path（breakout=False）不受影響，仍輸出「進場區/停損/目標」。"""
    html = _render_operation_framework(
        action_pill='🟢 進場區可佈', direction='long',
        swing_levels={'entry_zone': (100, 110), 'invalidation': 100, 'target': 130},
        breakout=False,
    )
    assert '進場區：' in html
    # 「停損：」單字段在非 breakout long 仍存在（與 breakout 區隔）
    assert '停損：' in html
    # 不應有 watermark
    assert '首日' not in html and '反轉風險' not in html


def test_short_unchanged():
    """short path 不受影響。"""
    html = _render_operation_framework(
        action_pill='🔴 分批佈空', direction='short',
        swing_levels={'entry_zone': (69.6, 74.7), 'invalidation': 74.7, 'target': 60.0},
        breakout=False,
    )
    assert '空進：' in html
    assert '空停：' in html
    assert '空標：' in html
