"""F8 §三十二 Bug-3：結構閘安全網（_apply_structure_safety_net）測試。

撼訊 5/25 報表 case：pill = 🔴 不宜進（結構已轉弱反推），AI 內文卻標
DIRECTION=long + 寫「方向一致順勢做多 / 再積累」。安全網在 post-process
階段強制覆寫 direction=neutral，避免下游 pill / 第五節 / target_pnf
出現多頭錨點與 pill 矛盾。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _apply_structure_safety_net


def test_safety_net_weakened_long_overridden_to_neutral():
    """結構已轉弱 + AI 標 long → 強制 neutral（撼訊 5/25 case）。"""
    assert _apply_structure_safety_net('結構已轉弱', 'long') == 'neutral'


def test_safety_net_weakened_short_unchanged():
    """結構已轉弱 + AI 標 short → 不變（符合結構閘預期）。"""
    assert _apply_structure_safety_net('結構已轉弱', 'short') == 'short'


def test_safety_net_weakened_neutral_unchanged():
    """結構已轉弱 + AI 標 neutral → 不變。"""
    assert _apply_structure_safety_net('結構已轉弱', 'neutral') == 'neutral'


def test_safety_net_not_weakened_long_unchanged():
    """結構未轉弱 + AI 標 long → 不變（正常順勢做多 case）。"""
    assert _apply_structure_safety_net('結構未轉弱', 'long') == 'long'


def test_safety_net_inflection_long_unchanged():
    """結構轉折中 + AI 標 long → 不變（允許 AI 判斷邊界 case）。"""
    assert _apply_structure_safety_net('結構轉折中', 'long') == 'long'


def test_safety_net_insufficient_data_long_unchanged():
    """資料不足 + AI 標 long → 不變（無依據覆寫）。"""
    assert _apply_structure_safety_net('資料不足', 'long') == 'long'


def test_safety_net_empty_flag_unchanged():
    """空旗標 + 任意 direction → 不變（防 NoneType / 缺欄位 crash）。"""
    assert _apply_structure_safety_net('', 'long') == 'long'
    assert _apply_structure_safety_net('', '') == ''


def test_safety_net_not_weakened_short_overridden_to_neutral():
    """結構未轉弱 + AI 標 short → 強制 neutral（2026-07-12 plan §三十九 short 鏡像修法）。"""
    assert _apply_structure_safety_net('結構未轉弱', 'short') == 'neutral'


def test_safety_net_inflection_short_unchanged():
    """結構轉折中 + AI 標 short → 不變（允許 AI 判斷邊界 case，鏡像不誤殺）。"""
    assert _apply_structure_safety_net('結構轉折中', 'short') == 'short'


def test_safety_net_insufficient_data_short_unchanged():
    """資料不足 + AI 標 short → 不變（無依據覆寫，鏡像不誤殺）。"""
    assert _apply_structure_safety_net('資料不足', 'short') == 'short'
