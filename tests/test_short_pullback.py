"""
§四十三 R1（2026-07-17）— short 強跌反彈誠實揭露（§三十八 long 鏡像）

7/16 實證：矽力/瑞軒/瑞耘/華星光 空進區距現價 25~30%，「🟡 等反彈佈空」
不可操作。gate：空進區下緣距現價 >25%（過遠）或 區間過寬 >25%（復用
_strong_pullback_state）→ 🟡 強跌反彈觀望 + 誠實 §5。
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.ai_analyzer_v2 import _decide_action, _render_operation_framework


class TestR1DecideAction:
    def test_far_zone_gives_pullback_watch(self):
        """空進區下緣 130 距現價 100 = 30% → 強跌反彈觀望（矽力型）。"""
        sl = {'range_high': 140, 'range_low': 90,
              'entry_zone': [130, 140], 'invalidation': 140}
        pill = _decide_action(status='watch', direction='short',
                              structure_flag='結構已轉弱', swing_levels=sl,
                              breakout=False, price=100.0)
        assert pill == '🟡 強跌反彈觀望'

    def test_wide_zone_gives_pullback_watch(self):
        """區間過寬：zone (102, 130) 寬 28% of 現價 100 → 強跌反彈觀望。"""
        sl = {'range_high': 130, 'range_low': 80,
              'entry_zone': [102, 130], 'invalidation': 130}
        pill = _decide_action(status='watch', direction='short',
                              structure_flag='結構已轉弱', swing_levels=sl,
                              breakout=False, price=100.0)
        assert pill == '🟡 強跌反彈觀望'

    def test_normal_below_zone_unchanged(self):
        """回歸：區近且窄（下緣 105 距現價 5%、寬 7%）→ 維持 等反彈佈空。"""
        sl = {'range_high': 112, 'range_low': 95,
              'entry_zone': [105, 112], 'invalidation': 112}
        pill = _decide_action(status='watch', direction='short',
                              structure_flag='結構已轉弱', swing_levels=sl,
                              breakout=False, price=100.0)
        assert pill == '🟡 等反彈佈空'

    def test_invalidated_still_wins(self):
        """優先序回歸：價過空停 → 🔴 論點作廢（不被新 gate 搶走）。"""
        sl = {'range_high': 140, 'range_low': 90,
              'entry_zone': [130, 140], 'invalidation': 140}
        pill = _decide_action(status='watch', direction='short',
                              structure_flag='結構已轉弱', swing_levels=sl,
                              breakout=False, price=150.0)
        assert pill == '🔴 論點作廢'


class TestR1HonestFramework:
    _sl = {'range_high': 645, 'range_low': 500,
           'entry_zone': (599.5, 645), 'invalidation': 645, 'target': 400.0}

    def test_pullback_watch_cuts_entry_and_target(self):
        """pill=強跌反彈觀望 → §5 砍空進區/空標，留失效價 + 等新結構。"""
        html = _render_operation_framework(
            action_pill='🟡 強跌反彈觀望', direction='short',
            swing_levels=self._sl, breakout=False, price=473.0)
        assert '空進：' not in html
        assert '空標：' not in html
        assert '645.00' in html, '應保留客觀失效價'
        assert '過遠' in html or '過寬' in html
        assert '新' in html and '結構' in html

    def test_normal_short_frame_not_regressed(self):
        """回歸：一般 short pill → 完整空方框架。"""
        html = _render_operation_framework(
            action_pill='🟡 等反彈佈空', direction='short',
            swing_levels=self._sl, breakout=False, price=610.0)
        assert '空進：599.50 ~ 645.00 元' in html
        assert '空停：645.00 元' in html
