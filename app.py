import os
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from dotenv import load_dotenv
from modules.auth import init_auth
from modules.database import SessionLocal
from modules.stock_service import get_user_stocks, add_stock, add_trade, remove_stock

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

init_auth(app)


# ── 頁面路由 ──────────────────────────────────────────────

@app.route('/')
def index():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect('/dashboard')
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/stock/<int:stock_id>')
@login_required
def stock_detail(stock_id):
    db = SessionLocal()
    try:
        from modules.models import Stock
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return redirect('/dashboard')

        total = stock.total_zhang if stock.status == 'holding' and stock.trades else None
        avg   = float(stock.avg_cost) if stock.avg_cost else None

        class StockView:
            pass
        sv = StockView()
        sv.id          = stock.id
        sv.symbol      = stock.symbol
        sv.name        = stock.name
        sv.status      = stock.status
        sv.avg_cost    = avg
        sv.total_zhang = float(total) if total else None

        return render_template('stock.html', stock=sv)
    finally:
        db.close()


# ── 市場資料 API ──────────────────────────────────────────

@app.route('/api/market/<symbol>/data')
@login_required
def api_market_data(symbol):
    from modules.data_enricher import get_full_stock_data
    data = get_full_stock_data(symbol)
    if data is None:
        return jsonify({'error': f'無法取得 {symbol} 資料'}), 404
    return jsonify(data)


# ── AI 分析 API ───────────────────────────────────────────

@app.route('/api/stocks/<int:stock_id>/analyze', methods=['POST'])
@login_required
def api_analyze_stock(stock_id):
    db = SessionLocal()
    try:
        from modules.models import Stock
        from modules.data_enricher import get_full_stock_data
        from modules.ai_analyzer_v2 import analyze_stock_three_masters

        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        enriched = get_full_stock_data(stock.symbol)
        if enriched is None:
            return jsonify({'error': f'無法取得 {stock.symbol} 市場資料'}), 503

        avg   = float(stock.avg_cost)    if stock.avg_cost    else None
        total = float(stock.total_zhang) if stock.total_zhang else None

        result = analyze_stock_three_masters(
            name          = stock.name,
            symbol        = stock.symbol,
            enriched_data = enriched,
            status        = stock.status,
            avg_cost      = avg,
            total_zhang   = total,
            news_list     = [],
        )
        return jsonify({
            'html':          result['html'],
            'risk_pct':      result['risk_pct'],
            'support':       result['support'],
            'resistance':    result['resistance'],
            'target_pnf':    result['target_pnf'],
            'wyckoff_phase': result['wyckoff_phase'],
        })
    finally:
        db.close()


# ── 持股 CRUD API ─────────────────────────────────────────

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
