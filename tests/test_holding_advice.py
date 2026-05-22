"""優化1（2026-05-22）— 持倉部位建議。

spec: docs/superpowers/specs/2026-05-22-holding-position-advice-design.md
"""
import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import analyze_market_only


def test_signature_has_is_holding():
    """analyze_market_only 須有 optional is_holding 參數（向後相容預設 False）。"""
    params = inspect.signature(analyze_market_only).parameters
    assert 'is_holding' in params
    assert params['is_holding'].default is False


def test_static_block_has_section_six():
    """static_block 須含「六、持倉部位建議」schema 與「持倉停損」bullet。"""
    src = inspect.getsource(analyze_market_only)
    assert '六、持倉部位建議' in src
    assert '持倉停損' in src
