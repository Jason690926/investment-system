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
