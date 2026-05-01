from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from modules.models import Stock, Trade, User


def get_user_stocks(db: Session, user_id: int) -> list:
    stocks = db.query(Stock).filter_by(user_id=user_id).order_by(Stock.created_at).all()
    result = []
    for s in stocks:
        item = {
            'id': s.id,
            'symbol': s.symbol,
            'name': s.name,
            'status': s.status,
        }
        if s.status == 'holding' and s.trades:
            total = s.total_zhang
            item['total_zhang'] = float(total)
            item['total_zhang_display'] = s.zhang_display(total)
            item['avg_cost'] = float(s.avg_cost) if s.avg_cost else None
            item['trades'] = [
                {
                    'id': t.id,
                    'buy_price': float(t.buy_price),
                    'quantity_zhang': float(t.quantity_zhang),
                    'buy_date': t.buy_date.isoformat() if t.buy_date else None,
                }
                for t in s.trades
            ]
        result.append(item)
    return result


def add_stock(db: Session, user_id: int, symbol: str, name: str,
              status: str = 'watching',
              buy_price: float = None, quantity_zhang: float = None,
              buy_date: str = None) -> Stock:

    user = db.get(User, user_id)
    current_count = db.query(Stock).filter_by(user_id=user_id).count()
    if user.role != 'admin' and current_count >= user.max_stocks:
        raise ValueError(f"已達持股上限（{user.max_stocks}支）")

    existing = db.query(Stock).filter_by(user_id=user_id, symbol=symbol).first()
    if existing:
        raise ValueError(f"{symbol} 已在清單中")

    stock = Stock(user_id=user_id, symbol=symbol, name=name, status=status)
    db.add(stock)
    db.flush()

    if status == 'holding' and buy_price and quantity_zhang:
        parsed_date = date.fromisoformat(buy_date) if buy_date else None
        trade = Trade(
            stock_id=stock.id,
            buy_price=Decimal(str(buy_price)),
            quantity_zhang=Decimal(str(quantity_zhang)),
            buy_date=parsed_date,
        )
        db.add(trade)

    db.commit()
    db.refresh(stock)
    return stock


def add_trade(db: Session, user_id: int, stock_id: int,
              buy_price: float, quantity_zhang: float,
              buy_date: str = None) -> Trade:

    stock = db.query(Stock).filter_by(id=stock_id, user_id=user_id).first()
    if not stock:
        raise ValueError("持股不存在")
    if stock.status == 'watching':
        stock.status = 'holding'

    parsed_date = date.fromisoformat(buy_date) if buy_date else None
    trade = Trade(
        stock_id=stock_id,
        buy_price=Decimal(str(buy_price)),
        quantity_zhang=Decimal(str(quantity_zhang)),
        buy_date=parsed_date,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def remove_stock(db: Session, user_id: int, stock_id: int):
    stock = db.query(Stock).filter_by(id=stock_id, user_id=user_id).first()
    if not stock:
        raise ValueError("持股不存在")
    db.delete(stock)
    db.commit()
