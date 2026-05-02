import os
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from dotenv import load_dotenv
from modules.auth import init_auth
from modules.database import SessionLocal
from modules.stock_service import get_user_stocks, add_stock, add_trade, remove_stock, update_trade, delete_trade

from werkzeug.middleware.proxy_fix import ProxyFix
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

init_auth(app)


# ── 偵錯（找完問題後移除）───────────────────────���────────
@app.route('/debug-oauth')
def debug_oauth():
    from modules.auth import oauth
    redirect_uri = url_for('auth.callback', _external=True)
    auth_url = oauth.google.create_authorization_url(redirect_uri)
    return f"""
    <p>Redirect URI Flask產生: <code>{redirect_uri}</code></p>
    <p>Client ID: <code>{os.getenv('GOOGLE_CLIENT_ID','')[:30]}...</code></p>
    <p>Secret末尾: <code>...{os.getenv('GOOGLE_CLIENT_SECRET','')[-6:]}</code></p>
    """

# ── 頁面路由 ───────────────────────────────────────��──────

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

@app.route('/api/market/<symbol>/info')
@login_required
def api_market_info(symbol):
    from modules.data_enricher import get_stock_info
    info = get_stock_info(symbol)
    if info is None:
        return jsonify({'error': f'找不到 {symbol}'}), 404
    return jsonify(info)


@app.route('/api/market/<symbol>/data')
@login_required
def api_market_data(symbol):
    from modules.data_enricher import get_full_stock_data
    print(f"[market/data] 查詢 {symbol}")
    data = get_full_stock_data(symbol)
    if data is None:
        print(f"[market/data] 失敗 {symbol}")
        return jsonify({'error': f'無法取得 {symbol} 資料，請確認代號格式（如 2330.TW）'}), 404
    return jsonify(data)


# ── AI 分析 API ───────────────────────────────────────────

@app.route('/api/stocks/<int:stock_id>/analysis')
@login_required
def api_get_analysis(stock_id):
    """讀取今日市場快取分析（若存在，不含個人建議）"""
    from datetime import date as dt_date
    from modules.models import Stock, StockAnalysis
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404
        today = dt_date.today()
        cached = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        if not cached or not cached.html_content:
            return jsonify({'cached': False})
        return jsonify({
            'cached':        True,
            'html':          cached.html_content,
            'risk_pct':      cached.risk_pct,
            'support':       float(cached.support_price)    if cached.support_price    else None,
            'resistance':    float(cached.resistance_price) if cached.resistance_price else None,
            'target_pnf':    float(cached.target_price)     if cached.target_price     else None,
            'wyckoff_phase': cached.wyckoff_phase,
            'generated_at':  cached.generated_at.strftime('%H:%M') if cached.generated_at else None,
        })
    finally:
        db.close()


@app.route('/api/stocks/<int:stock_id>/analyze', methods=['POST'])
@login_required
def api_analyze_stock(stock_id):
    """產生市場分析（第一段）並存入跨用戶快取"""
    from datetime import date as dt_date
    import datetime as _dt
    from modules.models import Stock, StockAnalysis
    from modules.data_enricher import get_full_stock_data
    from modules.ai_analyzer_v2 import analyze_market_only
    from decimal import Decimal

    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        today = dt_date.today()
        # 已有今日快取直接回傳，不重複呼叫 AI
        existing = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        if existing and existing.html_content:
            return jsonify({
                'html':          existing.html_content,
                'risk_pct':      existing.risk_pct,
                'support':       float(existing.support_price)    if existing.support_price    else None,
                'resistance':    float(existing.resistance_price) if existing.resistance_price else None,
                'target_pnf':    float(existing.target_price)     if existing.target_price     else None,
                'wyckoff_phase': existing.wyckoff_phase,
                'from_cache':    True,
            })

        enriched = get_full_stock_data(stock.symbol)
        if enriched is None:
            return jsonify({'error': f'無法取得 {stock.symbol} 市場資料'}), 503

        result = analyze_market_only(
            name=stock.name, symbol=stock.symbol,
            enriched_data=enriched, news_list=[],
        )

        if existing:
            existing.html_content     = result['html']
            existing.risk_pct         = result['risk_pct']
            existing.support_price    = Decimal(str(result['support']))    if result['support']    else None
            existing.resistance_price = Decimal(str(result['resistance'])) if result['resistance'] else None
            existing.target_price     = Decimal(str(result['target_pnf'])) if result['target_pnf'] else None
            existing.wyckoff_phase    = result['wyckoff_phase']
            existing.generated_at     = _dt.datetime.utcnow()
        else:
            db.add(StockAnalysis(
                symbol=stock.symbol, analysis_date=today, analysis_type='daily',
                html_content=result['html'], risk_pct=result['risk_pct'],
                support_price=Decimal(str(result['support']))    if result['support']    else None,
                resistance_price=Decimal(str(result['resistance'])) if result['resistance'] else None,
                target_price=Decimal(str(result['target_pnf'])) if result['target_pnf'] else None,
                wyckoff_phase=result['wyckoff_phase'],
            ))
        db.commit()

        return jsonify({
            'html':          result['html'],
            'risk_pct':      result['risk_pct'],
            'support':       result['support'],
            'resistance':    result['resistance'],
            'target_pnf':    result['target_pnf'],
            'wyckoff_phase': result['wyckoff_phase'],
            'from_cache':    False,
        })
    finally:
        db.close()


@app.route('/api/stocks/<int:stock_id>/recommend', methods=['POST'])
@login_required
def api_recommend_stock(stock_id):
    """產生個人化操作建議（第二段），使用市場快取資料，不另外存入 DB"""
    from datetime import date as dt_date
    from modules.models import Stock, StockAnalysis
    from modules.data_enricher import get_stock_info
    from modules.ai_analyzer_v2 import generate_personal_recommendation

    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        today = dt_date.today()
        cached = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        if not cached or not cached.html_content:
            return jsonify({'error': '尚無市場分析，請先產生分析'}), 404

        info = get_stock_info(stock.symbol)
        current_price = info['price'] if info else 0

        avg   = float(stock.avg_cost)    if stock.avg_cost    else None
        total = float(stock.total_zhang) if stock.total_zhang else None

        html = generate_personal_recommendation(
            name=stock.name, symbol=stock.symbol,
            current_price=current_price,
            wyckoff_phase=cached.wyckoff_phase or '未知',
            risk_pct=cached.risk_pct or 50,
            support=float(cached.support_price)    if cached.support_price    else None,
            resistance=float(cached.resistance_price) if cached.resistance_price else None,
            target_pnf=float(cached.target_price)  if cached.target_price    else None,
            status=stock.status,
            avg_cost=avg,
            total_zhang=total,
        )
        return jsonify({'html': html})
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


@app.route('/api/stocks/<int:stock_id>/trades')
@login_required
def api_get_trades(stock_id):
    db = SessionLocal()
    try:
        from modules.models import Stock
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404
        return jsonify({
            'trades':      [{'id': t.id, 'buy_price': float(t.buy_price),
                             'quantity_zhang': float(t.quantity_zhang),
                             'buy_date': t.buy_date.isoformat() if t.buy_date else None}
                            for t in stock.trades],
            'total_zhang': float(stock.total_zhang) if stock.total_zhang else 0,
            'avg_cost':    float(stock.avg_cost) if stock.avg_cost else None,
        })
    finally:
        db.close()


@app.route('/api/trades/<int:trade_id>', methods=['PUT'])
@login_required
def api_update_trade(trade_id):
    data = request.json
    db = SessionLocal()
    try:
        trade = update_trade(db, current_user.id, trade_id,
                             quantity_zhang=data['quantity_zhang'],
                             buy_price=data.get('buy_price'),
                             buy_date=data.get('buy_date'))
        return jsonify({'ok': True, 'trade_id': trade.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/trades/<int:trade_id>', methods=['DELETE'])
@login_required
def api_delete_trade(trade_id):
    db = SessionLocal()
    try:
        delete_trade(db, current_user.id, trade_id)
        return jsonify({'ok': True})
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
