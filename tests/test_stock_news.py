"""
§四十二（2026-07-17）— 個股當日新聞佐證量價異動

Task 1：_filter_stock_news 純過濾邏輯 + get_stock_news_rss fail-open
Task 2：_stock_news_block prompt 注入塊（見同檔下方 class）
spec: docs/superpowers/specs/2026-07-17-stock-news-corroboration-design.md
"""
import sys, os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.data_fetcher import _filter_stock_news, get_stock_news_rss

UTC = timezone.utc
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(hours=24)


def _item(title, hours_ago=1.0, source='工商時報', pub_dt='auto'):
    if pub_dt == 'auto':
        pub_dt = NOW - timedelta(hours=hours_ago)
    return {'title': title, 'source': source, 'pub_dt': pub_dt}


class TestFilterStockNews:
    def test_title_must_contain_name(self):
        """標題不含股名 → 剔除（搜尋引擎模糊匹配不可信）。"""
        items = [_item('晶心科接單暢旺'), _item('台股大盤震盪整理')]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1
        assert out[0]['title'] == '晶心科接單暢旺'

    def test_24h_cutoff_boundary(self):
        """23.5h 保留 / 24.5h 剔除。"""
        items = [_item('晶心科 A', hours_ago=23.5), _item('晶心科 B', hours_ago=24.5)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert [o['title'] for o in out] == ['晶心科 A']

    def test_pub_dt_none_kept_with_empty_label(self):
        """pubDate 解析失敗（pub_dt=None）→ 保留、pub_label=''（沿用寬容邏輯）。"""
        items = [_item('晶心科 C', pub_dt=None)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1
        assert out[0]['pub_label'] == ''

    def test_naive_pub_dt_no_crash(self):
        """naive datetime（無 tzinfo）與 aware cutoff 比較會 TypeError → 須保留不 crash。"""
        items = [_item('晶心科 D', pub_dt=datetime(2026, 7, 17, 10, 0, 0))]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert len(out) == 1

    def test_n_limit_5(self):
        """超過 n 則 → 只取前 5。"""
        items = [_item(f'晶心科 {i}') for i in range(8)]
        out = _filter_stock_news(items, '晶心科', CUTOFF, n=5)
        assert len(out) == 5

    def test_pub_label_is_tw_time(self):
        """pub_label = 台灣時間 MM/DD HH:MM（UTC 12:00 → TW 20:00）。"""
        items = [_item('晶心科 E', pub_dt=NOW)]
        out = _filter_stock_news(items, '晶心科', CUTOFF)
        assert out[0]['pub_label'] == '07/17 20:00'

    def test_output_shape(self):
        """回傳 keys = title/source/pub_label（無 pub_dt 內部欄位外洩）。"""
        out = _filter_stock_news([_item('晶心科 F')], '晶心科', CUTOFF)
        assert set(out[0].keys()) == {'title', 'source', 'pub_label'}


class TestGetStockNewsFailOpen:
    def test_network_failure_returns_empty(self, monkeypatch):
        """urllib 失敗 → 回 []（誠實降級，不 raise 不 retry）。"""
        import urllib.request

        def _boom(*a, **kw):
            raise OSError('simulated network failure')

        monkeypatch.setattr(urllib.request, 'urlopen', _boom)
        assert get_stock_news_rss('晶心科', '6533') == []


# ── Task 2：_stock_news_block prompt 注入塊 ──────────────────────
from modules.ai_analyzer_v2 import _stock_news_block


class TestStockNewsBlock:
    def test_empty_list_gives_no_news_ban(self):
        """無新聞 → 主動訊號化：暫無字樣 + 禁止臆測消息面禁令。"""
        block = _stock_news_block([])
        assert '暫無相關新聞（近 24h）' in block
        assert '禁止臆測消息面' in block
        assert '市場傳聞' in block, '禁令應列舉禁用字眼'
        assert '資金面' in block, '應給唯一合法歸因寫法'

    def test_none_input_same_as_empty(self):
        """None 輸入（legacy caller 未傳）→ 同無新聞分支，不 crash。"""
        assert _stock_news_block(None) == _stock_news_block([])

    def test_news_lines_with_label_and_source(self):
        """有新聞 → 每則一行 '- MM/DD HH:MM 標題（來源）'。"""
        block = _stock_news_block([
            {'title': '晶心科接單暢旺', 'source': '工商時報',
             'pub_label': '07/16 18:30'},
        ])
        assert '- 07/16 18:30 晶心科接單暢旺（工商時報）' in block

    def test_three_iron_rules_present(self):
        """有新聞 → 三條鐵律齊全（推翻禁令 / 矛盾程式為準 / 禁引數字）。"""
        block = _stock_news_block([{'title': '晶心科 A', 'source': '',
                                    'pub_label': ''}])
        assert '禁止作為推翻結構旗標' in block
        assert '以程式數據為準' in block
        assert '新聞面與量價數據不一致' in block
        assert '禁止引用新聞中的價位' in block

    def test_max_5_items(self):
        """超過 5 則只列前 5。"""
        news = [{'title': f'晶心科 {i}', 'source': '', 'pub_label': ''}
                for i in range(7)]
        block = _stock_news_block(news)
        assert block.count('- ') == 5

    def test_legacy_format_without_pub_label(self):
        """legacy 格式（無 pub_label/source key，parallel 路徑舊資料）→ 不 crash、無多餘空白。"""
        block = _stock_news_block([{'title': '晶心科 B'}])
        assert '- 晶心科 B' in block
        assert '- 晶心科 B（' not in block, 'source 缺時不應有空括號'
