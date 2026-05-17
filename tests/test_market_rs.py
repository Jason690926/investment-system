"""Bug D — 個股 vs 大盤(TWII)同期相對強度（2026-05-17）

驗證 _twii_close_on_or_before 對齊邏輯 + _market_rs_block 計算/正負號/
TWII 缺漏 fallback（誠實不注入）。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import modules.data_fetcher as df
from modules.ai_analyzer_v2 import _twii_close_on_or_before, _market_rs_block


def _bars(closes, start='2026-05-01'):
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    out = []
    for i, c in enumerate(closes):
        d = d0 + timedelta(days=i)
        out.append({'date': str(d), 'open': c, 'high': c, 'low': c, 'close': c})
    return out


class TestTwiiCloseOnOrBefore:

    def test_exact_hit(self):
        twii = {'2026-05-01': 100.0, '2026-05-02': 101.0}
        assert _twii_close_on_or_before(twii, '2026-05-02') == 101.0

    def test_nearest_earlier_when_missing(self):
        twii = {'2026-05-01': 100.0, '2026-05-03': 103.0}
        # 05-02 缺 → 取最近較早的 05-01
        assert _twii_close_on_or_before(twii, '2026-05-02') == 100.0

    def test_before_all_returns_none(self):
        twii = {'2026-05-05': 100.0}
        assert _twii_close_on_or_before(twii, '2026-05-01') is None

    def test_empty_returns_none(self):
        assert _twii_close_on_or_before({}, '2026-05-01') is None


class TestMarketRsBlock:

    def _patch_twii(self, monkeypatch, mapping):
        monkeypatch.setattr(df, 'get_index_daily_closes',
                            lambda *a, **k: dict(mapping))

    def test_outperform_block(self, monkeypatch):
        # 22 根，close=100+i → idx21=121, idx16=116, idx1=101
        bars = _bars([100 + i for i in range(22)])
        d = {b['date']: None for b in bars}
        twii = {
            bars[1]['date']:  1000.0,   # 20日窗口起點
            bars[16]['date']: 1010.0,   # 5日窗口起點
            bars[21]['date']: 1005.0,   # 現在
        }
        self._patch_twii(monkeypatch, twii)
        block = _market_rs_block(bars)
        assert '【大盤對比（程式計算，禁止更改）】' in block
        assert '大盤對比鐵律' in block and 'beta 連動非 alpha' in block
        # 個股5日 (121/116-1)=+4.3% ; TWII5日 (1005/1010-1)=-0.5% ; rs=+4.8 跑贏
        assert '個股5日 +4.3%' in block
        assert 'TWII5日 -0.5%' in block
        assert '+4.8pp（跑贏大盤）' in block
        # 20日：個股 (121/101-1)=+19.8% ; TWII (1005/1000-1)=+0.5% ; rs=+19.3 跑贏
        assert '個股20日 +19.8%' in block
        assert '+19.3pp（跑贏大盤）' in block

    def test_resilient_when_stock_down_less_than_market(self, monkeypatch):
        # 個股小跌、大盤大跌 → 抗跌
        closes = [100] * 21 + [98]          # 22 根，最後一根 -2%（5日窗 idx16=100）
        bars = _bars(closes)
        twii = {bars[16]['date']: 1000.0, bars[1]['date']: 1000.0,
                bars[21]['date']: 950.0}    # 大盤 -5%
        self._patch_twii(monkeypatch, twii)
        block = _market_rs_block(bars)
        # rs5 = -2.0 - (-5.0) = +3.0 → 抗跌（stock_chg<0）
        assert '抗跌' in block
        assert '落後大盤' not in block

    def test_underperform(self, monkeypatch):
        closes = [100] * 21 + [99]          # 個股 -1%
        bars = _bars(closes)
        twii = {bars[16]['date']: 1000.0, bars[1]['date']: 1000.0,
                bars[21]['date']: 1030.0}   # 大盤 +3%
        self._patch_twii(monkeypatch, twii)
        block = _market_rs_block(bars)
        assert '落後大盤' in block

    def test_twii_unavailable_no_injection(self, monkeypatch):
        bars = _bars([100 + i for i in range(22)])
        self._patch_twii(monkeypatch, {})       # TWII 取得失敗
        assert _market_rs_block(bars) == ''

    def test_insufficient_bars_no_injection(self, monkeypatch):
        self._patch_twii(monkeypatch, {'2026-05-01': 1000.0})
        assert _market_rs_block(_bars([100, 101, 102])) == ''

    def test_nearest_earlier_alignment(self, monkeypatch):
        # TWII 缺現在當天 → 用最近較早交易日，仍能算出區塊
        bars = _bars([100 + i for i in range(22)])
        twii = {
            bars[1]['date']:  1000.0,
            bars[16]['date']: 1010.0,
            bars[20]['date']: 1004.0,   # 缺 bars[21] 當天，有前一交易日
        }
        self._patch_twii(monkeypatch, twii)
        block = _market_rs_block(bars)
        assert '個股5日' in block and 'pp（' in block
