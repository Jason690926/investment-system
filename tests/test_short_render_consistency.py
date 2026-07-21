"""
§四十一（2026-07-17）— short 渲染層一致性三修法

F1：§5 目標與 pill/§4 同源（call site 覆寫 _sl['target'] = target_pnf）
    + framework guard（short 空標須<price、long 目標須>price，否則「—」）
F2：空停統一 raw range_high（砍 ×1.03）+ pill 空進改區間 entry_low~entry_high
F3：pill 含「論點作廢」→ §5 誠實版（砍空進區/空標，保留失效價 + 等新結構）

測試策略：framework/anchors 走純函式；F1 call-site 覆寫以 source guard 防回退
（同 §三十七 test_call_sites_use_watch_not_hold 手法）；app.py pill 直接斷言
_render_one_block 輸出 HTML。
"""
import sys, os, datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.ai_analyzer_v2 import (
    _render_operation_framework,
    _resolve_swing_anchors,
)
import app as appmod


# ── F1：framework 目標 guard ──────────────────────────────────────
class TestF1TargetGuard:
    _sl_short = {'range_high': 210.5, 'range_low': 190,
                 'entry_zone': (204.19, 210.5), 'invalidation': 210.5,
                 'target': 232.0}

    def test_short_target_above_price_shows_dash(self):
        """晶心科 7/16：空標 232 > 現價 228 → §5 顯示「—」（stale 分析防護）。"""
        html = _render_operation_framework(
            action_pill='🟡 等反彈佈空', direction='short',
            swing_levels=self._sl_short, breakout=False, price=228.0)
        # §四十六 Fix C 配對改：「— 元」殘句砍除，改乾淨誠實句
        assert '空標：—（無有效箱體，等新箱形成）' in html, \
            f'空標高於現價應顯示 —，實際：\n{html}'
        assert '232.00' not in html

    def test_short_target_below_price_shown(self):
        """正常 short：空標 190 < 現價 228 → 正常顯示。"""
        sl = {**self._sl_short, 'target': 190.0}
        html = _render_operation_framework(
            action_pill='🟡 等反彈佈空', direction='short',
            swing_levels=sl, breakout=False, price=228.0)
        assert '空標：190.00 元' in html

    def test_long_target_below_price_shows_dash(self):
        """long 鏡像：目標 ≤ 現價 → 「—」。"""
        sl = {'range_high': 105, 'range_low': 96.8,
              'entry_zone': (96.8, 100.9), 'invalidation': 96.8,
              'target': 98.0}
        html = _render_operation_framework(
            action_pill='🟢 進場區可佈', direction='long',
            swing_levels=sl, breakout=False, price=99.0)
        # §四十六 Fix C 配對改：「— 元」殘句砍除，改乾淨誠實句
        assert '目標：—（無有效箱體，等新箱形成）' in html
        assert '98.00 元' not in html

    def test_long_target_above_price_shown(self):
        """回歸：long 目標 > 現價 → 正常顯示不受 guard 影響。"""
        sl = {'range_high': 105, 'range_low': 96.8,
              'entry_zone': (96.8, 100.9), 'invalidation': 96.8,
              'target': 120.0}
        html = _render_operation_framework(
            action_pill='🟢 進場區可佈', direction='long',
            swing_levels=sl, breakout=False, price=99.0)
        assert '目標：120.00 元' in html

    def test_price_none_no_guard(self):
        """price 缺（呼叫端異常）→ 不做 guard，照原值顯示（向後相容）。"""
        html = _render_operation_framework(
            action_pill='🟡 等反彈佈空', direction='short',
            swing_levels=self._sl_short, breakout=False, price=None)
        assert '空標：232.00 元' in html

    def test_call_sites_overwrite_target_with_target_pnf(self):
        """F1 call-site source guard：兩個 analyze 函式在 render 前
        須把 _sl['target'] 覆寫為 result['target_pnf']（§5 與 pill/§4 同源）。"""
        import inspect
        src = inspect.getsource(sys.modules['modules.ai_analyzer_v2'])
        n = src.count("'target': result.get('target_pnf')")
        assert n >= 2, f"兩 call site 應各有一次 target 同源覆寫，實際 {n} 次"


# ── F3：論點作廢誠實 §5 ──────────────────────────────────────────
class TestF3InvalidatedHonestFramework:
    _sl = {'range_high': 210.5, 'range_low': 190,
           'entry_zone': (204.19, 210.5), 'invalidation': 210.5,
           'target': 190.0}

    def test_invalidated_pill_cuts_entry_and_target(self):
        """pill=🔴 論點作廢 → §5 不給空進區/空標，保留失效價 + 等新結構。"""
        html = _render_operation_framework(
            action_pill='🔴 論點作廢', direction='short',
            swing_levels=self._sl, breakout=False, price=228.0)
        assert '空進：' not in html, '論點作廢不該再給空進區'
        assert '空標：' not in html, '論點作廢不該再給空標'
        assert '210.50' in html, '應保留客觀失效價'
        assert '論點作廢' in html
        assert '站回' in html, '應說明價已站回失效價上方'
        assert '新結構' in html, '應提示等新結構形成'

    def test_normal_short_pill_keeps_full_frame(self):
        """回歸：一般 short pill → 空進/空停/空標 完整框架不退化。"""
        html = _render_operation_framework(
            action_pill='🔴 分批佈空', direction='short',
            swing_levels=self._sl, breakout=False, price=207.0)
        assert '空進：204.19 ~ 210.50 元' in html
        assert '空停：210.50 元' in html
        assert '空標：190.00 元' in html


# ── F2：anchors raw 化 ────────────────────────────────────────────
def _bar(date_str, h, l, c=None):
    c = c if c is not None else (h + l) / 2
    return {'date': date_str, 'open': c, 'high': h, 'low': l,
            'close': c, 'volume_zhang': 1000}


def _make_bars(highs_lows, start_date='2026-01-01'):
    from datetime import date as dt_date, timedelta
    d = dt_date.fromisoformat(start_date)
    bars = []
    for h, l in highs_lows:
        bars.append(_bar(d.isoformat(), h, l))
        d += timedelta(days=1)
    return bars


class TestF2StopLossRaw:
    _swing_bars = [
        (100, 95), (102, 96), (105, 98), (108, 100),
        (110, 105), (112, 106), (115, 108),
        (113, 109), (110, 105), (108, 102),
        (106, 100), (104, 98), (102, 95),
        (100, 92), (98, 90),
        (102, 95), (105, 98), (108, 100),
        (110, 104), (112, 106), (115, 108),
        (113, 109), (110, 105),
    ]

    def test_stop_loss_equals_range_high_raw(self):
        """空停 = raw range_high（不再 ×1.03、不 round）→ 與 §5/§3/作廢 gate 同值。"""
        bars = _make_bars(self._swing_bars)
        r = _resolve_swing_anchors({'daily_bars': bars}, 108.0, 'short')
        assert r['stop_loss_anchor'] is not None
        assert r['stop_loss_anchor'] == r['resistance_anchor'], (
            f"空停 {r['stop_loss_anchor']} 應 == range_high {r['resistance_anchor']}"
        )

    def test_fallback_stop_loss_raw_20d_high(self):
        """swing 算不出時 fallback = 近20日最高（raw，不 ×1.03）。"""
        flat = _make_bars([(100, 95)] * 30)
        r = _resolve_swing_anchors({'daily_bars': flat}, 97.0, 'short')
        assert r['stop_loss_anchor'] == 100.0


# ── F2：app.py short pill 空進區間 ────────────────────────────────
def _q(close, prev=None):
    return SimpleNamespace(close=close,
                           prev_close=prev if prev is not None else close,
                           cache_date=datetime.date(2026, 7, 17))


def _stock(symbol='6533', name='測試股', status='holding',
           avg_cost=355.0, total_zhang=2.0, trades=True):
    return SimpleNamespace(symbol=symbol, name=name, status=status,
                           avg_cost=avg_cost, total_zhang=total_zhang, trades=trades)


def _analysis(**kw):
    base = dict(html_content='<p>分析內文</p>', support_price=None,
                resistance_price=None, target_price=None, stop_loss=None,
                entry_low=None, entry_high=None, wyckoff_phase=None,
                risk_pct=35, action_pill=None)
    base.update(kw)
    return SimpleNamespace(**base)


class TestF2ShortEntryPillRange:
    def _short_analysis(self, **kw):
        base = dict(wyckoff_phase='下跌', support_price=190,
                    resistance_price=210.5, stop_loss=210.5,
                    entry_low=204.19, entry_high=210.5,
                    target_price=190, action_pill='🟡 等反彈佈空')
        base.update(kw)
        return _analysis(**base)

    def test_short_entry_pill_shows_range(self):
        """空進 pill 顯示區間 entry_low~entry_high（區下緣才是可操作價）。"""
        a = self._short_analysis()
        html = appmod._render_one_block(_stock(), a, _q(207.0),
                                        idx=1, mode='holding')
        assert '空進 </span>204.2~210.5' in html, (
            f'空進應顯示區間，實際：{html[html.find("空進"):html.find("空進")+80]}'
        )

    def test_short_entry_pill_fallback_single_when_no_entry(self):
        """舊資料（entry_low/high 缺）→ fallback 原單值 resistance。
        注意：entry 皆 None 會被 §三十七 F3 判 neutral，故只缺一邊測 fallback。"""
        a = self._short_analysis(entry_low=None)
        html = appmod._render_one_block(_stock(), a, _q(207.0),
                                        idx=1, mode='holding')
        assert '空進 </span>210.5' in html
        assert '~' not in html.split('空進 </span>')[1][:20]
