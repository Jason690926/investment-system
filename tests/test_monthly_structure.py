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


# ---------- compute_monthly_structure ----------
from modules.data_enricher import compute_monthly_structure


def _mbars(specs):
    """specs: list of (o,h,l,c)；自動補日期。回傳月K bar list。"""
    out = []
    for i, (o, h, l, c) in enumerate(specs):
        out.append(_bar(o, h, l, c, date=f'2026-{i+1:02d}-01'))
    return out


def test_compute_jingxinke_uptrend_pullback_not_weak():
    """臻鼎型：月K升、僅末根收陰、現價在 MA60 上 → 結構未轉弱。"""
    # 3 根已收盤（升、末根陰）+ 1 根進行中
    completed = _mbars([
        (200, 234, 157, 220),   # 陽
        (300, 421, 213, 400),   # 陽
        (429, 471, 372, 408),   # 陰（close<open）
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300)
    assert r['monthly_structure'] == '升'
    assert r['consecutive_bear_months'] == 1
    assert r['price_vs_ma60'] == '在上'
    assert r['structure_flag'] == '結構未轉弱'


def test_compute_downtrend_is_weak():
    """晶心科型：月K跌、現價跌破 MA60 → 結構已轉弱。"""
    completed = _mbars([
        (260, 270, 230, 240),
        (240, 245, 210, 219),
        (235, 240, 170, 200),
    ])
    inprogress = [_bar(214, 221, 213, 216, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=216, ma60=250)
    assert r['monthly_structure'] == '跌'
    assert r['price_vs_ma60'] == '在下'
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_two_bear_months_forces_weak():
    """月K升、現價在 MA60 上，但連 2 月陰 → 仍判結構已轉弱。"""
    completed = _mbars([
        (200, 234, 157, 230),   # 陽
        (300, 421, 213, 280),   # 陰
        (429, 471, 372, 408),   # 陰
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=439, ma60=300)
    assert r['consecutive_bear_months'] == 2
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_excludes_inprogress_month():
    """進行中月份（最後一根）不參與月K結構判定。"""
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    # 進行中月份是暴跌，但應被排除
    inprogress = [_bar(408, 410, 100, 110, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=110, ma60=300)
    assert r['monthly_structure'] == '升'   # 仍用已收盤 3 根


def test_compute_weekly_hold_support_true():
    """週K收盤 401/401/408.5（離散<3%、墊高）→ 守穩支撐=是。"""
    wcompleted = [
        _bar(400, 410, 390, 401, date='2026-05-03'),
        _bar(401, 405, 396, 401, date='2026-05-10'),
        _bar(401, 415, 372, 408.5, date='2026-05-17'),
    ]
    winprogress = [_bar(408, 420, 405, 415, date='2026-05-20')]
    r = compute_monthly_structure([], wcompleted + winprogress, price=415, ma60=None)
    assert r['weekly_hold_support'] is True


def test_compute_weekly_hold_support_false_when_declining():
    wcompleted = [
        _bar(420, 425, 410, 420, date='2026-05-03'),
        _bar(415, 418, 400, 405, date='2026-05-10'),
        _bar(400, 405, 380, 385, date='2026-05-17'),
    ]
    winprogress = [_bar(385, 390, 375, 380, date='2026-05-20')]
    r = compute_monthly_structure([], wcompleted + winprogress, price=380, ma60=None)
    assert r['weekly_hold_support'] is False


def test_compute_insufficient_data():
    r = compute_monthly_structure([], [], price=100, ma60=90)
    assert r['monthly_structure'] == '資料不足'
    assert r['structure_flag'] == '資料不足'


# ---------- _structure_block 格式化 ----------
from modules.ai_analyzer_v2 import _structure_block


def test_structure_block_not_weak_contains_ban():
    completed = _mbars([
        (200, 234, 157, 220),
        (300, 421, 213, 400),
        (429, 471, 372, 408),
    ])
    inprogress = [_bar(412, 448, 402, 439, date='2026-05-01')]
    enriched = {'monthly_bars': completed + inprogress, 'weekly_bars': [],
                'ma60': 300}
    block = _structure_block(enriched, 439)
    assert '月線結構客觀事實' in block
    assert '結構未轉弱' in block
    assert '禁止標派發' in block


def test_structure_block_empty_when_insufficient():
    enriched = {'monthly_bars': [], 'weekly_bars': [], 'ma60': None}
    assert _structure_block(enriched, 100) == ''
