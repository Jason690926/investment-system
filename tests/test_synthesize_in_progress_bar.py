"""C1 / Bug S1 + W1（2026-05-24）— 合成進行中週/月棒。

根因：Yahoo 1wk/1mo 進行中棒被 Bug A 剔除後，週/月末根 close = 前一交易日日 close
（少當日）。本修法用當日 daily K roll-up 合成「進行中」週/月棒並覆寫/append 到尾端。

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from modules.data_enricher import _synthesize_in_progress_bar


def _df(rows):
    """rows = [(date_str, O, H, L, C, V), ...]"""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {'Open':   [r[1] for r in rows],
         'High':   [r[2] for r in rows],
         'Low':    [r[3] for r in rows],
         'Close':  [r[4] for r in rows],
         'Volume': [r[5] for r in rows]},
        index=idx,
    ).rename_axis('Date')


# ============================================================
# C1-T1：當期 5 個交易日 → close = 最新日 close
# ============================================================
def test_weekly_synthesis_full_week():
    """日K 5/18~5/22（5根），週 K 末根為 5/11（已完成週），
    合成本週（5/18 起）：open=5/18 open, high=max, low=min, close=5/22 close, volume=sum"""
    daily = _df([
        ('2026-05-18', 110, 115, 108, 113, 1000),
        ('2026-05-19', 113, 116, 111, 112, 1100),
        ('2026-05-20', 112, 113, 109, 110, 800),
        ('2026-05-21', 112, 114, 112, 113, 1200),
        ('2026-05-22', 115, 124, 113, 124, 1500),
    ])
    weekly = _df([
        ('2026-05-04', 100, 105, 95, 102, 6500),
        ('2026-05-11', 102, 108, 100, 107, 7000),
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, weekly, 'W', today=today)

    assert len(out) == 3, '應 append 一根進行中週棒，共 3 根'
    last = out.iloc[-1]
    assert out.index[-1] == pd.Timestamp('2026-05-18'), '進行中週日期=本週週一'
    assert last['Open']  == 110, 'open=本週第一日 open'
    assert last['High']  == 124, 'high=本週所有日 max'
    assert last['Low']   == 108, 'low=本週所有日 min'
    assert last['Close'] == 124, 'close=最新日 close (5/22)'
    assert last['Volume'] == 5600, 'volume=本週所有日 sum'


def test_monthly_synthesis_full_period():
    """日K 5/1~5/22（假設 18 根），月 K 末根為 4/1（已完成月），
    合成本月（5/1 起）：open=5/1 open, high=max, low=min, close=最新日 close, volume=sum"""
    daily = _df([
        ('2026-05-01', 100, 105, 99, 103, 1000),
        ('2026-05-08', 103, 108, 102, 107, 1200),
        ('2026-05-15', 107, 110, 105, 109, 900),
        ('2026-05-22', 109, 124, 108, 124, 1500),
    ])
    monthly = _df([
        ('2026-03-01', 90,  95, 85, 92, 50000),
        ('2026-04-01', 92, 100, 90, 99, 60000),
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, monthly, 'M', today=today)

    assert len(out) == 3
    assert out.index[-1] == pd.Timestamp('2026-05-01')
    last = out.iloc[-1]
    assert last['Open']  == 100
    assert last['High']  == 124
    assert last['Low']   == 99
    assert last['Close'] == 124
    assert last['Volume'] == 4600


# ============================================================
# C1-T2：當期 1 個交易日 → 合成棒四價非全相同（取該日 O/H/L/C）
# ============================================================
def test_weekly_synthesis_single_day():
    """連假後本週只有 1 個交易日（5/22 週五），合成棒 = 該日 K"""
    daily = _df([
        ('2026-05-22', 110, 125, 108, 124, 2000),
    ])
    weekly = _df([
        ('2026-05-11', 100, 108, 95, 105, 7000),
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, weekly, 'W', today=today)

    assert len(out) == 2
    last = out.iloc[-1]
    assert last['Open']  == 110
    assert last['High']  == 125
    assert last['Low']   == 108
    assert last['Close'] == 124
    assert last['Volume'] == 2000


# ============================================================
# C1-T3：跨期 — today=6/2，daily 含 5 月末 + 6 月初；月只取 6 月、週取本週
# ============================================================
def test_cross_month_only_picks_current_period():
    """today=2026-06-02 (Tue)，daily 含 5/28~6/2；
    月合成：只取 6/1, 6/2；週合成：當週 6/1~6/2 也只取兩根"""
    daily = _df([
        ('2026-05-28', 80, 85, 79, 84, 500),
        ('2026-05-29', 84, 88, 83, 87, 600),
        ('2026-06-01', 88, 90, 86, 89, 700),
        ('2026-06-02', 89, 95, 88, 95, 1100),
    ])
    today = pd.Timestamp('2026-06-02')

    # 月：current month start = 2026-06-01；in-month = 6/1, 6/2
    monthly = _df([
        ('2026-04-01', 70, 75, 65, 73, 30000),
        ('2026-05-01', 73, 90, 72, 84, 50000),
    ])
    mout = _synthesize_in_progress_bar(daily, monthly, 'M', today=today)
    assert len(mout) == 3
    assert mout.index[-1] == pd.Timestamp('2026-06-01')
    last_m = mout.iloc[-1]
    assert last_m['Open']  == 88, '只取 6/1 open，不取 5/28'
    assert last_m['High']  == 95
    assert last_m['Low']   == 86
    assert last_m['Close'] == 95
    assert last_m['Volume'] == 1800

    # 週：current week start = 2026-06-01 (Monday)；in-week = 6/1, 6/2
    weekly = _df([
        ('2026-05-18', 70, 80, 68, 78, 3000),
        ('2026-05-25', 78, 88, 77, 87, 3500),
    ])
    wout = _synthesize_in_progress_bar(daily, weekly, 'W', today=today)
    assert len(wout) == 3
    assert wout.index[-1] == pd.Timestamp('2026-06-01')
    last_w = wout.iloc[-1]
    assert last_w['Open']  == 88
    assert last_w['Close'] == 95
    assert last_w['Volume'] == 1800


# ============================================================
# C1-T4：daily 末根 < 進行中期間起始 → 不合成
# ============================================================
def test_no_synthesis_when_daily_outside_period():
    """today=5/22，daily 末根 = 5/15（早於本週起始 5/18）→ 不合成"""
    daily = _df([
        ('2026-05-13', 100, 105, 99, 103, 1000),
        ('2026-05-14', 103, 107, 102, 106, 1100),
        ('2026-05-15', 106, 109, 104, 107, 900),
    ])
    weekly = _df([
        ('2026-05-04', 95,  100, 92, 99, 6000),
        ('2026-05-11', 99,  108, 98, 107, 7000),
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, weekly, 'W', today=today)

    # 無變動：仍 2 根
    assert len(out) == 2
    assert out.index[-1] == pd.Timestamp('2026-05-11')


# ============================================================
# C1-T5：daily 為空 → 不合成
# ============================================================
def test_empty_daily_returns_original():
    daily = _df([])
    weekly = _df([
        ('2026-05-11', 100, 108, 99, 107, 7000),
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, weekly, 'W', today=today)

    assert len(out) == 1
    assert out.index[-1] == pd.Timestamp('2026-05-11')


# ============================================================
# C1-T6：period_df 末根 Date == 合成期間起始 → 覆寫不 append
# ============================================================
def test_overwrite_existing_in_progress_bar():
    """若 Yahoo 1mo 沒被 A1 剔除（無 spurious 標記），period_df 已含 5/1 月棒（值滯後）
    合成時應覆寫該根，不是 append（避免重複）"""
    daily = _df([
        ('2026-05-01', 100, 105, 99, 103, 1000),
        ('2026-05-22', 109, 124, 108, 124, 1500),
    ])
    monthly = _df([
        ('2026-04-01', 92, 100, 90, 99, 60000),
        ('2026-05-01', 100, 124, 99, 113, 2500),  # ← Yahoo 滯後值
    ])
    today = pd.Timestamp('2026-05-22')
    out = _synthesize_in_progress_bar(daily, monthly, 'M', today=today)

    # 仍 2 根（覆寫不 append）
    assert len(out) == 2
    last = out.iloc[-1]
    assert out.index[-1] == pd.Timestamp('2026-05-01')
    assert last['Open']  == 100
    assert last['High']  == 124
    assert last['Low']   == 99
    assert last['Close'] == 124, '覆寫後 close=最新日 close 124（非舊值 113）'
    assert last['Volume'] == 2500
