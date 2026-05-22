"""Bug A（2026-05-22）— Yahoo 1wk/1mo spurious 即時棒剔除 + 時區日期校正。

spec: docs/superpowers/specs/2026-05-22-kbar-spurious-bar-fix-design.md
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.data_enricher import _chart_json_to_df, compute_monthly_structure
from modules.ai_analyzer_v2 import _last_bar_in_progress, _render_ktables_html

# 真實 epoch（UTC）；台股 gmtoffset = 28800
WK1 = 1776614400          # 週起始
WK2 = 1777219200
WK3 = 1777824000          # 2026-05-04 00:00 TW（進行中本週的正確聚合）
APR = 1774972800          # 2026-04-01 00:00 TW（月棒）
MAY = 1777564800          # 2026-05-01 00:00 TW（月棒）
RMT = 1779427816          # regularMarketTime（2026-05-22 盤中）


def _d(timestamps, opens, highs, lows, closes, vols, *, rmt=RMT, gmtoffset=28800):
    meta = {'gmtoffset': gmtoffset}
    if rmt is not None:
        meta['regularMarketTime'] = rmt
    return {
        'timestamp': list(timestamps),
        'indicators': {'quote': [{
            'open': list(opens), 'high': list(highs), 'low': list(lows),
            'close': list(closes), 'volume': list(vols),
        }]},
        'meta': meta,
    }


# ---------- A1：剔除 spurious 即時棒 ----------
def test_1wk_drops_spurious_bar():
    """1wk 尾端 ts==regularMarketTime 的 spurious 棒應被剔除。"""
    d = _d([WK1, WK2, WK3, RMT],
           [10, 11, 12, 99], [12, 13, 14, 99], [9, 10, 11, 99],
           [11, 12, 13, 99], [1000, 1100, 1200, 5])
    df = _chart_json_to_df(d, '1wk')
    assert len(df) == 3, '應剩 3 根真實週棒'
    assert df.iloc[-1]['Close'] == 13, '末棒應為正確的本週聚合，非 spurious 99'
    assert df.iloc[-1]['Volume'] == 1200


def test_1mo_drops_spurious_bar():
    """1mo 尾端 spurious 棒同樣剔除。"""
    d = _d([APR, MAY, RMT],
           [20, 21, 88], [25, 26, 88], [18, 19, 88],
           [22, 24, 88], [9000, 9500, 7])
    df = _chart_json_to_df(d, '1mo')
    assert len(df) == 2
    assert df.iloc[-1]['Close'] == 24, '末棒應為本月聚合，非 spurious 88'


# ---------- 回歸保護：不可過砍 ----------
def test_1d_never_drops_even_when_ts_equals_rmt():
    """1d 即使尾端 ts==regularMarketTime 也不剔除（當日日K 本就進行中）。"""
    d = _d([WK1, WK2, RMT],
           [10, 11, 12], [12, 13, 14], [9, 10, 11],
           [11, 12, 13], [1000, 1100, 1200])
    df = _chart_json_to_df(d, '1d')
    assert len(df) == 3, '日K 一根都不可砍'


def test_1wk_keeps_all_when_no_spurious():
    """1wk 尾端非 spurious（ts[-1]!=rmt）→ 不可誤砍進行中聚合棒。"""
    d = _d([WK1, WK2, WK3],
           [10, 11, 12], [12, 13, 14], [9, 10, 11],
           [11, 12, 13], [1000, 1100, 1200], rmt=WK3 + 99999)
    df = _chart_json_to_df(d, '1wk')
    assert len(df) == 3


def test_no_regular_market_time_does_not_crash():
    """meta 缺 regularMarketTime → 不崩、不剔除。"""
    d = _d([WK1, WK2, WK3],
           [10, 11, 12], [12, 13, 14], [9, 10, 11],
           [11, 12, 13], [1000, 1100, 1200], rmt=None)
    df = _chart_json_to_df(d, '1wk')
    assert len(df) == 3


# ---------- A2：時區日期校正 ----------
def test_timezone_offset_applied_to_monthly_date():
    """月棒 ts=2026-05-01 00:00 TW，套 gmtoffset 後日期須為 2026-05-01，
    而非 UTC 伺服器誤算的 2026-04-30。"""
    d = _d([MAY], [44], [47], [43], [46], [50000], rmt=None)
    df = _chart_json_to_df(d, '1mo')
    assert df.index[-1].strftime('%Y-%m-%d') == '2026-05-01'


# ---------- 結構閘視窗：修法後 [:-1] 才真正排除進行中月 ----------
def test_monthly_structure_excludes_in_progress_month():
    """資料源乾淨後（無 spurious 棒），compute_monthly_structure 的 [:-1]
    應丟掉進行中月，monthly_structure 只反映前 3 根已收盤月。"""
    def _mb(o, h, l, c, date):
        return {'date': date, 'open': o, 'high': h, 'low': l,
                'close': c, 'volume_zhang': 1000}
    # 前 4 根已收盤月明確上升趨勢，第 5 根（進行中月）刻意暴跌
    monthly = [
        _mb(10, 12, 8, 11, '2026-01-01'),
        _mb(11, 15, 10, 14, '2026-02-01'),
        _mb(14, 18, 13, 17, '2026-03-01'),
        _mb(17, 21, 16, 20, '2026-04-01'),
        _mb(20, 20, 5, 6, '2026-05-01'),   # 進行中月，須被 [:-1] 排除
    ]
    res = compute_monthly_structure(monthly, [], price=20, ma60=12)
    assert res['monthly_structure'] == '升', '進行中月不應污染結構判定'


# ---------- 決策 6 防禦層：進行中棒標記 ----------
def test_last_bar_in_progress_monthly():
    bars = [{'date': '2026-04-01'}, {'date': '2026-05-01'}]
    assert _last_bar_in_progress(bars, '2026-05-22', 'monthly') is True
    assert _last_bar_in_progress(bars, '2026-06-02', 'monthly') is False


def test_last_bar_in_progress_weekly():
    bars = [{'date': '2026-05-11'}, {'date': '2026-05-18'}]
    assert _last_bar_in_progress(bars, '2026-05-22', 'weekly') is True   # 同週 +4 天
    assert _last_bar_in_progress(bars, '2026-05-27', 'weekly') is False  # 已隔週 +9 天


def test_last_bar_in_progress_daily_kind_none():
    assert _last_bar_in_progress([{'date': '2026-05-22'}], '2026-05-22', None) is False


def test_render_ktables_marks_in_progress():
    """週K/月K 末根標『（進行中）』，日K 不標。"""
    def _eb(date):
        return {'date': date, 'open': 10, 'high': 12, 'low': 9,
                'close': 11, 'volume_zhang': 1000}
    enriched = {
        'daily_bars':   [_eb(f'2026-05-{d:02d}') for d in (18, 19, 20, 21, 22)],
        'weekly_bars':  [_eb('2026-05-04'), _eb('2026-05-11'), _eb('2026-05-18')],
        'monthly_bars': [_eb('2026-03-01'), _eb('2026-04-01'), _eb('2026-05-01')],
    }
    html = _render_ktables_html(enriched)
    assert '2026-05-18（進行中）' in html, '週K 末根應標進行中'
    assert '2026-05-01（進行中）' in html, '月K 末根應標進行中'
    assert '2026-05-22（進行中）' not in html, '日K 不應標進行中'
