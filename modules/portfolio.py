import json
import os
from datetime import datetime
import config

PORTFOLIO_FILE = os.path.join(config.DATA_DIR, 'portfolio.json')

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not data:
                return _default_portfolio()
            return data
    return _default_portfolio()

def _default_portfolio():
    return {
        'cash': config.INITIAL_CAPITAL,
        'initial_capital': config.INITIAL_CAPITAL,
        'holdings': {},
        'trade_history': [],
        'created_at': datetime.now().strftime('%Y-%m-%d')
    }

def save_portfolio(portfolio):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

def buy_stock(portfolio, name, symbol, price, reason=''):
    cash = portfolio['cash']
    holdings = portfolio['holdings']

    if len(holdings) >= config.MAX_HOLDINGS:
        return portfolio, f'❌ 已達最大持倉數 {config.MAX_HOLDINGS} 檔'

    max_amount = config.INITIAL_CAPITAL * config.MAX_SINGLE_STOCK
    min_cash = config.INITIAL_CAPITAL * config.MIN_CASH_RATIO
    available = cash - min_cash

    if available <= 0:
        return portfolio, '❌ 現金不足，無法買進'

    invest_amount = min(max_amount, available)
    shares = int(invest_amount / price / 1000) * 1000
    if shares <= 0:
        return portfolio, '❌ 資金不足以購買最小單位'

    fee = round(price * shares * 0.001425, 0)
    total_cost = price * shares + fee

    if total_cost > available:
        return portfolio, '❌ 扣除手續費後資金不足'

    portfolio['cash'] -= total_cost
    portfolio['holdings'][name] = {
        'symbol': symbol,
        'shares': shares,
        'cost': price,
        'buy_date': datetime.now().strftime('%Y-%m-%d'),
        'fee': fee
    }

    portfolio['trade_history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'action': 'BUY',
        'name': name,
        'symbol': symbol,
        'price': price,
        'shares': shares,
        'amount': total_cost,
        'reason': reason
    })

    save_portfolio(portfolio)
    return portfolio, f'✅ 買進 {name} {shares}股 @{price} 金額:{int(total_cost):,}'

def sell_stock(portfolio, name, current_price, reason=''):
    holdings = portfolio['holdings']

    if name not in holdings:
        return portfolio, f'❌ 未持有 {name}'

    holding = holdings[name]
    shares = holding['shares']
    cost = holding['cost']

    fee = round(current_price * shares * 0.001425, 0)
    tax = round(current_price * shares * 0.003, 0)
    proceeds = current_price * shares - fee - tax

    pnl = proceeds - (cost * shares + holding['fee'])
    pnl_pct = round((pnl / (cost * shares)) * 100, 2)

    portfolio['cash'] += proceeds
    del portfolio['holdings'][name]

    portfolio['trade_history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'action': 'SELL',
        'name': name,
        'price': current_price,
        'shares': shares,
        'amount': proceeds,
        'pnl': round(pnl, 0),
        'pnl_pct': pnl_pct,
        'reason': reason
    })

    save_portfolio(portfolio)
    return portfolio, f'✅ 賣出 {name} {shares}股 @{current_price} 損益:{int(pnl):,}({pnl_pct}%)'

def get_portfolio_summary(portfolio, current_prices={}):
    holdings = portfolio['holdings']
    cash = portfolio['cash']
    initial = portfolio['initial_capital']

    total_market_value = 0
    holdings_detail = []

    for name, holding in holdings.items():
        curr_price = current_prices.get(name, holding['cost'])
        market_value = curr_price * holding['shares']
        cost_value = holding['cost'] * holding['shares']
        pnl = market_value - cost_value
        pnl_pct = round((pnl / cost_value) * 100, 2)
        total_market_value += market_value
        holdings_detail.append({
            'name': name,
            'shares': holding['shares'],
            'cost': holding['cost'],
            'current_price': curr_price,
            'market_value': round(market_value, 0),
            'pnl': round(pnl, 0),
            'pnl_pct': pnl_pct,
            'buy_date': holding['buy_date']
        })

    total_assets = cash + total_market_value
    total_pnl = total_assets - initial
    total_pnl_pct = round((total_pnl / initial) * 100, 2)

    return {
        'cash': round(cash, 0),
        'total_market_value': round(total_market_value, 0),
        'total_assets': round(total_assets, 0),
        'total_pnl': round(total_pnl, 0),
        'total_pnl_pct': total_pnl_pct,
        'holdings_detail': holdings_detail
    }