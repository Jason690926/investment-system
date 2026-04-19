import json
import os
from datetime import datetime

WATCHLIST_FILE = 'data/watchlist.json'

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            return data if data else []
    return []

def save_watchlist(watchlist):
    os.makedirs('data', exist_ok=True)
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

def add_stock(symbol, name='', cost=None, shares=None, buy_date=None):
    from modules.stock_names import enrich_name
    import yfinance as yf
    watchlist = load_watchlist()
    # 自動判斷上市/上櫃
    if not symbol.endswith('.TW') and not symbol.endswith('.TWO'):
        hist_tw = yf.Ticker(symbol + '.TW').history(period='5d')
        if len(hist_tw) > 0:
            symbol = symbol + '.TW'
        else:
            hist_two = yf.Ticker(symbol + '.TWO').history(period='5d')
            symbol = symbol + '.TWO' if len(hist_two) > 0 else symbol + '.TW'
    # 檢查是否已存在
    for s in watchlist:
        if s['symbol'] == symbol:
            return False, f'{symbol} 已在追蹤清單中'
    # 自動取得中文名稱
    final_name = enrich_name(symbol, name)
    entry = {
        'symbol': symbol,
        'name': final_name,
        'added_date': datetime.now().strftime('%Y-%m-%d'),
        'cost': float(cost) if cost else None,
        'shares': int(shares) if shares else None,
        'buy_date': buy_date if buy_date else None
    }
    watchlist.append(entry)
    save_watchlist(watchlist)
    return True, f'已新增 {final_name}（{symbol}）到追蹤清單'

def remove_stock(symbol):
    watchlist = load_watchlist()
    new_list = [s for s in watchlist if s['symbol'] != symbol]
    if len(new_list) == len(watchlist):
        return False, f'{symbol} 不在追蹤清單中'
    save_watchlist(new_list)
    return True, f'已移除 {symbol}'

def get_watchlist():
    return load_watchlist()