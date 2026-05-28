"""Bug-H 修法測試（plan §三十五, 2026-05-28）。

AI generation 失敗時：
- _generate 仍回 'AI分析失敗:...' 字串（向後相容其他 caller）
- 新 helper _detect_error_kind 偵測 error 種類（credit / rate_limit / timeout / generic）
- generate_personal_recommendation 偵測到 error 改 raise AIGenerationError（不污染 cache）
- AIGenerationError 提供 friendly_message 給呼叫端
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest

from modules.ai_analyzer_v2 import (
    _detect_error_kind, AIGenerationError, generate_personal_recommendation,
)


# ============ _detect_error_kind ============

def test_detect_ok_for_normal_response():
    """正常 AI 回應（非 AI分析失敗 開頭）→ 'ok'。"""
    assert _detect_error_kind('<h3>▶ 整體判斷</h3><p>續抱...</p>') == 'ok'


def test_detect_credit_for_balance_error():
    """credit balance too low → 'credit'。"""
    err = ("AI分析失敗: Error code: 400 - {'type': 'error', 'error': "
           "{'type': 'invalid_request_error', 'message': 'Your credit balance is too low...'}")
    assert _detect_error_kind(err) == 'credit'


def test_detect_rate_limit():
    """rate_limit / 429 → 'rate_limit'。"""
    assert _detect_error_kind('AI分析失敗: Error code: 429 - rate_limit_error') == 'rate_limit'


def test_detect_timeout():
    """timeout → 'timeout'。"""
    assert _detect_error_kind('AI分析失敗: TimeoutError after 90s') == 'timeout'


def test_detect_generic_error():
    """無法分類 → 'generic'。"""
    assert _detect_error_kind('AI分析失敗: 未知錯誤 xyz') == 'generic'


# ============ AIGenerationError ============

def test_error_friendly_message_credit():
    e = AIGenerationError(raw_error='credit balance too low', kind='credit')
    assert 'AI 服務額度不足' in e.friendly_message


def test_error_friendly_message_rate_limit():
    e = AIGenerationError(raw_error='rate_limit_error', kind='rate_limit')
    assert '繁忙' in e.friendly_message or '稍候' in e.friendly_message


def test_error_friendly_message_timeout():
    e = AIGenerationError(raw_error='timeout', kind='timeout')
    assert '逾時' in e.friendly_message


def test_error_friendly_message_generic():
    e = AIGenerationError(raw_error='unknown error xyz', kind='generic')
    # 包含 raw error snippet（前 80 字元）
    assert 'unknown error' in e.friendly_message


# ============ generate_personal_recommendation 整合 ============

def test_generate_personal_raises_on_error(monkeypatch):
    """_generate 回 error 字串時 → generate_personal_recommendation raise。"""
    import modules.ai_analyzer_v2 as mod
    err_str = ("AI分析失敗: Error code: 400 - {'type': 'error', 'error': "
               "{'type': 'invalid_request_error', 'message': 'Your credit balance is too low...'}")
    monkeypatch.setattr(mod, '_generate', lambda *a, **kw: err_str)

    with pytest.raises(AIGenerationError) as exc:
        generate_personal_recommendation(
            name='測試股', symbol='9999.TW', current_price=100,
            wyckoff_phase='上漲', risk_pct=50,
            support=90, resistance=110, target_pnf=120,
            status='watching',
        )
    assert exc.value.kind == 'credit'
    assert 'credit balance' in exc.value.raw_error


def test_generate_personal_returns_normally_on_success(monkeypatch):
    """_generate 回正常 html → generate_personal_recommendation 直接 return。"""
    import modules.ai_analyzer_v2 as mod
    ok_html = '<h3>▶ 整體判斷</h3><p>續抱</p>'
    monkeypatch.setattr(mod, '_generate', lambda *a, **kw: ok_html)

    result = generate_personal_recommendation(
        name='測試股', symbol='9999.TW', current_price=100,
        wyckoff_phase='上漲', risk_pct=50,
        support=90, resistance=110, target_pnf=120,
        status='watching',
    )
    assert result == ok_html
