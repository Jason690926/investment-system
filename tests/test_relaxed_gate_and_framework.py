"""
§四十三 R3/R4/R5（2026-07-17）

R3：relaxed pending 但現價已過 gate（微星「需先突破 144」現價 145）→ 收穩措辭
R4：§5 目標「—」但 relaxed 有值（大聯大 124/微星 159/采鈺 433）→ 同源 gate 句
R5：§5 空值殘句（合晶「進場區：— 元（觸發須量 ≥196,074 張）」）→ 砍後綴
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.ai_analyzer_v2 import (
    _relaxed_sentence_from_info,
    _relaxed_target_note,
    _render_operation_framework,
)


# ── R3：§4 relaxed 句過期 gate 檢查 ──────────────────────────────
class TestR3RelaxedGateSentence:
    def test_long_pending_price_past_gate(self):
        """微星：pending、現價 145 ≥ gate 144 → 「已站上…收穩確認」非「需先突破」。"""
        s = _relaxed_sentence_from_info('long', (159, 144, 'pending'), 145.0)
        assert '已站上 144' in s
        assert '收穩' in s
        assert '需先突破' not in s

    def test_long_pending_price_below_gate_unchanged(self):
        """回歸：現價 130 < gate 144 → 維持既有「需先突破 144 元觸發」句。"""
        s = _relaxed_sentence_from_info('long', (159, 144, 'pending'), 130.0)
        assert 'P&F理論目標：159元 — 需先突破 144 元觸發（等幅量度）' == s

    def test_short_pending_price_past_gate(self):
        """short 鏡像：現價 118 ≤ gate 120 → 「已跌破…收穩確認」。"""
        s = _relaxed_sentence_from_info('short', (100, 120, 'pending'), 118.0)
        assert '已跌破 120' in s
        assert '需先跌破' not in s

    def test_reached_sentence_unchanged(self):
        """回歸：reached 句逐字不變（§三十五 Bug-D 既有行為）。"""
        s = _relaxed_sentence_from_info('long', (52.2, 46.4, 'reached'), 133.0)
        assert s == ('P&F概念目標：先前等幅量度 52.2 元已達成（突破點 46.4 元），'
                     '等新箱形成才能估算下一目標')


# ── R4：§5 目標 note（與 §4 同源） ───────────────────────────────
class TestR4TargetNote:
    def test_pending_note(self):
        note = _relaxed_target_note('long', (159, 144, 'pending'), 130.0)
        assert note == '需先突破 144 元後估 159 元'

    def test_pending_past_gate_note(self):
        note = _relaxed_target_note('long', (159, 144, 'pending'), 145.0)
        assert note == '已站上 144 元，收穩確認後估 159 元'

    def test_reached_returns_none(self):
        """reached → None（§5 維持「—」，§4 已寫等新箱）。"""
        assert _relaxed_target_note('long', (52.2, 46.4, 'reached'), 133.0) is None

    def test_no_info_returns_none(self):
        assert _relaxed_target_note('long', None, 130.0) is None

    def test_framework_long_target_uses_note(self):
        """§5 long 目標列：tg=None + note → 顯示 gate 句非「— 元」。"""
        sl = {'range_high': 144, 'range_low': 120,
              'entry_zone': (120, 132), 'invalidation': 120, 'target': None}
        html = _render_operation_framework(
            action_pill='🟡 等回測', direction='long', swing_levels=sl,
            breakout=False, price=130.0,
            target_note='需先突破 144 元後估 159 元')
        assert '目標：需先突破 144 元後估 159 元（等幅量度）' in html
        assert '目標：— 元' not in html

    def test_framework_short_target_uses_note(self):
        sl = {'range_high': 120, 'range_low': 100,
              'entry_zone': (110, 120), 'invalidation': 120, 'target': None}
        html = _render_operation_framework(
            action_pill='🟡 等反彈佈空', direction='short', swing_levels=sl,
            breakout=False, price=115.0,
            target_note='需先跌破 100 元後估 80 元')
        assert '空標：需先跌破 100 元後估 80 元' in html

    def test_framework_no_note_keeps_dash(self):
        """回歸：無 note → 維持「— 元」。"""
        sl = {'range_high': 144, 'range_low': 120,
              'entry_zone': (120, 132), 'invalidation': 120, 'target': None}
        html = _render_operation_framework(
            action_pill='🟡 等回測', direction='long', swing_levels=sl,
            breakout=False, price=130.0)
        assert '目標：— 元' in html

    def test_call_sites_wire_target_note(self):
        """兩 call site 都須算 note 傳入 framework（source guard）。"""
        import inspect
        src = inspect.getsource(sys.modules['modules.ai_analyzer_v2'])
        assert src.count('_relaxed_target_note(') >= 3, \
            'def + 兩 call site 應至少 3 處出現'


# ── R5：空值殘句 ────────────────────────────────────────────────
class TestR5EmptyValueRows:
    def test_long_none_entry_no_vol_suffix(self):
        """合晶：進場區 None + 有量能門檻 → 不得出現「— 元（觸發須量…）」。"""
        sl = {'range_high': None, 'range_low': None,
              'entry_zone': None, 'invalidation': None, 'target': None}
        html = _render_operation_framework(
            action_pill='⚪ 觀望', direction='long', swing_levels=sl,
            breakout=False, vol_threshold_zhang=196074, price=180.0)
        assert '觸發須量' not in html
        assert '進場區：—（無有效箱體' in html

    def test_long_none_inv_no_invalid_suffix(self):
        """停損 None → 不得出現「— 元 — 跌破即論點作廢」。"""
        sl = {'range_high': None, 'range_low': None,
              'entry_zone': None, 'invalidation': None, 'target': None}
        html = _render_operation_framework(
            action_pill='⚪ 觀望', direction='long', swing_levels=sl,
            breakout=False, price=180.0)
        assert '— 元 — 跌破即論點作廢' not in html
        assert '停損：—（無有效箱體）' in html

    def test_long_values_present_unchanged(self):
        """回歸：值齊全時列格式不變。"""
        sl = {'range_high': 105, 'range_low': 96.8,
              'entry_zone': (96.8, 100.9), 'invalidation': 96.8, 'target': 120.0}
        html = _render_operation_framework(
            action_pill='🟢 進場區可佈', direction='long', swing_levels=sl,
            breakout=False, vol_threshold_zhang=1500, price=99.0)
        assert '進場區：96.80 ~ 100.90 元（觸發須量 ≥ 1,500 張）' in html
        assert '停損：96.80 元 — 跌破即論點作廢' in html
        assert '目標：120.00 元' in html

    def test_short_none_entry_no_suffix(self):
        """short 鏡像：空進 None → 「空進：—（無有效箱體）」無佈空後綴。"""
        sl = {'range_high': None, 'range_low': None,
              'entry_zone': None, 'invalidation': None, 'target': None}
        html = _render_operation_framework(
            action_pill='⚪ 觀望', direction='short', swing_levels=sl,
            breakout=False, price=180.0)
        assert '空進：—（無有效箱體）' in html
        assert '— 元（回測壓力佈空）' not in html
        assert '空停：—（無有效箱體）' in html
