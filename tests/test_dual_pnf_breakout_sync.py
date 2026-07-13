"""F3 §三十九（2026-07-13）— 強勢突破股目標價雙源同步。

根因：`_dual_pnf`（prompt 注入，AI 呼叫**前**）用標準 calc_pnf_target；
`_breakout_overrides`（post-process，AI 呼叫**後**）用 60 日低重算等幅量度
→ 大聯大第四節「P&F概念目標：120元」vs 第五節框架/pill「目標 133.00」；
微星 159 vs 196.2。§三十四 S2「pill 與內文同源」沒覆蓋 breakout override 路徑。

修法：`_dual_pnf` 加 `breakout=False` 參數，成立時 long 句改用
`_breakout_overrides` target；兩 call site pre-prompt 先算 `_strong_breakout_state`
傳入（純函式，與 post-process 判定 deterministic 一致）。

plan §三十九 / F3
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import inspect
from modules.ai_analyzer_v2 import _dual_pnf


def _bars(lows: list) -> list:
    """組 daily_bars（測試只看 low：_breakout_overrides 取 60 日絕對最低）。"""
    return [
        {'date': f'2026-06-{(i % 28)+1:02d}',
         'open': l + 0.5, 'high': l + 1, 'low': l, 'close': l + 0.5,
         'volume_zhang': 1000}
        for i, l in enumerate(lows)
    ]


def _patch_swing(monkeypatch, rh=113.0, deep_ok=True):
    """patch calc_swing_levels（_dual_pnf 內部 from-import 自 candlestick）。
    long invalidation 設低（不觸發 Bug-I 失效句）、short invalidation 設高。"""
    import modules.candlestick as ck
    def fake_csl(bars, direction, current_price=None):
        return {
            'direction': direction,
            'range_low': 93.0, 'range_high': rh,
            'entry_zone': (93.0, 103.0),
            'invalidation': 93.0 if direction == 'long' else 999.0,
            'target': None,
        }
    monkeypatch.setattr(ck, 'calc_swing_levels', fake_csl)


# ============================================================
# F3-T1：大聯大場景 — breakout=True → long 句用 override target 133（非標準 120）
# ============================================================
def test_breakout_long_sentence_uses_override_target(monkeypatch):
    """rh=113、60日低=93 → etmm=113+(113-93)=133；標準 calc_pnf_target=120 應被覆蓋"""
    import modules.ai_analyzer_v2 as mod
    _patch_swing(monkeypatch)
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction:
                        120.0 if direction == 'long' else None)
    monkeypatch.setattr(mod, 'calc_pnf_target_relaxed',
                        lambda bars, lookback, current_price, direction: None)
    dk = _bars([93] + [100] * 30)
    pnf_long, _, block = _dual_pnf({'weekly_bars': [], 'daily_bars': dk}, 117.0,
                                    breakout=True)
    assert pnf_long == 133, f'long 目標應與 _breakout_overrides 同源 133，得到 {pnf_long}'
    assert 'P&F概念目標：133元（等幅量度）' in block
    assert '120元' not in block, '標準 target 120 不可殘留在 block（雙源矛盾）'


# ============================================================
# F3-T2：breakout=False（default）→ 行為與修法前完全一致
# ============================================================
def test_no_breakout_keeps_standard_target(monkeypatch):
    import modules.ai_analyzer_v2 as mod
    _patch_swing(monkeypatch)
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction:
                        120.0 if direction == 'long' else None)
    monkeypatch.setattr(mod, 'calc_pnf_target_relaxed',
                        lambda bars, lookback, current_price, direction: None)
    dk = _bars([93] + [100] * 30)
    pnf_long, _, block = _dual_pnf({'weekly_bars': [], 'daily_bars': dk}, 117.0)
    assert pnf_long == 120
    assert 'P&F概念目標：120元（等幅量度）' in block


# ============================================================
# F3-T3：breakout=True 但 override 退讓（deep_low ≥ rh）→ fallback 標準 target
# ============================================================
def test_breakout_override_empty_falls_back(monkeypatch):
    """60 日低 ≥ range_high（邏輯不通）→ _breakout_overrides 回 {} → 沿用標準 120"""
    import modules.ai_analyzer_v2 as mod
    _patch_swing(monkeypatch)
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction:
                        120.0 if direction == 'long' else None)
    monkeypatch.setattr(mod, 'calc_pnf_target_relaxed',
                        lambda bars, lookback, current_price, direction: None)
    dk = _bars([115] * 30)  # deep_low=115 > rh=113
    pnf_long, _, block = _dual_pnf({'weekly_bars': [], 'daily_bars': dk}, 117.0,
                                    breakout=True)
    assert pnf_long == 120
    assert 'P&F概念目標：120元（等幅量度）' in block


# ============================================================
# F3-T4：short 句完全不受 breakout 影響
# ============================================================
def test_breakout_does_not_touch_short_sentence(monkeypatch):
    import modules.ai_analyzer_v2 as mod
    _patch_swing(monkeypatch)
    monkeypatch.setattr(mod, 'calc_pnf_target',
                        lambda bars, lookback, current_price, direction:
                        120.0 if direction == 'long' else 85.0)
    dk = _bars([93] + [100] * 30)
    _, pnf_short, block = _dual_pnf({'weekly_bars': [], 'daily_bars': dk}, 117.0,
                                     breakout=True)
    assert pnf_short == 85.0
    assert 'P&F概念目標：85.0元（等幅量度）' in block


# ============================================================
# F3-T5：兩個 call site 都 pre-prompt 傳 breakout（source 斷言）
# ============================================================
def test_call_sites_pass_breakout_to_dual_pnf():
    import modules.ai_analyzer_v2 as mod
    src = inspect.getsource(mod)
    assert src.count('_dual_pnf(enriched_data, _price_f,') == 2, \
        'analyze_stock_three_masters / analyze_market_only 兩 call site 都應傳 breakout'
    assert src.count('breakout=_breakout_pre') == 2


# ============================================================
# F3-T6：post-process 兩寫入點 override target 有 quantize
#（內文 198 / 框架 197.70 / pill 196.2 三處 rounding 打架的收斂點）
# ============================================================
def test_post_process_quantizes_override_target():
    import modules.ai_analyzer_v2 as mod
    src = inspect.getsource(mod)
    assert src.count("_ov = {**_ov, 'target': _quantize_price(_ov['target'])}") == 2, \
        '兩 post-process 寫入點都應 quantize override target（與 _dual_pnf 注入句同值）'
