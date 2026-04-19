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

def _check_symbol(symbol):
    """快速判斷股票代號是否有效，最多等 5 秒"""
    import yfinance as yf
    try:
        hist = yf.Ticker(symbol).history(period='5d', timeout=5)
        return len(hist) > 0
    except:
        return False

def resolve_symbol(raw):
    """
    自動補上 .TW 或 .TWO 後綴。
    策略：同時發出兩個請求，哪個先有資料就用哪個。
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 已有後綴，直接回傳
    if raw.upper().endswith('.TW') or raw.upper().endswith('.TWO'):
        return raw

    candidates = [raw + '.TW', raw + '.TWO']

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(_check_symbol, s): s for s in candidates}
        for f in as_completed(futures):
            symbol = futures[f]
            if f.result():
                return symbol

    # 都沒資料，預設 .TW
    return raw + '.TW'

def add_stock(symbol, name='', cost=None, shares=None, buy_date=None):
    from modules.stock_names import enrich_name

    watchlist = load_watchlist()

    # 自動判斷上市/上櫃（同時查詢，速度快）
    symbol = resolve_symbol(symbol.strip())

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
