"""優化2（2026-05-22）— 強勢突破狀態判定。

spec: docs/superpowers/specs/2026-05-22-strong-breakout-tracking-design.md
"""
import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strong_breakout_state, analyze_market_only


def _swingy_daily():
    """峰-谷-升形狀（40 根）：0-9 升至峰、10-19 跌至谷、20-39 再升。
    calc_swing_levels 取得 range_high ≈ idx9 峰高。"""
    closes = ([10, 13, 16, 19, 22, 24, 26, 28, 29, 30,   # 0-9 升（峰）
               28, 26, 24, 22, 20, 18, 17, 16, 15, 14,   # 10-19 跌（谷）
               16, 18, 21, 24, 27, 30, 33, 36, 39, 42,   # 20-29 反彈再升
               44, 46, 48, 49, 50, 51, 52, 53, 54, 55])  # 30-39 續升
    return [{'date': f'2026-{(i // 28) + 3:02d}-{(i % 28) + 1:02d}',
             'open': c - 1, 'high': c + 1, 'low': c - 2,
             'close': c, 'volume_zhang': 1000} for i, c in enumerate(closes)]


def _ed(daily, vt, v5):
    return {'daily_bars': daily, 'volume_zhang': vt, 'volume_5d_avg_zhang': v5}


def test_breakout_true_when_above_range_high_and_volume():
    # 現價遠高於 range_high（≈31），今日量 2000 ≥ 5日均1000×1.5
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5=1000), price_f=999) is True


def test_breakout_false_when_volume_insufficient():
    # 量 1200 < 1000×1.5=1500；price_f=32 剛過 range_high=31 但 < 31×1.05=32.55，
    # 避免觸發新增的條件 B（plan §三十 Bug B）
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=1200, v5=1000), price_f=32) is False


def test_breakout_false_when_price_below_range_high():
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5=1000), price_f=5) is False


def test_breakout_false_on_bad_input():
    assert _strong_breakout_state({'daily_bars': []}, price_f=None) is False
    # price_f=32 同上避免觸發條件 B
    assert _strong_breakout_state(_ed(_swingy_daily(), vt=2000, v5='--'), price_f=32) is False


def test_long_template_has_breakout_branch():
    """強勢突破追蹤分支：plan §三十一 後改由 _render_operation_framework 渲染。
    確認該函式 source 含「強勢突破追蹤」「回測進場（保守）」兩個字串。"""
    from modules.ai_analyzer_v2 import _render_operation_framework
    src = inspect.getsource(_render_operation_framework)
    assert '強勢突破追蹤' in src
    assert '回測進場（保守）' in src


# ---------- 3 條件擇一（2026-05-25, plan §三十 Bug B）----------
def _peak_at_20_daily(closes_35_to_39):
    """構造 40 根含明確局部峰在 idx 20（high=31, close=30）的 daily bars。
    呼叫端指定 closes[35:40] 的尾段 5 根 close 即可。
    open=close-0.5, high=close+1, low=close-1, volume_zhang=1000（除非自定）。
    """
    closes = (list(range(10, 31)) +              # idx 0-20: 升到 30
              [28, 25, 22, 20, 18, 20, 22] +      # idx 21-27: 跌再升
              [25, 28, 32, 36, 40, 44, 48])       # idx 28-34: 續升
    closes = closes + list(closes_35_to_39)       # idx 35-39: 自訂尾段
    assert len(closes) == 40
    return [{'date': f'2026-04-{(i % 28) + 1:02d}',
             'open': c - 0.5, 'high': c + 1, 'low': c - 1,
             'close': float(c), 'volume_zhang': 1000} for i, c in enumerate(closes)]


def test_breakout_true_via_condition_b_continuous_high_close():
    """條件 B：突破 range_high × 1.05 且 近 5 日 close 都 > range_high → True。
    range_high=31，尾段 close=49,50,51,52,53 都 > 31，漲幅僅 1.92% 不觸發 C。"""
    daily = _peak_at_20_daily([49, 50, 51, 52, 53])
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A: 500 < 1000×1.5=1500 不過；C: 漲幅 1.92% 不過 → 只靠 B 過
    assert _strong_breakout_state(ed, price_f=53) is True


def test_breakout_false_when_recent_close_dips_below_range_high():
    """條件 B 失效：近 5 日有任一 close ≤ range_high → 不成立。"""
    daily = _peak_at_20_daily([30, 50, 51, 52, 53])  # idx 35 close=30 ≤ range_high=31
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A 量不過、B 第 1 根 close=30 不站高、C 漲幅 1.92% 不過 → False
    assert _strong_breakout_state(ed, price_f=53) is False


def test_breakout_true_via_condition_c_consecutive_limit_up():
    """條件 C：連 2+ 根漲停型 → True。合晶 5/22~5/26 連 3 根漲停 case。
    F6 §三十二 Bug-4：條件 C 加附加條件「近 3 日 ≥2 根漲停」避免單根衝動誤判。"""
    daily = _peak_at_20_daily([30, 40, 45, 47, 52])  # 倒數第 2 根 close=47, 倒數第 1 = 52
    # 倒數第 2 根改為漲停（idx 38）：昨日 (idx 37) close=45 → 今日漲幅 (47-45)/45 = 4.4% 不夠
    # 先把 idx 37 改成 42.7 → idx 38 close=47 → 漲幅 +10.07%
    daily[37]['close'] = 42.7
    daily[38]['close'] = 47.0  # 漲幅 +10.07%
    # 最後一根（idx 39）一字漲停：昨日 47 → 今日 51.6（漲幅 +9.79%）
    daily[-1] = {
        'date': '2026-04-28',
        'open': 51.6, 'high': 51.6, 'low': 51.6, 'close': 51.6,
        'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A: 500 < 1500 量不過；B: idx 35 close=30 不過 5 根全站高
    # C: 漲幅 9.79% + close=high + 近 3 日 2 根漲停（idx 38 + 39）→ True
    assert _strong_breakout_state(ed, price_f=51.6) is True


def test_breakout_false_via_condition_c_single_limit_up():
    """F6 §三十二 Bug-4：單根一字漲停（前根非漲停）→ False。
    瑞軒 5/22 case（5/21 爆量但非漲停 +18.9%、5/22 才首次一字漲停 +9.83%）→ 5/26 -8.5% 翻車。"""
    daily = _peak_at_20_daily([30, 50, 51, 52, 53])
    # 最後一根一字漲停（昨日 52、今日 57.15 +9.9%），但前一根 53→52 不是漲停
    daily[-1] = {
        'date': '2026-04-28',
        'open': 57.15, 'high': 57.15, 'low': 57.15, 'close': 57.15,
        'volume_zhang': 500,
    }
    daily[-2]['close'] = 52.0
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A: 量不過、B: idx 35=30 不過、C: 漲幅 9.9% ✓ + close=high ✓ + 但近 3 日只 1 根漲停 ✗
    assert _strong_breakout_state(ed, price_f=57.15) is False


def test_breakout_false_when_limit_up_but_below_range_high():
    """漲停但價未過 range_high → 不誤判反彈。"""
    # 構造高峰 ~70 接著跌到低位、最後一根一字漲停但仍 < range_high
    closes = ([50, 55, 60, 65, 70, 68, 65, 62, 58, 55,        # idx 0-9: 升到 70
               50, 45, 40, 35, 30, 25, 20, 16, 13, 10,         # idx 10-19: 跌到 10
               9, 8, 7, 6, 5, 6, 7, 8, 9, 10,                   # idx 20-29: 谷底震盪
               9, 8, 7, 6, 5, 6, 7, 8, 9])                       # idx 30-38
    closes.append(closes[-1] * 1.099)                            # idx 39: 漲停（9.9%）
    daily = [{'date': f'2026-04-{(i % 28) + 1:02d}',
              'open': c - 0.5, 'high': c + 1, 'low': c - 1,
              'close': float(c), 'volume_zhang': 1000} for i, c in enumerate(closes)]
    # 最後一根改為一字漲停
    last_close = closes[-1]
    daily[-1] = {
        'date': '2026-05-01',
        'open': last_close, 'high': last_close, 'low': last_close,
        'close': last_close, 'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # range_high ≈ 71（idx 4 峰），price=9.89 << 71 → 全條件不過
    assert _strong_breakout_state(ed, price_f=last_close) is False


def test_breakout_false_when_close_not_at_high():
    """漲幅夠但 close < high × 0.99（有顯著上影）→ 條件 C 不成立。
    並確保 B 條件也不過（idx 35 close=30 ≤ range_high）。"""
    daily = _peak_at_20_daily([30, 50, 51, 52, 53])
    daily[-2]['close'] = 52.0
    daily[-1] = {
        'date': '2026-04-28',
        'open': 53, 'high': 66, 'low': 53, 'close': 57.15,   # 漲幅 9.9% 但 close/high=0.866
        'volume_zhang': 500,
    }
    ed = {'daily_bars': daily, 'volume_zhang': 500, 'volume_5d_avg_zhang': 1000}
    # A 量不過、B idx 35 close=30 不過、C close/high=0.866 < 0.99 不過 → False
    assert _strong_breakout_state(ed, price_f=57.15) is False
