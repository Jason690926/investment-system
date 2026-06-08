"""
§三十七（2026-06-08）— 建議動作客觀化（與持有解耦）+ 2 渲染 bug

F1：建議 pill 不因持有而異（_decide_action call site 恆 watch）+ 移除標頭 deep-loss 疊加
F2（P1-1）：short 標頭「空標」改 P&F 下行目標（恆在價下），修「空標跑到現價上方」
F3（P2-1）：方向 badge 與 pill 同源（相位反推 long/short 但 entry 皆 None → neutral）

測試策略：F2/F3/F1-overlay 直接斷言 app._render_one_block 輸出 HTML（測行為非內部結構），
F1 決策走 _decide_action 純函式，F1 call-site 改動以 source guard 防回退。
"""
import sys, os, inspect, datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as appmod
from modules.ai_analyzer_v2 import _decide_action


# ── mock 建構（避免 DB 物件，沿用既有 pure-function 測試風格）────────────
def _q(close, prev=None):
    return SimpleNamespace(close=close,
                           prev_close=prev if prev is not None else close,
                           cache_date=datetime.date(2026, 6, 8))


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


# ── F1：建議動作客觀化 ────────────────────────────────────────────
class TestF1ObjectivePill:
    def test_decide_action_watch_long_in_zone(self):
        """持股改走 watch → long 在進場區得客觀字『進場區可佈』（非 HOLD 字典『加碼』）。"""
        sl = {'range_high': 105, 'range_low': 96.8,
              'entry_zone': [96.8, 100.9], 'invalidation': 96.8}
        pill = _decide_action(status='watch', direction='long',
                              structure_flag='結構未轉弱', swing_levels=sl,
                              breakout=False, price=99.0)
        assert pill == '🟢 進場區可佈'

    def test_decide_action_watch_short_below_zone(self):
        """晶心科風格：short 結構已轉弱、價在放空區下方 → 『等反彈佈空』（非 HOLD『出場』）。"""
        sl = {'range_high': 243, 'range_low': 224.5,
              'entry_zone': [233.75, 243], 'invalidation': 243}
        pill = _decide_action(status='watch', direction='short',
                              structure_flag='結構已轉弱', swing_levels=sl,
                              breakout=False, price=202.5)
        assert pill == '🟡 等反彈佈空'

    def test_call_sites_use_watch_not_hold(self):
        """兩個 analyze 函式呼叫 _decide_action 不得再依持有切 hold/watch 字典。"""
        src = inspect.getsource(sys.modules['modules.ai_analyzer_v2'])
        assert "status=('hold' if" not in src, \
            "call site 仍依持有切 hold/watch — 建議動作會因持有而異"

    def test_render_no_deep_loss_overlay(self):
        """標頭 deep-loss 疊加移除：持股深虧 -43% 不再把客觀 pill 覆寫成『觀望持有』。"""
        a = _analysis(action_pill='🟢 加碼', wyckoff_phase='再積累',
                      support_price=96.8, resistance_price=105,
                      entry_low=96.8, entry_high=100.9, target_price=None)
        # cost 355 / close 202.5 → ≈ -43%
        html = appmod._render_one_block(_stock(avg_cost=355.0), a,
                                        _q(202.5), idx=1, mode='holding')
        assert '建議 </span>🟢 加碼' in html, '標頭應保留 DB 既存客觀 pill'
        assert '觀望持有' not in html, 'deep-loss 疊加應已移除，不再覆寫標頭'


# ── F2（P1-1）：short 標頭空標 = P&F 下行目標 ──────────────────────
class TestF2ShortTarget:
    def _short_analysis(self, **kw):
        base = dict(wyckoff_phase='下跌', support_price=224.5,
                    resistance_price=243, stop_loss=250,
                    entry_low=233.75, entry_high=243,
                    action_pill='🟡 等反彈佈空')
        base.update(kw)
        return _analysis(**base)

    def test_short_target_uses_pnf_below_price(self):
        """晶心科風格：空標取 target_price=192（< 現價 202.5），非 range_low 224.5。"""
        a = self._short_analysis(target_price=192)
        html = appmod._render_one_block(_stock(), a, _q(202.5),
                                        idx=1, mode='holding')
        assert '空標 </span>192.0</span>' in html, '空標應顯示 P&F 下行目標 192'
        assert '224.5' not in html, 'range_low 224.5 不該再出現於 short 標頭'

    def test_short_target_none_hides_pill(self):
        """target_price 缺 → 不顯示空標 pill（誠實 > 錯誤）。"""
        a = self._short_analysis(target_price=None)
        html = appmod._render_one_block(_stock(), a, _q(202.5),
                                        idx=1, mode='holding')
        assert '空標' not in html

    def test_short_target_above_price_hidden(self):
        """guard：target_price ≥ 現價 → 不顯示（空標必在價下）。"""
        a = self._short_analysis(target_price=250)
        html = appmod._render_one_block(_stock(), a, _q(202.5),
                                        idx=1, mode='holding')
        assert '空標' not in html


# ── F3（P2-1）：方向 badge 與 pill 同源 ───────────────────────────
class TestF3DirectionBadge:
    def test_badge_neutral_when_entry_both_none(self):
        """采鈺風格：phase 再積累(→long) 但 entry_low/high 皆 None → badge『觀望』。"""
        a = _analysis(wyckoff_phase='再積累', support_price=462,
                      resistance_price=562, entry_low=None, entry_high=None,
                      risk_pct=62, action_pill='⚪ 觀望')
        html = appmod._render_one_block(_stock(status='watching'), a,
                                        _q(487.5), idx=1, mode='watching')
        assert '方向 </span>觀望' in html, 'entry 皆 None 時 badge 應為觀望'
        assert '方向 </span>多' not in html
        assert '箱底' not in html, 'neutral 應用 撐/壓 而非 箱底/箱頂'

    def test_badge_long_when_entry_present_not_regressed(self):
        """回歸：正常 long（entry 有值）→ badge『多』+ 箱底/箱頂 不退化。"""
        a = _analysis(wyckoff_phase='再積累', support_price=96.8,
                      resistance_price=105, entry_low=96.8, entry_high=100.9,
                      target_price=None, risk_pct=42, action_pill='🟢 進場區可佈')
        html = appmod._render_one_block(_stock(status='watching'), a,
                                        _q(99.0), idx=1, mode='watching')
        assert '方向 </span>多' in html
        assert '箱底' in html
