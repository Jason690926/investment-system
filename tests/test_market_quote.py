"""market_quote 讀取路徑單元測試。

驗證 Phase 2 設計：14:30 後優先用 MarketDataCache（收盤權威），
盤前/盤中寫入的 QuoteCache 不可信，記憶體快取也要在 post-close 失效。
"""
import json
from datetime import datetime, date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import _resolve_quote, _post_close_tw, _today_close_threshold_utc, _quote_cache
from modules.models import QuoteCache, MarketDataCache


@pytest.fixture(autouse=True)
def _clear_quote_mem_cache():
    _quote_cache.clear()
    yield
    _quote_cache.clear()


def _build_daily_bars(close_today=458):
    """產生 22 根 daily_bars，最後一根 close=指定值"""
    bars = [
        {'date': f'2026-04-{i:02d}', 'open': 400, 'high': 410, 'low': 395, 'close': 405}
        for i in range(10, 30)
    ]
    bars.append({'date': '2026-05-12', 'open': 450, 'high': 455, 'low': 440, 'close': 452})
    bars.append({'date': '2026-05-13', 'open': 455, 'high': 460, 'low': 445, 'close': close_today})
    return bars


def _mock_db(qc=None, mkt=None):
    """模擬 SQLAlchemy session：query(QuoteCache) / query(MarketDataCache) 各回不同 value。"""
    db = MagicMock()

    def _make_q(value):
        q = MagicMock()
        q.filter_by.return_value.first.return_value = value
        q.filter_by.return_value.order_by.return_value.first.return_value = value
        return q

    qc_q = _make_q(qc)
    mkt_q = _make_q(mkt)

    def _query_side_effect(model):
        if model is QuoteCache:
            return qc_q
        if model is MarketDataCache:
            return mkt_q
        return _make_q(None)

    db.query.side_effect = _query_side_effect
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    db.add = MagicMock()
    return db


# ─────────────── helper 函式行為 ───────────────

def test_post_close_tw_true_at_1500_tpe():
    assert _post_close_tw(now_utc=datetime(2026, 5, 13, 7, 0)) is True


def test_post_close_tw_true_at_exactly_1430_tpe():
    assert _post_close_tw(now_utc=datetime(2026, 5, 13, 6, 30)) is True


def test_post_close_tw_false_at_1429_tpe():
    assert _post_close_tw(now_utc=datetime(2026, 5, 13, 6, 29)) is False


def test_today_close_threshold_utc_is_today_0630():
    th = _today_close_threshold_utc(now_utc=datetime(2026, 5, 13, 7, 0))
    assert th == datetime(2026, 5, 13, 6, 30, 0)


# ─────────────── resolve_quote: B 核心（post-close 優先 MarketDataCache）───────────────

def test_post_close_prefers_market_data_cache_over_quote_cache():
    """14:30 後且 MarketDataCache 有今日資料：應拿 daily_bars[-1].close=458，而非 QuoteCache.close=420（盤中寫的）"""
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 7, 0)
    qc = SimpleNamespace(
        close=Decimal('420'), open=Decimal('418'),
        high=Decimal('425'), low=Decimal('415'),
        prev_close=Decimal('412'),
        cached_at=datetime(2026, 5, 13, 5, 0),  # 13:00 TPE pre-close
    )
    mkt = SimpleNamespace(
        data_json=json.dumps({'daily_bars': _build_daily_bars(close_today=458)}),
        cache_date=today,
    )
    db = _mock_db(qc=qc, mkt=mkt)

    result = _resolve_quote(db, '2330.TW', today, now_utc, get_yahoo_quote=lambda s: None)

    assert result is not None
    assert result['close'] == 458
    assert result['open'] == 455
    assert len(result['spark_bars']) == 20


def test_post_close_upserts_quote_cache_after_market_data_hit():
    """C 內建：拿 MarketDataCache 後同時把 QuoteCache.close 覆寫成收盤"""
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 7, 0)
    qc = SimpleNamespace(
        close=Decimal('420'), open=Decimal('418'),
        high=Decimal('425'), low=Decimal('415'),
        prev_close=Decimal('412'),
        cached_at=datetime(2026, 5, 13, 5, 0),
    )
    mkt = SimpleNamespace(
        data_json=json.dumps({'daily_bars': _build_daily_bars(close_today=458)}),
        cache_date=today,
    )
    db = _mock_db(qc=qc, mkt=mkt)

    _resolve_quote(db, '2330.TW', today, now_utc)

    assert float(qc.close) == 458, "QuoteCache.close 應被覆寫為 daily_bars[-1].close=458"
    assert float(qc.open) == 455
    assert qc.cached_at >= datetime(2026, 5, 13, 6, 30, 0), "cached_at 應更新為 post-close 時間"


# ─────────────── resolve_quote: stale 偵測 ───────────────

def test_post_close_stale_quote_cache_bypassed_falls_to_yahoo():
    """14:30 後、無 MarketDataCache、QuoteCache.cached_at < 今日 14:30 → 視為 stale → Yahoo"""
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 7, 0)
    qc = SimpleNamespace(
        close=Decimal('420'), open=Decimal('418'),
        high=Decimal('425'), low=Decimal('415'),
        prev_close=Decimal('412'),
        cached_at=datetime(2026, 5, 13, 5, 0),  # 13:00 TPE pre-close
    )
    db = _mock_db(qc=qc, mkt=None)
    yahoo_payload = {
        'symbol': '2330.TW', 'open': 455, 'high': 460,
        'low': 445, 'close': 458, 'prev_close': 452,
    }

    result = _resolve_quote(db, '2330.TW', today, now_utc,
                            get_yahoo_quote=lambda s: yahoo_payload)

    assert result['close'] == 458


def test_post_close_fresh_quote_cache_trusted_no_yahoo_call():
    """14:30 後、無 MarketDataCache、QuoteCache.cached_at >= 今日 14:30 → 信任，不打 Yahoo"""
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 7, 0)
    qc = SimpleNamespace(
        close=Decimal('458'), open=Decimal('455'),
        high=Decimal('460'), low=Decimal('445'),
        prev_close=Decimal('452'),
        cached_at=datetime(2026, 5, 13, 6, 35),  # 14:35 TPE post-close
    )
    db = _mock_db(qc=qc, mkt=None)
    yahoo_called = []

    def _mock_yahoo(s):
        yahoo_called.append(s)
        return {'symbol': s, 'close': 999}

    result = _resolve_quote(db, '2330.TW', today, now_utc, get_yahoo_quote=_mock_yahoo)

    assert result['close'] == 458
    assert yahoo_called == [], "fresh QuoteCache 信任時不應呼叫 Yahoo"


# ─────────────── resolve_quote: pre-close 不退化 ───────────────

def test_pre_close_unchanged_behavior_trusts_quote_cache():
    """14:30 前：QuoteCache 命中即返回，不檢查 staleness"""
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 3, 0)  # 11:00 TPE pre-close
    qc = SimpleNamespace(
        close=Decimal('420'), open=Decimal('418'),
        high=Decimal('425'), low=Decimal('415'),
        prev_close=Decimal('412'),
        cached_at=datetime(2026, 5, 13, 2, 0),
    )
    db = _mock_db(qc=qc, mkt=None)

    result = _resolve_quote(db, '2330.TW', today, now_utc, get_yahoo_quote=lambda s: None)

    assert result['close'] == 420


# ─────────────── resolve_quote: 記憶體快取 stale ───────────────

def test_memory_cache_pre_close_then_post_close_invalidates():
    """同 process：pre-close 寫入 mem，跨到 post-close 應 invalidate 並用 MarketDataCache"""
    today = date(2026, 5, 13)
    # Step 1: pre-close
    qc_pre = SimpleNamespace(
        close=Decimal('420'), open=Decimal('418'),
        high=Decimal('425'), low=Decimal('415'),
        prev_close=Decimal('412'),
        cached_at=datetime(2026, 5, 13, 2, 0),
    )
    r1 = _resolve_quote(_mock_db(qc=qc_pre, mkt=None),
                        '2330.TW', today,
                        now_utc=datetime(2026, 5, 13, 3, 0))
    assert r1['close'] == 420
    assert _quote_cache.get(f'2330.TW_{today}') is not None

    # Step 2: post-close + MarketDataCache 有 daily_bars
    mkt = SimpleNamespace(
        data_json=json.dumps({'daily_bars': _build_daily_bars(close_today=458)}),
        cache_date=today,
    )
    r2 = _resolve_quote(_mock_db(qc=qc_pre, mkt=mkt),
                        '2330.TW', today,
                        now_utc=datetime(2026, 5, 13, 7, 0))
    assert r2['close'] == 458, "post-close 應 invalidate mem 並使用 MarketDataCache"


# ─────────────── resolve_quote: 邊界 ───────────────

def test_yahoo_failure_returns_none():
    today = date(2026, 5, 13)
    now_utc = datetime(2026, 5, 13, 7, 0)
    db = _mock_db(qc=None, mkt=None)

    result = _resolve_quote(db, '9999.TW', today, now_utc, get_yahoo_quote=lambda s: None)

    assert result is None
