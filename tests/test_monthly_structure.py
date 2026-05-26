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


# ---------- 強勢上漲否決（2026-05-25, plan §三十 Bug A）----------
def test_structure_flag_close_strict_up_overrides_inflection():
    """東捷型：_hl_trend 因 lows 不嚴格升回「轉折」，但 close 嚴格上揚 → 結構未轉弱。"""
    # 2~4 月 close: 48.85 → 63.30 → 104.0 嚴格升
    # 2~4 月 lows: 44.80 → 43.30 → 63.80 不嚴格升（3 月低於 2 月）→ _hl_trend 回「轉折」
    completed = _mbars([
        (43.25, 48.35, 40.55, 47.30),  # 12 月 陽
        (47.50, 60.90, 45.85, 53.30),  # 1 月 陽
        (52.30, 57.50, 44.80, 48.85),  # 2 月 陰
        (47.10, 77.60, 43.30, 63.30),  # 3 月 陽
        (67.20, 104.0, 63.80, 104.0),  # 4 月 陽
    ])
    inprogress = [_bar(114.0, 143.5, 103.5, 120.5, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=132.5, ma60=58)
    assert r['monthly_structure'] == '轉折'
    assert r['monthly_close_strict_up_3'] is True
    assert r['structure_flag'] == '結構未轉弱'


def test_structure_flag_bull_count_6_overrides_inflection():
    """近 6 月陽月數 ≥ 4 強勢上漲：_hl_trend 回「轉折」但近期陽月多 → 結構未轉弱。"""
    completed = _mbars([
        (10, 12, 8, 11),    # 陽
        (11, 13, 9, 12),    # 陽
        (12, 14, 10, 13),   # 陽
        (13, 14, 11, 12),   # 陰 — 讓 close 不嚴格上揚
        (12, 16, 6, 15),    # 陽 — lows 6<11 不嚴格升 → _hl_trend 回「轉折」
    ])
    inprogress = [_bar(15, 17, 14, 16, date='2026-06-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=10)
    assert r['monthly_structure'] == '轉折'
    assert r['monthly_close_strict_up_3'] is False
    assert r['monthly_bull_count_6'] >= 4
    assert r['structure_flag'] == '結構未轉弱'


def test_structure_flag_below_ma60_not_overridden_by_strong_up():
    """價在 MA60 之下：強勢上漲否決不可逆轉（仍判結構已轉弱）。"""
    completed = _mbars([
        (10, 12, 8, 11),   # 陽
        (11, 14, 10, 13),  # 陽
        (13, 16, 11, 15),  # 陽 — close 嚴格上揚
    ])
    inprogress = [_bar(15, 17, 14, 16, date='2026-05-01')]
    # 價 16 < ma60 20 → 在下，必須仍是已轉弱
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=20)
    assert r['price_vs_ma60'] == '在下'
    assert r['monthly_close_strict_up_3'] is True
    assert r['structure_flag'] == '結構已轉弱'


def test_compute_monthly_structure_close_strict_up_3_field():
    """compute_monthly_structure 回 dict 含 monthly_close_strict_up_3 欄位。"""
    completed = _mbars([
        (10, 12, 8, 11),
        (11, 14, 10, 13),
        (13, 16, 11, 15),
    ])
    inprogress = [_bar(15, 17, 14, 16, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=10)
    assert r['monthly_close_strict_up_3'] is True


def test_compute_monthly_structure_bull_count_6_field():
    """compute_monthly_structure 回 dict 含 monthly_bull_count_6 欄位。"""
    completed = _mbars([
        (10, 12, 8, 11),   # 陽
        (11, 14, 10, 13),  # 陽
        (13, 14, 12, 12),  # 陰（close=open=12 不算陽）
    ])
    inprogress = [_bar(12, 15, 11, 14, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=14, ma60=10)
    assert r['monthly_bull_count_6'] == 2  # 只 2 陽月（不含進行中）


# ---------- F7 §三十二 Bug-5：進行中月強漲否決 ----------
def test_structure_flag_inprogress_strong_up_overrides_inflection():
    """技嘉型：completed 月線陰陽混合（close 不嚴格上揚 + bull_count_6<4），
    但進行中月強漲 +21% 且在 MA60 之上 → 結構未轉弱。"""
    # 12 月陽 / 1 月陰 / 2 月陽 / 3 月陰 / 4 月陽
    completed = _mbars([
        (243.5, 250.5, 232.0, 249.5),  # 12 月陽
        (249.0, 259.0, 231.0, 233.0),  # 1 月陰
        (229.0, 239.5, 219.0, 239.5),  # 2 月陽
        (234.5, 251.0, 206.5, 222.5),  # 3 月陰
        (230.0, 292.0, 222.0, 273.0),  # 4 月陽
    ])
    # 進行中 5 月：open=278, current price=336.5 → 漲幅 +21%
    inprogress = [_bar(278.0, 351.0, 270.5, 336.5, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=336.5, ma60=245)
    assert r['monthly_close_strict_up_3'] is False  # 2/3/4: 239.5,222.5,273 不嚴格升
    assert r['monthly_bull_count_6'] < 4   # 3 個陽月 < 4
    assert r['monthly_inprogress_strong_up'] is True
    assert r['price_vs_ma60'] == '在上'
    assert r['structure_flag'] == '結構未轉弱'


def test_structure_flag_inprogress_mild_change_no_strong_up():
    """進行中月漲幅 < 7% → inprogress_strong_up=False。"""
    completed = _mbars([
        (243.5, 250.5, 232.0, 249.5),
        (249.0, 259.0, 231.0, 233.0),
        (229.0, 239.5, 219.0, 239.5),
        (234.5, 251.0, 206.5, 222.5),
        (230.0, 292.0, 222.0, 273.0),
    ])
    # 進行中月漲幅 +5%（< 7%）
    inprogress = [_bar(278.0, 295.0, 270.5, 292.0, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=292.0, ma60=245)
    assert r['monthly_inprogress_strong_up'] is False


def test_structure_flag_inprogress_strong_up_below_ma60_not_overridden():
    """進行中月強漲但價在 MA60 之下 → 不觸發否決（避免跌深反彈誤判）。"""
    completed = _mbars([
        (10, 12, 8, 9),   # 陰
        (9, 14, 8, 13),   # 陽
        (13, 16, 11, 15), # 陽
    ])
    # 進行中月漲 +30% 但價 16 < ma60 25 → 在下
    inprogress = [_bar(12.3, 17, 11, 16, date='2026-05-01')]
    r = compute_monthly_structure(completed + inprogress, [], price=16, ma60=25)
    assert r['price_vs_ma60'] == '在下'
    assert r['monthly_inprogress_strong_up'] is False  # 在下→不觸發
    assert r['structure_flag'] == '結構已轉弱'
