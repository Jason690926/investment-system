"""一次性執行：把 data/watchlist.json 的舊資料匯入 PostgreSQL"""
import json
from decimal import Decimal
from modules.database import SessionLocal
from modules.models import User, Stock, Trade

ADMIN_EMAIL = 'frodo19800926@gmail.com'

with open('data/watchlist.json', encoding='utf-8-sig') as f:
    old_data = json.load(f)

db = SessionLocal()
try:
    admin = db.query(User).filter_by(email=ADMIN_EMAIL).first()
    if not admin:
        print("找不到管理者帳號，請先登入一次再執行此腳本")
        exit(1)

    for item in old_data:
        existing = db.query(Stock).filter_by(
            user_id=admin.id, symbol=item['symbol']
        ).first()
        if existing:
            print(f"跳過（已存在）: {item['symbol']}")
            continue

        stock = Stock(
            user_id=admin.id,
            symbol=item['symbol'],
            name=item['name'],
            status='holding',
        )
        db.add(stock)
        db.flush()

        shares = item.get('shares', 0)
        zhang = Decimal(str(shares)) / 1000

        if shares > 0 and item.get('cost'):
            trade = Trade(
                stock_id=stock.id,
                buy_price=Decimal(str(item['cost'])),
                quantity_zhang=zhang,
                buy_date=None,
            )
            db.add(trade)

        print(f"匯入: {item['name']} {item['symbol']} {zhang}張 @ {item['cost']}")

    db.commit()
    print("✅ 遷移完成")
finally:
    db.close()
