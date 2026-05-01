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


class StockAnalysis(Base):
    """每支股票的 AI 分析快取，跨用戶共用客觀市場面"""
    __tablename__ = 'stock_analyses'

    id              = Column(Integer, primary_key=True)
    symbol          = Column(String(32), nullable=False)
    analysis_date   = Column(Date, nullable=False)
    analysis_type   = Column(String(16), nullable=False)  # 'daily' or 'weekly_full'
    market_analysis = Column(Text)       # AI 產出的客觀市場分析（JSON string）
    wyckoff_phase   = Column(String(32)) # 威科夫階段快取：accumulation/markup/distribution/markdown
    risk_pct        = Column(Integer)    # 風險係數 0-100
    support_price   = Column(Numeric(10, 2))
    resistance_price= Column(Numeric(10, 2))
    target_price    = Column(Numeric(10, 2))  # P&F 概念目標價
    generated_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'analysis_date', 'analysis_type',
                         name='uq_stock_analysis'),
    )
