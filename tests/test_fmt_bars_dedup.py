"""
C 組（2026-05-20）— K 棒重複/缺漏防呆
用戶 2026-05-19 報表 5 支股日 K 表出現「2026-05-19 同日列兩次」+「(補充)/(最新)」標記，
根因是 AI 自行補行；本檔驗證 _fmt_bars 入口層防呆 dedup 已生效。
"""
import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _dedup_bars_by_date, _fmt_bars


def _bar(date_str, o=100, h=101, l=99, c=100, vol=1000):
    return {'date': date_str, 'open': o, 'high': h, 'low': l,
            'close': c, 'volume_zhang': vol}


class TestDedupBarsByDate:
    def test_no_dup_unchanged(self):
        bars = [_bar(f'2026-01-0{i}') for i in range(1, 5)]
        result = _dedup_bars_by_date(bars)
        assert len(result) == 4
        assert [b['date'] for b in result] == [b['date'] for b in bars]

    def test_same_date_keeps_last(self):
        """同 date 重複出現時保留最末（最新一筆覆寫舊）。"""
        b1 = _bar('2026-05-19', c=100)
        b2 = _bar('2026-05-19', c=200)
        result = _dedup_bars_by_date([b1, b2])
        assert len(result) == 1
        assert result[0]['close'] == 200  # 末筆優先

    def test_yongli_case_5_19_dup(self):
        """模擬用戶報表矽力 case：2026-05-19 連續列兩次（OHLC 相同）。"""
        bars = [
            _bar('2026-05-14', c=503),
            _bar('2026-05-15', c=468),
            _bar('2026-05-18', c=514),
            _bar('2026-05-19', c=482),
            _bar('2026-05-19', c=482),  # 重複行（OHLC 相同）
        ]
        result = _dedup_bars_by_date(bars)
        assert len(result) == 4
        dates = [b['date'] for b in result]
        assert dates.count('2026-05-19') == 1, '重複日應只保留一筆'

    def test_empty(self):
        assert _dedup_bars_by_date([]) == []

    def test_missing_date_field_skipped(self):
        """缺 date 欄位的 bar 被忽略（防呆）。"""
        bars = [_bar('2026-01-01'), {'open': 100}, _bar('2026-01-02')]
        result = _dedup_bars_by_date(bars)
        assert len(result) == 2  # 中間缺 date 的被剔除


class TestFmtBarsDeduplication:
    def test_fmt_bars_no_duplicate_output_row(self):
        """_fmt_bars 對重複日的 bars 輸出不應有兩個同日列。"""
        bars = [
            _bar('2026-05-14'), _bar('2026-05-15'),
            _bar('2026-05-18'), _bar('2026-05-19'),
            _bar('2026-05-19'),  # dup
        ]
        text = _fmt_bars(bars, "日K", 5)
        # 2026-05-19 在輸出 text 中只出現一次（為行起點 — date 在每行第一個 token）
        date_occurrence = text.count('2026-05-19')
        assert date_occurrence == 1, (
            f'去重後同日應只出現 1 次，實際 {date_occurrence} 次：\n{text}'
        )

    def test_fmt_bars_handles_less_than_n_bars(self):
        """資料少於 n 根時照實輸出（如技嘉 case 只有 3 根）。"""
        bars = [_bar('2026-05-15'), _bar('2026-05-18'), _bar('2026-05-19')]
        text = _fmt_bars(bars, "日K", 5)
        # 應該有 3 個日期行，不應有「補充」或「最新」字串
        assert '2026-05-15' in text
        assert '2026-05-18' in text
        assert '2026-05-19' in text
        # 表頭應反映實際根數（3 根，非寫死 5 根）
        assert '最近3根' in text, (
            f'表頭應顯示「最近3根」而非「最近5根」：\n{text[:100]}'
        )
