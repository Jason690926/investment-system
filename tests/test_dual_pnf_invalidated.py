"""Bug-I 修法測試（plan §三十六, 2026-05-28 Round 3）。

晶心科 5/28 場景：pill=🔴 出場（跌穿停損 224.5 → 219.5）但同段 P&F 仍寫
「需先突破 260 元觸發」邏輯矛盾。

修法：_dual_pnf 偵測 swing_levels invalidation 是否被跌穿/站回：
- long: cur < swing_low × 0.985 → long 句改「論點已失效（跌穿支撐 X 元）」
- short: cur > swing_high × 1.015 → short 句改「論點已失效（站回壓力 X 元）」
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _dual_pnf
import modules.ai_analyzer_v2 as mod
import modules.candlestick as cs


def _patch_swing_levels(monkeypatch, swing_low=224.5, swing_high=250.0):
    """monkeypatch calc_swing_levels 直接控制 invalidation 觸發點。"""
    def fake(bars, direction, price=None):
        if not bars:
            return None
        if direction == 'long':
            return {'invalidation': swing_low, 'range_low': swing_low, 'range_high': swing_high}
        if direction == 'short':
            return {'invalidation': swing_high, 'range_low': swing_low, 'range_high': swing_high}
        return None
    monkeypatch.setattr(mod, 'calc_pnf_target', lambda *a, **kw: None)
    monkeypatch.setattr(mod, 'calc_pnf_target_relaxed', lambda *a, **kw: (260, 240, 'pending'))
    monkeypatch.setattr(cs, 'calc_swing_levels', fake)


def _bars():
    return [{'open': 220, 'high': 230, 'low': 210, 'close': 220, 'volume_zhang': 1000} for _ in range(25)]


# ============ Bug-I：long 論點失效 ============

def test_long_invalidated_when_price_below_swing_low(monkeypatch):
    """晶心科場景：long 論點失效 → P&F 句改「論點已失效」。"""
    _patch_swing_levels(monkeypatch, swing_low=224.5, swing_high=250.0)
    _, _, block = _dual_pnf({'daily_bars': _bars(), 'weekly_bars': []}, price_f=219.5)
    long_part = block.split('空方')[0] if '空方' in block else block
    assert '論點已失效' in long_part
    assert '需先突破' not in long_part


def test_long_not_invalidated_at_boundary(monkeypatch):
    """邊界：cur 接近但未過 0.985 門檻 → 不算失效。"""
    _patch_swing_levels(monkeypatch, swing_low=224.5, swing_high=250.0)
    _, _, block = _dual_pnf({'daily_bars': _bars(), 'weekly_bars': []}, price_f=222.5)
    long_part = block.split('空方')[0] if '空方' in block else block
    assert '論點已失效' not in long_part


def test_long_normal_when_price_in_range(monkeypatch):
    """正常：現價在 swing 範圍內 → 既有邏輯（不觸發 invalidated）。"""
    _patch_swing_levels(monkeypatch, swing_low=220.0, swing_high=250.0)
    _, _, block = _dual_pnf({'daily_bars': _bars(), 'weekly_bars': []}, price_f=235.0)
    assert '論點已失效' not in block


# ============ short 論點失效 ============

def test_short_invalidated_when_price_above_swing_high(monkeypatch):
    """short 論點失效：cur 站回 swing_high × 1.015 → 空方句改。"""
    _patch_swing_levels(monkeypatch, swing_low=220.0, swing_high=250.0)
    _, _, block = _dual_pnf({'daily_bars': _bars(), 'weekly_bars': []}, price_f=258.0)
    short_part = block.split('空方')[1] if '空方' in block else block
    assert '論點已失效' in short_part
    assert '站回壓力' in short_part


# ============ 退化 ============

def test_no_bars_returns_safely():
    """空資料 → 不 crash。"""
    enriched = {'daily_bars': [], 'weekly_bars': []}
    _, _, block = _dual_pnf(enriched, price_f=100)
    assert isinstance(block, str)
