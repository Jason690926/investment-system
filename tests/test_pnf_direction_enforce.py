"""
§四十五（2026-07-17）— P&F 句方向錯配 post-process 強制矯正

7/17 報告實證：_dual_pnf 注入多方句/空方句由 AI 依 DIRECTION 挑，AI 挑錯：
- 撼訊 DIRECTION=short 引用多方失效句「論點已失效（跌穿支撐 121 元）」
- 晶心科 DIRECTION=neutral 引用 long relaxed 句（應為「—（無方向，待結構確認）」）
修法：post-process 以最終 direction（含 safety net 覆寫後）deterministic
重算正確句（_pnf_sentences 與 _dual_pnf 同源）並替換 html 中的 P&F 句。
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.ai_analyzer_v2 import (
    _enforce_pnf_direction,
    _pnf_sentences,
    _dual_pnf,
)

LONG_S  = 'P&F概念目標：論點已失效（跌穿支撐 121 元），論點重建前 P&F 不適用'
SHORT_S = 'P&F概念目標：先前等幅量度 41.9 元已達成（跌破點 36.2 元），等新箱形成才能估算下一目標'
NEUTRAL_S = 'P&F概念目標：—（無方向，待結構確認）'


class TestEnforcePnfDirection:
    def test_short_direction_replaces_long_sentence(self):
        """撼訊案例：direction=short 但 html 引多方失效句 → 換成空方句。"""
        html = f'<p>衝突點：...</p>\n<p>{LONG_S}</p>\n<p>▶ 波段結構偏空</p>'
        out, replaced = _enforce_pnf_direction(html, 'short', LONG_S, SHORT_S)
        assert replaced is True
        assert SHORT_S in out
        assert '跌穿支撐 121' not in out

    def test_neutral_direction_replaces_directional_sentence(self):
        """晶心科案例：direction=neutral 但 html 引 long relaxed 句 → 換 neutral 句。"""
        html = '<p>P&F理論目標：176元 — 已跌破 213 元，需收穩確認觸發（等幅量度）</p>'
        out, replaced = _enforce_pnf_direction(html, 'neutral', LONG_S, SHORT_S)
        assert replaced is True
        assert NEUTRAL_S in out
        assert '176' not in out

    def test_correct_sentence_untouched(self):
        """已正確引用 → 不動、replaced=False。"""
        html = f'<p>{SHORT_S}</p>'
        out, replaced = _enforce_pnf_direction(html, 'short', LONG_S, SHORT_S)
        assert replaced is False
        assert out == html

    def test_no_pnf_sentence_untouched(self):
        """html 無 P&F 句（AI 漏寫）→ 原樣，不亂插。"""
        html = '<p>三宗師融合結論</p>'
        out, replaced = _enforce_pnf_direction(html, 'long', LONG_S, SHORT_S)
        assert replaced is False
        assert out == html

    def test_multiple_occurrences_all_replaced(self):
        """AI 重複引兩次錯句 → 全部替換。"""
        html = f'<p>{LONG_S}</p><p>P&F理論目標：176元 — 需先突破 213 元觸發（等幅量度）</p>'
        out, _ = _enforce_pnf_direction(html, 'short', LONG_S, SHORT_S)
        assert out.count(SHORT_S) == 2
        assert '121' not in out and '176' not in out

    def test_spaced_prefix_matched(self):
        """AI 寫「P&F 概念目標：」帶空白 → 也要抓到。"""
        html = '<p>P&F 概念目標：120元（等幅量度）</p>'
        out, replaced = _enforce_pnf_direction(html, 'short', LONG_S, SHORT_S)
        assert replaced is True
        assert SHORT_S in out

    def test_section5_short_target_row_not_touched(self):
        """§5「空標：X 元（P&F 下行目標）」非 P&F 目標句前綴 → 不得誤替換。"""
        html = f'<p>{SHORT_S}</p><div class="op-row">空標：75.60 元（P&amp;F 下行目標）</div>'
        out, _ = _enforce_pnf_direction(html, 'short', LONG_S, SHORT_S)
        assert '空標：75.60 元（P&amp;F 下行目標）' in out


class TestPnfSentencesSameSource:
    def _bars(self):
        """簡單下跌序列（有效 swing）。"""
        out = []
        from datetime import date, timedelta
        d = date(2026, 1, 1)
        seq = [(100, 95), (105, 98), (110, 104), (115, 108), (113, 109),
               (110, 105), (108, 102), (106, 100), (104, 98), (102, 95),
               (100, 92), (98, 90), (102, 95), (105, 98), (108, 100),
               (110, 104), (112, 106), (115, 108), (113, 109), (110, 105),
               (108, 102), (105, 99), (102, 96)]
        for h, l in seq:
            out.append({'date': d.isoformat(), 'open': (h + l) / 2, 'high': h,
                        'low': l, 'close': (h + l) / 2, 'volume_zhang': 1000})
            d += timedelta(days=1)
        return out

    def test_sentences_match_dual_pnf_block(self):
        """_pnf_sentences 的兩句必須逐字出現在 _dual_pnf block（同源保證）。"""
        enriched = {'daily_bars': self._bars(), 'weekly_bars': []}
        pl, ps, ls, ss = _pnf_sentences(enriched, 101.0)
        _, _, block = _dual_pnf(enriched, 101.0)
        assert ls in block
        assert ss in block

    def test_call_sites_wire_enforcement(self):
        """兩 call site 都須呼叫 _enforce_pnf_direction（source guard）。"""
        import inspect
        src = inspect.getsource(sys.modules['modules.ai_analyzer_v2'])
        assert src.count('_enforce_pnf_direction(') >= 3, 'def + 兩 call site'
