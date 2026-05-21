"""威科夫結構閘（2026-05-21）— 月線結構客觀事實計算測試。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.data_enricher import _hl_trend, _consecutive_bear


def _bar(o, h, l, c, date='2026-01-01', vol=1000):
    return {'date': date, 'open': o, 'high': h, 'low': l,
            'close': c, 'volume_zhang': vol}


# ---------- _hl_trend ----------
def test_hl_trend_rising():
    bars = [_bar(10, 12, 8, 11), _bar(11, 15, 10, 14), _bar(14, 18, 13, 17)]
    assert _hl_trend(bars) == '升'


def test_hl_trend_falling():
    bars = [_bar(17, 18, 13, 14), _bar(14, 15, 10, 11), _bar(11, 12, 8, 9)]
    assert _hl_trend(bars) == '跌'


def test_hl_trend_inflection():
    # 高點墊高、低點下降 → 轉折
    bars = [_bar(10, 12, 9, 11), _bar(11, 14, 8, 10), _bar(10, 16, 7, 12)]
    assert _hl_trend(bars) == '轉折'


def test_hl_trend_sideways():
    # 高點 12,11,13 與低點 8,9,7 皆非單調 → 橫
    bars = [_bar(10, 12, 8, 11), _bar(11, 11, 9, 10), _bar(10, 13, 7, 12)]
    assert _hl_trend(bars) == '橫'


def test_hl_trend_insufficient():
    assert _hl_trend([_bar(10, 12, 8, 11)]) == '資料不足'


# ---------- _consecutive_bear ----------
def test_consecutive_bear_counts_from_newest():
    bars = [_bar(10, 12, 8, 11), _bar(11, 13, 9, 9), _bar(9, 10, 6, 7)]
    # 最新兩根 close<open → 2
    assert _consecutive_bear(bars) == 2


def test_consecutive_bear_stops_at_bull():
    bars = [_bar(10, 12, 8, 9), _bar(9, 13, 8, 12), _bar(12, 14, 9, 10)]
    # 最新一根陰、前一根陽 → 1
    assert _consecutive_bear(bars) == 1


def test_consecutive_bear_zero_when_newest_bull():
    bars = [_bar(10, 12, 8, 9), _bar(9, 13, 8, 12)]
    assert _consecutive_bear(bars) == 0
