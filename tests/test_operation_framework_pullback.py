"""§三十八 _render_operation_framework 強漲回測誠實第五節測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _render_operation_framework


def _swing(elo, ehi, inv):
    return {'entry_zone': (elo, ehi), 'invalidation': inv,
            'range_high': ehi, 'target': None}


def test_pullback_detach_honest_block():
    """合晶：脫離原箱 → 誠實第五節含失效價、無假進場區/目標。"""
    html = _render_operation_framework(
        action_pill='🟡 強漲回測觀望', direction='long',
        swing_levels=_swing(52.1, 76.8, 52.1), breakout=False,
        price=80.0)
    assert '🟡 強漲回測觀望' in html
    assert '脫離原箱' in html
    assert '失效（整波論點作廢）：52.10 元' in html
    assert '待新箱形成後估算' in html
    assert '進場區：' not in html
    assert '52.10 ~ 76.80' not in html


def test_pullback_toowide_honest_block():
    """矽力：區間過寬 → 含寬度百分比。"""
    html = _render_operation_framework(
        action_pill='🟡 強漲回測觀望', direction='long',
        swing_levels=_swing(391.0, 542.0, 391.0), breakout=False,
        price=524.0)
    assert '進場區過寬 29%' in html
    assert '失效（整波論點作廢）：391.00 元' in html


def test_normal_long_unchanged():
    """非強漲回測 pill → 維持原進場區區塊（不誤改）。"""
    html = _render_operation_framework(
        action_pill='🟢 進場區可佈', direction='long',
        swing_levels=_swing(37.5, 45.0, 37.5), breakout=False,
        price=43.6)
    assert '進場區：' in html
    assert '強漲後回測' not in html
