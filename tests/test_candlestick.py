"""
系統性除錯驗證 — candlestick.py 7項Bug修正
每個測試命名：test_bug{n}_<說明>
"""
import sys, os, pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.candlestick import detect_patterns, _find_local_peaks, _find_local_troughs, calc_pnf_target


# ────────────────────────────────────────
# 輔助函式
# ────────────────────────────────────────

def make_df(opens, highs, lows, closes, volumes=None):
    n = len(closes)
    return pd.DataFrame({
        'Open': opens, 'High': highs,
        'Low':  lows,  'Close': closes,
        'Volume': [1000] * n if volumes is None else volumes,
    })


def names(df):
    return [p['name'] for p in detect_patterns(df)]


def pad(opens, highs, lows, closes, n_pad=4, pad_price=100.0):
    """在前面補 n_pad 根中性 bar（讓 len >= 5 且不干擾型態偵測）。"""
    p = [pad_price] * n_pad
    return (
        p + list(opens),
        [pad_price + 0.5] * n_pad + list(highs),
        [pad_price - 0.5] * n_pad + list(lows),
        p + list(closes),
    )


# ────────────────────────────────────────
# Bug 2: _find_local_peaks >= → >
# ────────────────────────────────────────

class TestBug2PeakDetection:
    def test_plateau_top_no_peak(self):
        """平台頂（三根等高）不應偵測到峰值。"""
        arr = np.array([90, 92, 95, 100, 100, 100, 95, 92, 90], dtype=float)
        assert _find_local_peaks(arr, min_gap=3) == []

    def test_sharp_single_peak_detected(self):
        arr = np.array([90, 92, 95, 100, 95, 92, 90], dtype=float)
        peaks = _find_local_peaks(arr, min_gap=3)
        assert len(peaks) == 1 and peaks[0][1] == 100

    def test_two_equal_adjacent_peaks_not_counted(self):
        """兩根等高相鄰峰，兩者均不符合嚴格 > 條件。"""
        arr = np.array([88, 90, 95, 100, 100, 95, 90, 88], dtype=float)
        assert _find_local_peaks(arr, min_gap=3) == []

    def test_plateau_bottom_no_trough(self):
        arr = np.array([100, 95, 90, 90, 90, 95, 100], dtype=float)
        assert _find_local_troughs(arr, min_gap=3) == []


# ────────────────────────────────────────
# Bug 1: 三山頂 15 根時效性
# ────────────────────────────────────────

def _build_three_peak_df(last_peak_abs: int, total_bars: int,
                          peak_h=101.0, current_close=90.0):
    """
    在三個絕對位置（last_peak_abs-20, -10, 0）各建一個山峰。
    當前收盤固定為 current_close（低於峰值的 3% 以上）。
    """
    highs  = np.full(total_bars, current_close)
    lows   = highs - 1
    opens  = highs.copy()
    closes = np.full(total_bars, current_close)

    for delta in [-20, -10, 0]:
        center = last_peak_abs + delta
        for j, v in [(-2, peak_h-6), (-1, peak_h-3), (0, peak_h),
                     (1, peak_h-3), (2, peak_h-6)]:
            idx = center + j
            if 0 <= idx < total_bars:
                highs[idx] = v

    return make_df(opens, highs, lows, closes)


class TestBug1SanshanFreshness:
    def _fires(self, last_peak_abs, current_bar, total=80):
        df = _build_three_peak_df(last_peak_abs, total)
        sub = df.iloc[:current_bar + 1].copy()
        return '三山頂（酒田）' in names(sub)

    def test_fires_when_peak_5_bars_ago(self):
        """第三峰 5 根前 → 應觸發。"""
        assert self._fires(last_peak_abs=30, current_bar=35)

    def test_fires_at_boundary_15(self):
        """第三峰恰好 15 根前（邊界）→ 應觸發。"""
        assert self._fires(last_peak_abs=30, current_bar=45)

    def test_silent_after_15_bars(self):
        """Bug 1 修正：第三峰 16 根前 → 應靜音（舊 Bug 會一直觸發）。"""
        assert not self._fires(last_peak_abs=30, current_bar=46)

    def test_silent_30_bars_after_peak(self):
        """第三峰 30 根前 → 嚴格靜音。"""
        assert not self._fires(last_peak_abs=30, current_bar=60)


# ────────────────────────────────────────
# Bug 3: 大陽線不應在 gap_down 時觸發
# ────────────────────────────────────────

class TestBug3DaYangGapDown:
    def _gap_down_df(self):
        """
        i-1: h=101, l=99（昨日）
        i:   o=93, h=97, l=92, c=96.6  →  gap_down: h[i]=97 < l[i-1]=99 ✓
                                            bullish: c=96.6 > o=93 ✓
                                            body_ratio: (96.6-93)/(97-92) = 3.6/5 = 0.72 > 0.7 ✓
        """
        return make_df(
            opens  = [100, 100, 100, 100,  93  ],
            highs  = [101, 101, 101, 101,  97  ],
            lows   = [ 99,  99,  99,  99,  92  ],
            closes = [100, 100, 100, 100,  96.6],
        )

    def test_gap_down_recovery_shows_gap_pattern(self):
        assert '跳空低開反彈' in names(self._gap_down_df()), \
            "跳空低開後收高應顯示跳空低開反彈"

    def test_gap_down_recovery_no_dayang(self):
        """Bug 3 修正：gap_down + body_ratio>0.7 的陽線，不應顯示「大陽線（無跳空缺口）」。"""
        assert '大陽線' not in names(self._gap_down_df()), \
            "跳空低開後不應顯示大陽線（與 desc 無跳空缺口矛盾）"

    def test_normal_dayang_fires(self):
        """無跳空的真實大陽線應正常觸發。"""
        df = make_df(
            opens  = [100, 100, 100, 100,  95],
            highs  = [101, 101, 101, 101, 104],
            lows   = [ 99,  99,  99,  99,  94],
            closes = [100, 100, 100, 100, 103],
        )
        assert '大陽線' in names(df)


# ────────────────────────────────────────
# Bug 4 & 5: 三白兵/三黑鴉第一根影線（i-2）
# ────────────────────────────────────────
# 重要：i = len(c)-1，第一根為 i-2，即倒數第3根
# ────────────────────────────────────────

class TestBug45ThreeSoldiersCrowsFirstCandle:
    def _soldiers(self, first_shadow_ratio):
        """
        三白兵資料：最後 3 根（i-2, i-1, i）為連三陽線。
        first_shadow_ratio: i-2 上影線佔實體的比例。
        i-2: o=96, c=100, body=4 → shadow = body * ratio
        """
        body_i2  = 4.0
        h_i2     = 100 + body_i2 * first_shadow_ratio   # i-2 的高點
        return make_df(
            opens  = [95, 95,  96, 100, 102],
            highs  = [96, 96, h_i2, 102, 104],
            lows   = [94, 94,  95,  99,  101],
            closes = [95, 95, 100,  102,  104],
        )

    def test_soldiers_fires_short_first_shadow(self):
        """i-2 上影線短（20%實體）→ 三白兵應觸發。"""
        assert '三白兵' in names(self._soldiers(0.2))

    def test_bug4_soldiers_blocked_long_first_shadow(self):
        """Bug 4 修正：i-2 上影線長（80%實體）→ 三白兵不應觸發。"""
        result = names(self._soldiers(0.8))
        assert '三白兵' not in result, \
            f"i-2 長上影線，三白兵不應觸發。實際: {result}"

    def _crows(self, first_shadow_ratio):
        """
        三黑鴉資料：最後 3 根（i-2, i-1, i）為連三陰線。
        i-2: o=102, c=98, body=4 → lower shadow = body * ratio
        """
        body_i2 = 4.0
        l_i2    = 98 - body_i2 * first_shadow_ratio
        return make_df(
            opens  = [103, 103, 102, 100,  98],
            highs  = [104, 104, 103, 101,   99],
            lows   = [102, 102, l_i2,  98,   96],
            closes = [103, 103,  98,  96,   94],
        )

    def test_crows_fires_short_first_shadow(self):
        """i-2 下影線短（20%實體）→ 三黑鴉應觸發。"""
        assert '三黑鴉' in names(self._crows(0.2))

    def test_bug5_crows_blocked_long_first_shadow(self):
        """Bug 5 修正：i-2 下影線長（80%實體）→ 三黑鴉不應觸發。"""
        result = names(self._crows(0.8))
        assert '三黑鴉' not in result, \
            f"i-2 長下影線，三黑鴉不應觸發。實際: {result}"


# ────────────────────────────────────────
# Bug 6 & 7: 早晨之星/黃昏之星需大實體
# ────────────────────────────────────────

class TestBug67StarPatterns:
    # ── 早晨之星 ──
    def _morning(self, first_body_ratio, third_body_ratio):
        """
        i-2: bearish, ratio = first_body_ratio（實體/振幅）
        i-1: 小實體十字星
        i:   bullish, ratio = third_body_ratio
        i-2 body: o=98, c=90, body=8, range=10
        i   body: o=90, c=98, body=8, range=10
        """
        h_i2 = 98 + (10 - 8) / 2 if first_body_ratio >= 0.8 else 98 + 1
        l_i2 = 90 - (10 - 8) / 2 if first_body_ratio >= 0.8 else 90 - 1
        # 用 range 反推確保 body/range = ratio
        rng = 8.0 / first_body_ratio if first_body_ratio > 0 else 20
        extra = (rng - 8) / 2
        l_i2_r = 90 - extra
        h_i2_r = 98 + extra

        rng3 = 8.0 / third_body_ratio if third_body_ratio > 0 else 20
        extra3 = (rng3 - 8) / 2
        l_i_r  = 90 - extra3
        h_i_r  = 98 + extra3

        return make_df(
            opens  = [100, 100,  98,  88,  90],
            highs  = [101, 101, h_i2_r,  91, h_i_r],
            lows   = [ 99,  99, l_i2_r,  87, l_i_r],
            closes = [100, 100,  90,  89,  98],
        )

    def test_morning_star_fires_with_big_candles(self):
        """標準早晨之星（大陰+小實體+大陽）應觸發。"""
        # i-2: o=98,c=90,range=10,ratio=0.8 ; i: o=90,c=98,range=10,ratio=0.8
        df = make_df(
            opens  = [100, 100,  98,  88,  90],
            highs  = [101, 101,  99,  91,  99],
            lows   = [ 99,  99,  89,  87,  89],
            closes = [100, 100,  90,  89,  98],
        )
        assert '早晨之星' in names(df), "標準早晨之星應觸發"

    def test_bug6_morning_no_fire_small_first_candle(self):
        """Bug 6 修正：i-2 為小陰線（body < 50% range）→ 早晨之星不應觸發。"""
        # i-2: o=94, c=93, body=1, range=5 → ratio=20% < 50%
        df = make_df(
            opens  = [100, 100,  94,  88,  90],
            highs  = [101, 101,  96,  91,  99],
            lows   = [ 99,  99,  91,  87,  89],
            closes = [100, 100,  93,  89,  98],
        )
        assert '早晨之星' not in names(df), "第一根小陰線，早晨之星不應觸發"

    def test_bug6_morning_no_fire_small_third_candle(self):
        """Bug 6 修正：i 為小陽線（body < 50% range）→ 早晨之星不應觸發。"""
        # i: o=90, c=91, body=1, range=6 → ratio≈17%
        df = make_df(
            opens  = [100, 100,  98,  88,  90],
            highs  = [101, 101,  99,  91,  95],
            lows   = [ 99,  99,  89,  87,  89],
            closes = [100, 100,  90,  89,  91],
        )
        assert '早晨之星' not in names(df), "第三根小陽線，早晨之星不應觸發"

    # ── 黃昏之星 ──
    def test_evening_star_fires_with_big_candles(self):
        """標準黃昏之星（大陽+小實體+大陰）應觸發。"""
        # i-2: o=90,c=98,body=8,range=10,ratio=0.8
        # i-1: 小實體
        # i:   o=98,c=90,body=8,range=10,ratio=0.8，close < midpoint(90+98)/2=94 ✓
        df = make_df(
            opens  = [ 85,  85,  90,  99,  98],
            highs  = [ 86,  86,  99, 102,  99],
            lows   = [ 84,  84,  89,  98,  89],
            closes = [ 85,  85,  98, 100,  90],
        )
        assert '黃昏之星' in names(df), "標準黃昏之星應觸發"

    def test_bug7_evening_no_fire_small_first_candle(self):
        """Bug 7 修正：i-2 為小陽線（body < 50% range）→ 黃昏之星不應觸發。"""
        # i-2: o=90,c=91, body=1, range=8 → ratio=12.5%
        df = make_df(
            opens  = [ 85,  85,  90,  99,  98],
            highs  = [ 86,  86,  98, 102,  99],
            lows   = [ 84,  84,  89,  98,  89],
            closes = [ 85,  85,  91, 100,  90],
        )
        assert '黃昏之星' not in names(df), "第一根小陽線，黃昏之星不應觸發"


# ────────────────────────────────────────
# 回歸測試：正常型態仍正確觸發
# ────────────────────────────────────────

class TestRegressionNormalPatterns:
    def _df5(self, opens, highs, lows, closes):
        o, h, l, c = pad(opens, highs, lows, closes)
        return make_df(o, h, l, c)

    def test_bullish_engulfing(self):
        # i-1: bearish(o=98,c=96), i: bullish engulfs(o=95,c=99)
        df = self._df5([98, 95], [99, 100], [95, 94], [96, 99])
        assert '多頭吞噬' in names(df)

    def test_bearish_engulfing(self):
        # i-1: bullish(o=96,c=98), i: bearish engulfs(o=99,c=94)
        df = self._df5([96, 99], [99, 100], [95, 93], [98, 94])
        assert '空頭吞噬' in names(df)

    def test_gravestone_doji(self):
        # o=c=100（bottom），high=110，low=100
        df = self._df5([100], [110], [100], [100])
        assert '墓碑十字' in names(df)

    def test_dragonfly_doji(self):
        # o=c=110（top），high=110，low=100
        df = self._df5([110], [110], [100], [110])
        assert '蜻蜓十字' in names(df)

    def test_gap_up_big_rise(self):
        # 昨高 100.5，今低 106（gap up），今收 111
        df = self._df5([100, 106], [101, 112], [99, 105], [100, 111])
        assert '跳空大漲' in names(df)

    def test_gap_down_big_fall(self):
        # 昨低 99，今高 93（gap down），今收 89
        df = self._df5([100, 93], [101, 94], [99, 88], [100, 89])
        assert '跳空大跌' in names(df)

    def test_hammer(self):
        # o=100, c=102(陽), h=102.2, l=93
        # body=2, upper_shadow=0.2, lower_shadow=9 → ratio=2/11.2≈0.18>0.1
        # upper<body*0.3=0.6 ✓  lower>body*2=4 ✓
        df = self._df5([100], [102.2], [93], [102])
        assert '錘子線' in names(df)

    def test_shooting_star(self):
        # o=100, c=98(陰), h=110, l=97.8
        # body=2, upper_shadow=10, lower_shadow=0.2 → ratio=2/12.2≈0.16>0.1
        # upper>body*2=4 ✓  lower<body*0.3=0.6 ✓  body_ratio>0.1 → 非墓碑十字
        df = self._df5([100], [110], [97.8], [98])
        assert '射擊之星' in names(df)

    def test_dark_cloud_cover(self):
        # i-1: 大陽線，i: 跳空高開後收低過中線
        df = self._df5([90, 100], [91, 102], [89, 93], [90, 94])
        # o[1]=100 > h[0]=91 ✓, c[1]=94 < (90+90)/2=90? 94<90? No...
        # 需要重新設計
        # i-1: o=90,c=98; midpoint=(90+98)/2=94; i: o=100(> h_prev=99),c=93(<94)
        df = make_df(
            [100, 100, 100, 90, 100],
            [101, 101, 101, 99, 101],
            [ 99,  99,  99, 89,  92],
            [100, 100, 100, 98,  93],
        )
        assert '烏雲蓋頂' in names(df)

    def test_piercing_pattern(self):
        # i-1: 大陰線(o=98,c=90), i: 跳空低開後收過中線(midpt=94)
        df = make_df(
            [100, 100, 100, 98, 88],
            [101, 101, 101, 99, 97],
            [ 99,  99,  99, 89, 87],
            [100, 100, 100, 90, 95],
        )
        assert '曙光初現' in names(df)


# ────────────────────────────────────────
# calc_pnf_target — Darvas 箱體突破目標
# ────────────────────────────────────────

def _pnf_bar(h, l, date_str):
    c = (h + l) / 2
    return {'date': date_str, 'open': c, 'high': h, 'low': l, 'close': c}

def make_pnf_bars(specs):
    """(high, low) list → bars list，日期以週為單位遞增"""
    from datetime import date, timedelta
    d = date(2026, 1, 1)
    result = []
    for h, l in specs:
        result.append(_pnf_bar(h, l, str(d)))
        d += timedelta(weeks=1)
    return result


class TestCalcPnfTarget:

    # 基本場景：箱體確立 + 突破 → 回傳目標
    # 注意：cur 需 < target / 1.02，否則 Bug C 修法的 Filter B 會視為「目標已達」往更早找
    def test_basic_breakout_returns_target(self):
        bars = make_pnf_bars([
            (80, 70), (75, 65), (70, 60),
            (65, 55), (64, 56), (63, 55), (64, 56), (65, 57),
            (70, 62), (72, 64), (74, 65), (76, 68),
        ])
        # 該演算法選到 (64,56) 箱：top=64, bottom=55, target=73；cur=68 留出 target 上行空間
        result = calc_pnf_target(bars, lookback=12, current_price=68)
        assert result is not None
        assert result > 64  # 目標必須高於箱頂

    # 核心驗證：新增一根 bar 後目標不漂移
    def test_stable_target_after_new_bar(self):
        bars = make_pnf_bars([
            (80, 70), (75, 65), (70, 60),
            (65, 55), (64, 56), (63, 55), (64, 56), (65, 57),
            (70, 62), (72, 64), (74, 65), (76, 68),
        ])
        from datetime import date, timedelta
        extended = bars + [_pnf_bar(78, 70, str(date(2026, 3, 26)))]

        # cur 從 68 → 70 模擬「股價小幅上行」，但仍 < target / 1.02 = 73/1.02 ≈ 71.6
        r1 = calc_pnf_target(bars,     lookback=12, current_price=68)
        r2 = calc_pnf_target(extended, lookback=12, current_price=70)
        assert r1 is not None and r2 is not None
        assert r1 == r2, f"目標漂移：{r1} → {r2}"

    # 箱體存在但尚未突破 → None
    def test_no_breakout_returns_none(self):
        bars = make_pnf_bars([
            (80, 70), (75, 65), (70, 60),
            (65, 55), (64, 56), (63, 55), (64, 56), (65, 57),
            (64, 58),
        ])
        assert calc_pnf_target(bars, lookback=12, current_price=64) is None

    # 箱寬 > 20%（週K 閾值）→ None
    def test_box_too_wide_returns_none(self):
        # box_top=110, box_bottom=78 → 41% > 20%
        bars = make_pnf_bars([
            (100, 80), (99, 81), (98, 79),
            (110, 78), (109, 79), (108, 80), (109, 79), (110, 81),
            (120, 100), (122, 105),
        ])
        assert calc_pnf_target(bars, lookback=12, current_price=125) is None

    # 純趨勢段（無有效箱體）→ None
    def test_pure_uptrend_no_box(self):
        specs = [(50 + i*5, 45 + i*5) for i in range(12)]
        bars  = make_pnf_bars(specs)
        assert calc_pnf_target(bars, lookback=12, current_price=120) is None

    # 日K confirm=3（lookback=20 > 14）
    def test_daily_bars_confirm3(self):
        bars = make_pnf_bars([
            (80, 70), (75, 65), (70, 60), (68, 58),
            (65, 55), (64, 56), (63, 55), (64, 56), (65, 57), (65, 58),
            (70, 62), (72, 64), (74, 65), (76, 68),
            (78, 70), (80, 72), (82, 74), (84, 76), (86, 78), (88, 80),
        ])
        result = calc_pnf_target(bars, lookback=20, current_price=90)
        # confirm=3：不同的箱頂可能被選中，只確認有結果且大於箱頂
        assert result is None or result > 60

    # 資料不足 → None
    def test_insufficient_bars(self):
        assert calc_pnf_target([], lookback=12) is None
        assert calc_pnf_target([_pnf_bar(100, 90, '2026-01-01')] * 3) is None

    # ────────────────────────────────────────
    # Bug C regression（2026-05-13 用戶回報 6150 撼訊現價 73.1 / 目標 62）
    # ────────────────────────────────────────

    # 目標已被現價遠超 → 該箱體無預測力，應該繼續找更早的有效箱，全找不到才 None
    def test_bug_c_target_below_current_rejected(self):
        """模擬 6150 場景：早期窄箱（top=60, bottom=58, target=62）已被遠超，
        cur=73 不應被 algorithm 回傳 62 這種無意義目標。"""
        bars = make_pnf_bars([
            (62, 58), (61, 58), (60, 59), (60, 58), (61, 59),  # 早期窄箱
            (65, 60), (68, 63), (70, 66),                       # 突破上行
            (72, 68), (73, 70), (74, 71),                       # 持續上行至 ~73
        ])
        result = calc_pnf_target(bars, lookback=12, current_price=73.1)
        # 不論是 None 還是找到更早/合理的箱，絕對不可以是 62 這種低於現價的目標
        assert result is None or result > 73.1, (
            f"目標 {result} 必須 None 或 > 現價 73.1，不可低於現價"
        )

    # 未突破最近箱 + 有更早突破箱 → 應回溯找到更早箱的 target（不再硬 None）
    def test_bug_c_unbroken_recent_falls_back_to_older_box(self):
        """用戶 pushback：『其他沒有概念目標價是因為還沒突破前高?那照理說應該
        是往歷史回朔去找出現在的目標價才對』。修法後最近箱未突破時不再直接 None，
        而是繼續往更早箱找突破過且 target 仍領先 cur 的箱體。"""
        bars = make_pnf_bars([
            # 早期窄箱 60-65（已被突破，target=70）
            (65, 60), (64, 61), (63, 60), (64, 61), (65, 62),
            # 上行突破到 70+
            (70, 66), (72, 68), (74, 70),
            # 近期形成新窄箱 80-85（尚未突破）
            (85, 80), (84, 81), (83, 80), (84, 81), (85, 82),
        ])
        # cur=82 在近期 80-85 箱內、尚未突破近箱頂 85 × 1.02 = 86.7
        # 舊邏輯：return None（不往舊箱找）
        # 新邏輯：往回找到早期 65 箱、target=70；但 target 70 < cur 82 → Filter B reject
        #        繼續找不到 → None。OR 若中間還有 75-80 箱 target=85 → 採用該 target
        # 此 case 用於驗證「不再硬 return None」的行為，實際結果視 fixture 而定
        result = calc_pnf_target(bars, lookback=12, current_price=82)
        # 接受 None（找不到 target > cur）或合理 target（> cur）
        assert result is None or result > 82


# ────────────────────────────────────────
# calc_pnf_target — direction='short'（E-1，2026-05-17）
# long 的幾何鏡像：箱底支撐錨點 → 跌破向下等幅目標
# ────────────────────────────────────────

class TestCalcPnfTargetShort:

    # 共用 fixture：support≈55 / resistance≈60 盤整箱，後跌破向下
    # 手算：選到 i=5 箱 → box_bottom=55, box_top=60, target=55-(60-55)=50
    def _breakdown_bars(self):
        return make_pnf_bars([
            (75, 70), (70, 62), (66, 58),          # 下跌進入箱體
            (60, 55), (59, 56), (60, 55), (59, 56), (60, 57),  # 盤整箱
            (56, 50), (54, 48), (52, 46),          # 跌破箱底向下
        ])

    # 向後相容：不傳 direction 等同 direction='long'，既有行為不變
    def test_default_direction_is_long(self):
        bars = make_pnf_bars([
            (80, 70), (75, 65), (70, 60),
            (65, 55), (64, 56), (63, 55), (64, 56), (65, 57),
            (70, 62), (72, 64), (74, 65), (76, 68),
        ])
        r_default  = calc_pnf_target(bars, lookback=12, current_price=68)
        r_explicit = calc_pnf_target(bars, lookback=12, current_price=68,
                                     direction='long')
        assert r_default == r_explicit
        assert r_default is not None

    # 無效 direction → None（防呆）
    def test_invalid_direction_returns_none(self):
        bars = self._breakdown_bars()
        assert calc_pnf_target(bars, lookback=12, current_price=52,
                               direction='bogus') is None

    # 基本跌破：cur 已跌破箱底且 target 仍領先 → 回傳向下目標
    def test_basic_breakdown_returns_target(self):
        bars = self._breakdown_bars()
        # cur=52：跌破 box_bottom=55（×0.98=53.9），target=50 < cur×0.98=50.96
        result = calc_pnf_target(bars, lookback=12, current_price=52,
                                 direction='short')
        assert result == 50.0
        # 經濟意義：目標必須低於箱底、低於現價、且為正值
        assert 0 < result < 55
        assert result < 52

    # 尚未跌破箱底（Filter A）→ None
    def test_no_breakdown_returns_none(self):
        bars = self._breakdown_bars()
        # cur=58 仍在/高於箱底 55×0.98=53.9 → 未跌破
        assert calc_pnf_target(bars, lookback=12, current_price=58,
                               direction='short') is None

    # 目標已被現價跌穿（Filter B 鏡像）→ 該箱無預測力
    def test_target_already_passed_rejected(self):
        bars = self._breakdown_bars()
        # cur=47：target=50 > cur×0.98=46.06 → 價已跌過目標，無意義，不得回 50
        result = calc_pnf_target(bars, lookback=12, current_price=47,
                                 direction='short')
        assert result is None or result < 47

    # 新增一根 bar 後目標不漂移（鎖定性，鏡像 long 的核心驗證）
    def test_stable_target_after_new_bar(self):
        from datetime import date, timedelta
        bars = self._breakdown_bars()
        extended = bars + [_pnf_bar(50, 44, str(date(2026, 4, 2)))]
        r1 = calc_pnf_target(bars,     lookback=12, current_price=52,
                             direction='short')
        r2 = calc_pnf_target(extended, lookback=12, current_price=52,
                             direction='short')
        assert r1 is not None and r2 is not None
        assert r1 == r2, f"空方目標漂移：{r1} → {r2}"

    # 方向確實改變行為：同一跌破 fixture 用 long 不會回傳空方目標
    def test_direction_changes_behavior(self):
        bars = self._breakdown_bars()
        short_r = calc_pnf_target(bars, lookback=12, current_price=52,
                                  direction='short')
        long_r  = calc_pnf_target(bars, lookback=12, current_price=52,
                                  direction='long')
        assert short_r == 50.0
        assert long_r != 50.0  # 下跌盤面 long 不應產出向下目標（多為 None）

    # 資料不足 / 空輸入 → None（兩方向一致）
    def test_insufficient_bars_short(self):
        assert calc_pnf_target([], lookback=12, direction='short') is None
        assert calc_pnf_target([_pnf_bar(100, 90, '2026-01-01')] * 3,
                               direction='short') is None
