import os
from flask import Flask, jsonify, request
from flask_login import login_required, current_user
from dotenv import load_dotenv
from modules.auth import init_auth
from modules.database import SessionLocal
from modules.stock_service import get_user_stocks, add_stock, add_trade, remove_stock

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

init_auth(app)


@app.route('/')
@login_required
def index():
    return jsonify({
        'user': current_user.name,
        'email': current_user.email,
        'role': current_user.role,
    })


# ── 持股 API ──────────────────────────────────────────

@app.route('/api/stocks')
@login_required
def api_get_stocks():
    db = SessionLocal()
    try:
        return jsonify(get_user_stocks(db, current_user.id))
    finally:
        db.close()


@app.route('/api/stocks/add', methods=['POST'])
@login_required
def api_add_stock():
    data = request.json
    db = SessionLocal()
    try:
        stock = add_stock(
            db, current_user.id,
            symbol=data['symbol'],
            name=data['name'],
            status=data.get('status', 'watching'),
            buy_price=data.get('buy_price'),
            quantity_zhang=data.get('quantity_zhang'),
            buy_date=data.get('buy_date'),
        )
        return jsonify({'ok': True, 'id': stock.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/stocks/trade', methods=['POST'])
@login_required
def api_add_trade():
    data = request.json
    db = SessionLocal()
    try:
        trade = add_trade(
            db, current_user.id,
            stock_id=data['stock_id'],
            buy_price=data['buy_price'],
            quantity_zhang=data['quantity_zhang'],
            buy_date=data.get('buy_date'),
        )
        return jsonify({'ok': True, 'trade_id': trade.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/stocks/remove', methods=['POST'])
@login_required
def api_remove_stock():
    data = request.json
    db = SessionLocal()
    try:
        remove_stock(db, current_user.id, data['stock_id'])
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
