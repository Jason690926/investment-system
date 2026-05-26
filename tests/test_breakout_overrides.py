"""_breakout_overrides 測試（plan §三十二, spec 2026-05-26）。

覆蓋 happy path（5 檔真實數字）+ cap 觸發 + 退讓邊界。
"""
import pytest
from modules.ai_analyzer_v2 import _breakout_overrides


def _bars(lows: list) -> list:
    """組 daily_bars，high/open/close 用 low+1 簡化（測試只看 low）。"""
    return [
        {'date': f'2026-03-{i+1:02d}',
         'open': l + 0.5, 'high': l + 1, 'low': l, 'close': l + 0.5,
         'volume_zhang': 1000}
        for i, l in enumerate(lows)
    ]


# ---------- happy path（5 檔真實值）----------
def test_overrides_dongjie_8064():
    """東捷：rh=143.5, deep_low_60d=43.25, price=145.5 → target=243.75"""
    sl = {'range_high': 143.5, 'range_low': 75, 'entry_zone': (75, 109.25),
          'target': None, 'invalidation': 75}
    daily = _bars([43.25] + [80] * 30 + [120] * 28 + [140])  # 60 根，最低 43.25
    ov = _breakout_overrides(sl, daily, price=145.5)
    assert ov['target'] == pytest.approx(243.75, rel=1e-3)
    assert ov['entry_zone'][0] == pytest.approx(143.5 * 0.97, rel=1e-3)  # 139.195
    assert ov['entry_zone'][1] == pytest.approx(143.5, rel=1e-3)


def test_overrides_hejing_6182():
    """合晶：rh=59.3, deep_low_60d=28.25, price=76.8 → target=90.35"""
    sl = {'range_high': 59.3, 'range_low': 37.5, 'entry_zone': (37.5, 55.7),
          'target': None, 'invalidation': 37.5}
    daily = _bars([28.25] + [40] * 58 + [55])
    ov = _breakout_overrides(sl, daily, price=76.8)
    # etmm = 59.3 + (59.3 - 28.25) = 90.35
    # cap = 76.8 * 2 = 153.6 → 不踩
    assert ov['target'] == pytest.approx(90.35, rel=1e-3)
    assert ov['entry_zone'] == (pytest.approx(57.521, rel=1e-3),
                                 pytest.approx(59.3, rel=1e-3))


# ---------- cap 觸發 ----------
def test_overrides_cap_triggered():
    """cap=price×2 生效：deep_low 太低算出超大 etmm 應被 cap 截斷。"""
    sl = {'range_high': 100, 'range_low': 50, 'entry_zone': (50, 75),
          'target': None, 'invalidation': 50}
    daily = _bars([1] + [60] * 58 + [80])  # deep_low = 1 → etmm = 199
    ov = _breakout_overrides(sl, daily, price=50)
    # etmm = 100 + 99 = 199, cap = 50 * 2 = 100 → 取 100
    assert ov['target'] == pytest.approx(100, rel=1e-3)


def test_overrides_cap_not_triggered_when_price_high():
    """現價接近 etmm 時，cap 不踩。"""
    sl = {'range_high': 100, 'range_low': 50, 'entry_zone': (50, 75),
          'target': None, 'invalidation': 50}
    daily = _bars([10] + [60] * 58 + [80])  # deep_low = 10 → etmm = 190
    ov = _breakout_overrides(sl, daily, price=100)
    # etmm = 100 + 90 = 190, cap = 100 * 2 = 200 → 取 etmm
    assert ov['target'] == pytest.approx(190, rel=1e-3)


# ---------- 邊界退讓（回 {}） ----------
def test_overrides_returns_empty_when_swing_levels_none():
    """swing_levels=None → 回 {}（呼叫端不覆寫）。"""
    assert _breakout_overrides(None, _bars([10] * 5), price=20) == {}


def test_overrides_returns_empty_when_daily_bars_empty():
    """daily_bars 為空 → 回 {}。"""
    sl = {'range_high': 100, 'range_low': 50}
    assert _breakout_overrides(sl, [], price=110) == {}


def test_overrides_returns_empty_when_deep_low_ge_range_high():
    """deep_low ≥ range_high（資料邏輯不通）→ 回 {}。"""
    sl = {'range_high': 50, 'range_low': 30}
    daily = _bars([60] * 30)  # deep_low = 60 > rh=50
    assert _breakout_overrides(sl, daily, price=55) == {}


def test_overrides_returns_empty_when_price_none():
    """price=None → 回 {}。"""
    sl = {'range_high': 100, 'range_low': 50}
    assert _breakout_overrides(sl, _bars([10] * 30), price=None) == {}
