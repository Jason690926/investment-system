"""C2 / Bug S2 + S4（2026-05-24）— _dual_pnf 統一 rounding + placeholder 注入成品。

S2 根因：AI 收到 `:.0f` 給出「74 元」，DB 存 float 73.7 → pill 73.7 / 內文 74 差距。
S4 根因：placeholder 含 label「【P&F等幅量度目標·多方...】—（尚未接近突破點）」，
       prompt 又要求「P&F概念目標：[數值]元」格式 → AI 把整段 label 當數值代入巢狀。

修法：
1. 新 helper _quantize_price(x)：< 100 取 1dp、≥ 100 取 0dp（對齊 TWSE tick）
2. _dual_pnf 量化後同步寫進 block 字串（pill 與內文用同源 quantized 值）
3. placeholder 改注入「完整成品句」（含「P&F概念目標：73.7元（等幅量度）」），
   AI verbatim 引用，不再二次組合

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C2
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _quantize_price, _dual_pnf


# ============================================================
# C2-T1：_quantize_price 規則（< 100 → 1dp, ≥ 100 → 0dp）
# ============================================================
def test_quantize_price_under_100_keeps_1dp():
    assert _quantize_price(73.7) == 73.7
    assert _quantize_price(73.74) == 73.7  # 1dp 截斷/四捨五入
    assert _quantize_price(99.9) == 99.9


def test_quantize_price_at_or_above_100_zero_dp():
    assert _quantize_price(105.5) == 106  # half-up（或 banker's，看實作）
    assert _quantize_price(100.0) == 100
    assert _quantize_price(467.4) == 467


def test_quantize_price_none_returns_none():
    assert _quantize_price(None) is None


# ============================================================
# C2-T2：_dual_pnf 量化後 pnf_long/pnf_short 與 block 字串一致
# ============================================================
def _mock_enriched(target_long=None, target_short=None):
    """構造 enriched_data 讓 calc_pnf_target 回特定值。
    使用 monkey patch via direct injection — 簡化做法：
    用真實的 OHLCV bars 計算太複雜，這裡直接 patch calc_pnf_target。"""
    return {'weekly_bars': [], 'daily_bars': []}


def test_dual_pnf_long_quantizes_and_writes_back_to_block(monkeypatch):
    """pnf_long=73.74（< 100）→ 量化 73.7；block 字串顯示 73.7（非 73 或 74）"""
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: 73.74 if direction == 'long' else None)
    pnf_long, pnf_short, block = _dual_pnf(_mock_enriched(), 70.0)

    assert pnf_long == 73.7
    assert pnf_short is None
    assert '73.7' in block, 'block 必須含量化值 73.7'
    assert '73.74' not in block, 'block 不可含原始未量化值'
    assert '74 元' not in block, 'block 不可含 :.0f 結果'


def test_dual_pnf_long_above_100_zero_dp(monkeypatch):
    """pnf_long=111.4（≥ 100）→ 量化 111；block 顯示 111"""
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: 111.4 if direction == 'long' else None)
    pnf_long, _, block = _dual_pnf(_mock_enriched(), 100.0)
    assert pnf_long == 111
    assert '111' in block


# ============================================================
# C2-T3：placeholder 注入「完整成品句」格式
# ============================================================
def test_dual_pnf_block_contains_full_verbatim_sentence(monkeypatch):
    """block 必須含「P&F概念目標：73.7元（等幅量度）」整句，AI 可直接 verbatim 引用"""
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: 73.7 if direction == 'long' else None)
    _, _, block = _dual_pnf(_mock_enriched(), 70.0)
    assert 'P&F概念目標：73.7元（等幅量度）' in block, \
        '需注入完整成品句讓 AI verbatim 引用，避免 [數值] placeholder 巢狀'


def test_dual_pnf_block_none_uses_no_target_sentence(monkeypatch):
    """pnf strict + relaxed 都 None → 注入「無有效箱體可估算」句 (Opt-1 §三十四)。

    Opt-1 §三十四 後行為：strict None → 嘗試 relaxed → relaxed 也 None 才回
    「無有效箱體可估算」；relaxed 有值則回「P&F理論目標：X — 需先突破/跌破 Y」。
    """
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: None)
    monkeypatch.setattr(mod, 'calc_pnf_target_relaxed',
                        lambda bars, lookback, current_price, direction: None)
    _, _, block = _dual_pnf(_mock_enriched(), 70.0)
    # 新句：「P&F概念目標：—（無有效箱體可估算）」(strict + relaxed 都 None 時)
    assert 'P&F概念目標：—（無有效箱體可估算）' in block


def test_dual_pnf_block_relaxed_sentence_when_strict_none(monkeypatch):
    """Opt-1 §三十四 + Bug-D §三十五：strict None + relaxed 有值 → 依 status 改句。"""
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: None)
    # Bug-D §三十五：relaxed 回 (target, gate, status) 三元組
    monkeypatch.setattr(
        mod, 'calc_pnf_target_relaxed',
        lambda bars, lookback, current_price, direction: (
            (110.0, 100.0, 'pending') if direction == 'long' else (80.0, 90.0, 'pending')
        ),
    )
    _, _, block = _dual_pnf(_mock_enriched(), 95.0)
    # long pending：理論 110、需先突破 100
    assert 'P&F理論目標：110元 — 需先突破 100 元觸發' in block
    # short pending：理論 80、需先跌破 90（< 100 → quantize 1 dp 顯示 80.0 / 90.0）
    assert 'P&F理論目標：80.0元 — 需先跌破 90.0 元觸發' in block


def test_dual_pnf_block_reached_sentence_bug_d(monkeypatch):
    """Bug-D §三十五：status='reached' 改顯「先前等幅量度已達成」句。"""
    import modules.ai_analyzer_v2 as mod
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction: None)
    # long reached: gate 100 已被 cur 133 遠超
    monkeypatch.setattr(
        mod, 'calc_pnf_target_relaxed',
        lambda bars, lookback, current_price, direction: (
            (110.0, 100.0, 'reached') if direction == 'long' else None
        ),
    )
    _, _, block = _dual_pnf(_mock_enriched(), 133.0)
    # 新句不含舊「需先突破 X」
    assert '需先突破' not in block
    # 應出現「先前等幅量度 110 元已達成」+「突破點 100 元」
    assert '先前等幅量度' in block
    assert '110 元已達成' in block
    assert '突破點 100' in block
    assert '等新箱形成' in block


# ============================================================
# C2-T4：prompt 模板已移除舊「⚠️ P&F概念目標已由程式...格式：[數值]元」
# ============================================================
def test_prompt_no_longer_instructs_numeric_template():
    """prompt 模板必須改鐵律為「verbatim 引用整句」，移除舊「[數值]元」格式指令"""
    import modules.ai_analyzer_v2 as mod
    import inspect
    # 找 prompt 模板字串（在 analyze_stock_three_masters / analyze_market_only 內）
    src = inspect.getsource(mod)
    # 舊指令含「格式：」+「[數值]元」應移除
    assert '格式：<span class="target-price">P&F概念目標：[數值]元' not in src, \
        '舊「[數值]元」格式指令應改為 verbatim 引用整句'
