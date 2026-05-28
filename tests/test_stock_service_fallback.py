"""stock_service.get_user_stocks 14-day fallback 測試（plan §三十三, spec 2026-05-28）。

覆蓋：
- 主查詢命中（is_today_analysis=True）
- Fallback 命中（is_today_analysis=False, last_analysis_date 正確）
- 14 天邊界（14 天前命中、15 天前不命中）
- 多 symbol 混合（part 今日 / part fallback / part 無）
- 同 symbol 多筆 fallback → 取最近一筆
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.database import Base
from modules.models import User, Stock, StockAnalysis
from modules.stock_service import get_user_stocks


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    user = User(id=1, google_id='g_test', email='test@test.com',
                name='Test', role='user', max_stocks=20)
    s.add(user)
    s.commit()
    yield s
    s.close()


def _add_stock(db, user_id, symbol, name='測試股'):
    stock = Stock(user_id=user_id, symbol=symbol, name=name, status='watching')
    db.add(stock)
    db.commit()
    return stock


def _add_analysis(db, symbol, analysis_date, **kwargs):
    defaults = {
        'analysis_type': 'daily',
        'html_content': '<p>test</p>',
        'risk_pct': 50,
        'wyckoff_phase': '上漲',
        'action_pill': '🟢 進場區可佈',
        'support_price': 100,
        'resistance_price': 110,
        'target_price': 130,
        'entry_low': 100,
        'entry_high': 105,
    }
    defaults.update(kwargs)
    a = StockAnalysis(symbol=symbol, analysis_date=analysis_date, **defaults)
    db.add(a)
    db.commit()
    return a


# ---------- 主查詢命中 ----------
def test_today_analysis_hits_primary_query(db, monkeypatch):
    """主查詢命中 → is_today_analysis=True、fallback 不執行。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, '2330.TW')
    _add_analysis(db, '2330.TW', today, risk_pct=30)

    result = get_user_stocks(db, user_id=1)
    assert len(result) == 1
    assert result[0]['symbol'] == '2330.TW'
    assert result[0]['risk_pct'] == 30
    assert result[0]['is_today_analysis'] is True
    assert result[0]['last_analysis_date'] == '2026-05-27'


# ---------- Fallback 命中 ----------
def test_fallback_hits_when_today_missing(db, monkeypatch):
    """今日無分析 + 2 天前有 → fallback 命中、is_today_analysis=False。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, '2330.TW')
    _add_analysis(db, '2330.TW', date(2026, 5, 25), risk_pct=40)

    result = get_user_stocks(db, user_id=1)
    assert result[0]['is_today_analysis'] is False
    assert result[0]['risk_pct'] == 40
    assert result[0]['last_analysis_date'] == '2026-05-25'


# ---------- 14 天邊界 ----------
def test_fallback_14day_boundary(db, monkeypatch):
    """14 天前命中、15 天前不命中（>= cutoff 嚴格邊界）。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'A.TW')
    _add_stock(db, 1, 'B.TW')
    _add_analysis(db, 'A.TW', today - timedelta(days=14), risk_pct=14)
    _add_analysis(db, 'B.TW', today - timedelta(days=15), risk_pct=15)

    result = {item['symbol']: item for item in get_user_stocks(db, user_id=1)}
    # A: 14 天前命中
    assert result['A.TW'].get('risk_pct') == 14
    assert result['A.TW']['is_today_analysis'] is False
    # B: 15 天前不命中（無 risk_pct key、無 is_today_analysis key）
    assert 'risk_pct' not in result['B.TW']
    assert 'is_today_analysis' not in result['B.TW']


# ---------- 同 symbol 多筆 fallback → 取最近 ----------
def test_fallback_takes_most_recent(db, monkeypatch):
    """同 symbol 有多筆 fallback 候選 → 取最近一筆。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'X.TW')
    _add_analysis(db, 'X.TW', date(2026, 5, 20), risk_pct=20)
    _add_analysis(db, 'X.TW', date(2026, 5, 26), risk_pct=26)  # 最近
    _add_analysis(db, 'X.TW', date(2026, 5, 23), risk_pct=23)

    result = get_user_stocks(db, user_id=1)
    assert result[0]['risk_pct'] == 26
    assert result[0]['last_analysis_date'] == '2026-05-26'


# ---------- 多 symbol 混合 ----------
def test_mixed_today_and_fallback_and_none(db, monkeypatch):
    """3 支股：今日命中 / fallback 命中 / 都沒。"""
    today = date(2026, 5, 27)
    monkeypatch.setattr('modules.stock_service._analysis_day_tw', lambda: today)
    _add_stock(db, 1, 'T.TW')   # 今日命中
    _add_stock(db, 1, 'F.TW')   # fallback 命中
    _add_stock(db, 1, 'N.TW')   # 無
    _add_analysis(db, 'T.TW', today, risk_pct=11)
    _add_analysis(db, 'F.TW', date(2026, 5, 24), risk_pct=22)

    result = {item['symbol']: item for item in get_user_stocks(db, user_id=1)}
    assert result['T.TW']['is_today_analysis'] is True
    assert result['T.TW']['risk_pct'] == 11
    assert result['F.TW']['is_today_analysis'] is False
    assert result['F.TW']['risk_pct'] == 22
    assert 'risk_pct' not in result['N.TW']
    assert 'is_today_analysis' not in result['N.TW']
