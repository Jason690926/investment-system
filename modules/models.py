from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    Numeric, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from modules.database import Base


class User(Base):
    __tablename__ = 'users'

    id           = Column(Integer, primary_key=True)
    google_id    = Column(String(128), unique=True, nullable=False)
    email        = Column(String(256), unique=True, nullable=False)
    name         = Column(String(128), nullable=False)
    role         = Column(String(16), default='user')   # 'admin' or 'user'
    max_stocks   = Column(Integer, default=10)
    email_notify = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    stocks = relationship('Stock', back_populates='user', cascade='all, delete-orphan')


class Stock(Base):
    __tablename__ = 'stocks'

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey('users.id'), nullable=False)
    symbol     = Column(String(32), nullable=False)   # e.g. '2330.TW'
    name       = Column(String(64), nullable=False)   # e.g. '台積電'
    status     = Column(String(16), default='watching')  # 'holding' or 'watching'
    display_order = Column(Integer, nullable=True)  # 自訂排序；NULL=未設定，撈單以 COALESCE 排在最後
    created_at = Column(DateTime, default=datetime.utcnow)

    user   = relationship('User', back_populates='stocks')
    trades = relationship('Trade', back_populates='stock', cascade='all, delete-orphan')

    @property
    def total_zhang(self) -> Decimal:
        return sum((t.quantity_zhang for t in self.trades), Decimal('0'))

    @property
    def avg_cost(self):
        if not self.trades:
            return None
        total = self.total_zhang
        if total == 0:
            return None
        weighted = sum(t.buy_price * t.quantity_zhang for t in self.trades)
        return round(weighted / total, 2)

    def zhang_display(self, zhang_value) -> str:
        """顯示張數，整數省略小數點"""
        if zhang_value is None:
            return '-'
        v = Decimal(str(zhang_value))
        return f"{int(v)}張" if v == v.to_integral_value() else f"{v}張"


class Trade(Base):
    __tablename__ = 'trades'

    id              = Column(Integer, primary_key=True)
    stock_id        = Column(Integer, ForeignKey('stocks.id'), nullable=False)
    buy_price       = Column(Numeric(10, 2), nullable=False)
    quantity_zhang  = Column(Numeric(10, 1), nullable=False)  # 單位：張
    buy_date        = Column(Date, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    stock = relationship('Stock', back_populates='trades')


class MarketDataCache(Base):
    """當日市場 OHLCV 快取，跨用戶共用，避免重複呼叫 Yahoo Finance"""
    __tablename__ = 'market_data_cache'

    id         = Column(Integer, primary_key=True)
    symbol     = Column(String(32), nullable=False)
    cache_date = Column(Date, nullable=False)
    data_json  = Column(Text, nullable=False)
    cached_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'cache_date', name='uq_market_cache'),
    )


class QuoteCache(Base):
    """看板輕量行情快取（OHLC + 前日收）。
    跟 MarketDataCache 分開以避免「quote 寫入半成品 → 分析路徑誤用」。
    每日 1 筆/股票，寫滿即固化（盤中自動更新由前端 retry/refresh 控制）。"""
    __tablename__ = 'quote_cache'

    id         = Column(Integer, primary_key=True)
    symbol     = Column(String(32), nullable=False)
    cache_date = Column(Date, nullable=False)
    open       = Column(Numeric(10, 2))
    high       = Column(Numeric(10, 2))
    low        = Column(Numeric(10, 2))
    close      = Column(Numeric(10, 2))
    prev_close = Column(Numeric(10, 2))
    cached_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'cache_date', name='uq_quote_cache'),
    )


class StockAnalysis(Base):
    """每支股票的 AI 分析快取，跨用戶共用客觀市場面"""
    __tablename__ = 'stock_analyses'

    id              = Column(Integer, primary_key=True)
    symbol          = Column(String(32), nullable=False)
    analysis_date   = Column(Date, nullable=False)
    analysis_type   = Column(String(16), nullable=False)  # 'daily' or 'weekly_full'
    market_analysis = Column(Text)       # AI 產出的客觀市場分析（JSON string）
    html_content    = Column(Text)       # 三宗師完整 HTML 分析內容
    wyckoff_phase   = Column(String(32)) # 威科夫階段快取
    risk_pct        = Column(Integer)    # 風險係數 0-100
    support_price   = Column(Numeric(10, 2))
    resistance_price= Column(Numeric(10, 2))
    target_price    = Column(Numeric(10, 2))  # P&F 概念目標價
    generated_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'analysis_date', 'analysis_type',
                         name='uq_stock_analysis'),
    )


class EmailContact(Base):
    """每個用戶的 email 通訊錄（分享 PDF 報表用）"""
    __tablename__ = 'email_contacts'

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey('users.id'), nullable=False)
    email        = Column(String(256), nullable=False)
    name         = Column(String(64), nullable=True)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    created_at   = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'email', name='uq_user_email_contact'),
    )


class WeeklyReport(Base):
    """產業週報，每週一份，跨用戶共用"""
    __tablename__ = 'weekly_reports'

    id            = Column(Integer, primary_key=True)
    week_start    = Column(Date, nullable=False)
    week_end      = Column(Date, nullable=False)
    html_market   = Column(Text)   # 大盤週報 HTML
    html_industry = Column(Text)   # 產業指標股 HTML
    generated_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('week_start', name='uq_weekly_report'),
    )


class DailyMarketSummary(Base):
    """每日財經新聞摘要 + 明日方向，平日印表報表用"""
    __tablename__ = 'daily_market_summary'

    id           = Column(Integer, primary_key=True)
    summary_date = Column(Date, nullable=False, unique=True)
    html_content = Column(Text)   # 今日重大財經新聞 + 明日需關注方向 HTML
    generated_at = Column(DateTime, default=datetime.utcnow)


class PatternHistory(Base):
    """K線型態歷史紀錄，含事後漲跌回填"""
    __tablename__ = 'pattern_history'

    id            = Column(Integer, primary_key=True)
    symbol        = Column(String(32), nullable=False)
    detected_date = Column(Date, nullable=False)
    pattern_name  = Column(String(64), nullable=False)
    direction     = Column(String(16))   # 'bullish', 'bearish', 'neutral'
    candle_count  = Column(Integer)      # 型態涉及K棒數
    close_price   = Column(Numeric(10, 2))
    return_3d     = Column(Numeric(6, 2))   # 3交易日後漲跌%，事後回填
    return_5d     = Column(Numeric(6, 2))
    return_10d    = Column(Numeric(6, 2))
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'detected_date', 'pattern_name',
                         name='uq_pattern_history'),
    )
