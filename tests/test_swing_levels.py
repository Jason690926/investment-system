"""calc_swing_levels — 程式錨點 + 穩定性回歸（spec 2026-05-19）"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.candlestick import calc_swing_levels


def _bars(seq):
    """seq: list of (o,h,l,c) → bars dicts（volume 不影響 swing 計算）"""
    return [{'open': o, 'high': h, 'low': l, 'close': c, 'volume_zhang': 1000}
            for (o, h, l, c) in seq]


def _ramp_with_swings():
    """造一段含明確局部峰谷的 40 根日K：
    谷在 idx~10（low=90）、峰在 idx~25（high=130），尾端回落到 ~115"""
    seq = []
    for i in range(40):
        if i < 10:
            base = 100 - i          # 100→91 下行
        elif i < 25:
            base = 90 + (i - 10) * 2.7  # 90→~130 上行
        else:
            base = 130 - (i - 25) * 1.0  # 130→115 回落
        seq.append((base, base + 2, base - 2, base + 0.5))
    return _bars(seq)


def test_long_anchors():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'long', current_price=118.0)
    assert r is not None
    # 失效=最近波段低點（跌破→多方論點作廢），加碼=最近波段高點
    assert r['invalidation'] < r['add_trigger']
    assert r['invalidation'] == pytest.approx(r['range_low'], abs=1e-6)
    assert r['add_trigger'] == pytest.approx(r['range_high'], abs=1e-6)
    lo, hi = r['entry_zone']
    mid = (r['range_low'] + r['range_high']) / 2
    assert lo == pytest.approx(r['range_low'], abs=1e-6)
    assert hi == pytest.approx(mid, abs=1e-6)
    assert r['direction'] == 'long'


def test_short_anchors_mirror_long():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'short', current_price=118.0)
    assert r is not None
    # short 鏡像：失效=波段高（站回→回補），加碼=波段低（跌破→加空）
    assert r['invalidation'] > r['add_trigger']
    assert r['invalidation'] == pytest.approx(r['range_high'], abs=1e-6)
    assert r['add_trigger'] == pytest.approx(r['range_low'], abs=1e-6)
    lo, hi = r['entry_zone']
    mid = (r['range_low'] + r['range_high']) / 2
    assert lo == pytest.approx(mid, abs=1e-6)
    assert hi == pytest.approx(r['range_high'], abs=1e-6)


def test_neutral_range_and_flips():
    bars = _ramp_with_swings()
    r = calc_swing_levels(bars, 'neutral', current_price=118.0)
    assert r is not None
    assert r['range_low'] < r['range_high']
    assert r['flip_long'] == pytest.approx(r['range_high'], abs=1e-6)
    assert r['flip_short'] == pytest.approx(r['range_low'], abs=1e-6)
    assert r['invalidation'] is None
    assert r['add_trigger'] is None
    assert r['entry_zone'] is None


def test_insufficient_bars_returns_none():
    assert calc_swing_levels(_bars([(100, 102, 98, 101)] * 10), 'long', 100) is None
    assert calc_swing_levels([], 'long', 100) is None
    assert calc_swing_levels(None, 'long', 100) is None


def test_no_local_peak_returns_none():
    # 純單調上行，無左右確認的局部峰谷
    seq = [(100 + i, 100 + i + 1, 100 + i - 1, 100 + i) for i in range(40)]
    assert calc_swing_levels(_bars(seq), 'long', 140) is None


def test_bad_direction_returns_none():
    assert calc_swing_levels(_ramp_with_swings(), 'sideways', 118) is None


def test_stability_same_bars_byte_identical():
    bars = _ramp_with_swings()
    a = calc_swing_levels(bars, 'long', 118.0)
    b = calc_swing_levels(bars, 'long', 118.0)
    assert a == b


def test_stability_appending_non_breaking_bar_keeps_anchors():
    """尾端加一根『未觸及失效價』的 bar，錨點不變 → 翻來覆去根治實證"""
    bars = _ramp_with_swings()
    base = calc_swing_levels(bars, 'long', 118.0)
    # 加一根仍在 invalidation 之上、未創新高的 bar
    safe = base['invalidation'] + 5
    bars2 = bars + [{'open': safe, 'high': safe + 1, 'low': safe - 1,
                     'close': safe, 'volume_zhang': 1000}]
    after = calc_swing_levels(bars2, 'long', safe)
    assert after['invalidation'] == pytest.approx(base['invalidation'], abs=1e-6)
    assert after['add_trigger'] == pytest.approx(base['add_trigger'], abs=1e-6)
