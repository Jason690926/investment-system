from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from modules.models import Stock, Trade, User, StockAnalysis


def _analysis_day_tw():
    """最近有效的分析日（14:30 後才算今日；週末往回找最近工作日）"""
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    wd = now_tw.weekday()
    after_close = now_tw.hour > 14 or (now_tw.hour == 14 and now_tw.minute >= 30)
    if wd < 5 and after_close:
        return now_tw.date()
    day = now_tw.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def get_user_stocks(db: Session, user_id: int) -> list:
    # 自訂 display_order 在前（小到大），未設定者（NULL）排在最後並按 created_at
    stocks = (db.query(Stock)
              .filter_by(user_id=user_id)
              .order_by(case((Stock.display_order.is_(None), 1), else_=0),
                        Stock.display_order,
                        Stock.created_at)
              .all())

    # 只取「當前分析日」的快取；14:30 前算昨日，14:30 後算今日
    analysis_day = _analysis_day_tw()
    symbols = [s.symbol for s in stocks]
    analyses = {}
    if symbols:
        rows = (
            db.query(StockAnalysis)
            .filter(StockAnalysis.symbol.in_(symbols),
                    StockAnalysis.analysis_type == 'daily',
                    StockAnalysis.analysis_date == analysis_day,
                    StockAnalysis.html_content.isnot(None))
            .all()
        )
        analyses = {r.symbol: r for r in rows}

    result = []
    for s in stocks:
        item = {
            'id': s.id,
            'symbol': s.symbol,
            'name': s.name,
            'status': s.status,
        }
        analysis = analyses.get(s.symbol)
        if analysis:
            item['risk_pct']      = analysis.risk_pct
            item['wyckoff_phase'] = analysis.wyckoff_phase
            item['action_pill']   = analysis.action_pill  # plan §三十一
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

    # server-side 對照：本地表為單一事實來源，避免前端帶入英文名（yfinance fallback）
    from modules.stock_names import STOCK_NAMES
    base = symbol.replace('.TWO', '').replace('.TW', '')
    if base in STOCK_NAMES:
        name = STOCK_NAMES[base]

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


def reorder_stocks(db: Session, user_id: int, ordered_ids: list[int]) -> int:
    """依傳入 id 順序刷新 display_order = 0, 1, 2, ...
    僅更新該 user 擁有的 stock；非自家 id 直接忽略。回傳實際更新筆數。"""
    own_ids = {sid for (sid,) in db.query(Stock.id).filter_by(user_id=user_id).all()}
    updated = 0
    for idx, sid in enumerate(ordered_ids):
        if sid in own_ids:
            db.query(Stock).filter_by(id=sid, user_id=user_id).update(
                {Stock.display_order: idx}, synchronize_session=False
            )
            updated += 1
    db.commit()
    return updated


def remove_stock(db: Session, user_id: int, stock_id: int):
    stock = db.query(Stock).filter_by(id=stock_id, user_id=user_id).first()
    if not stock:
        raise ValueError("持股不存在")
    db.delete(stock)
    db.commit()


def update_trade(db: Session, user_id: int, trade_id: int,
                 quantity_zhang: float, buy_price: float = None,
                 buy_date: str = None) -> Trade:
    trade = (db.query(Trade).join(Stock)
               .filter(Trade.id == trade_id, Stock.user_id == user_id).first())
    if not trade:
        raise ValueError("交易記錄不存在")
    trade.quantity_zhang = Decimal(str(quantity_zhang))
    if buy_price is not None:
        trade.buy_price = Decimal(str(buy_price))
    if buy_date is not None:
        trade.buy_date = date.fromisoformat(buy_date)
    elif buy_date == '':
        trade.buy_date = None
    db.commit()
    db.refresh(trade)
    return trade


def delete_trade(db: Session, user_id: int, trade_id: int):
    trade = (db.query(Trade).join(Stock)
               .filter(Trade.id == trade_id, Stock.user_id == user_id).first())
    if not trade:
        raise ValueError("交易記錄不存在")
    db.delete(trade)
    db.commit()
