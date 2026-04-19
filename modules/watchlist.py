import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Google Sheets 設定 ────────────────────────────────────
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')

def _get_sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS', '')
    if not creds_json:
        return None
    try:
        creds_dict = json.loads(creds_json)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f'Google Sheets 連線失敗: {e}')
        return None

def _get_worksheet():
    client = _get_sheets_client()
    if not client:
        return None
    try:
        spreadsheet = client.open_by_key(SHEET_ID)
        try:
            ws = spreadsheet.worksheet('watchlist')
        except:
            ws = spreadsheet.add_worksheet(title='watchlist', rows=1000, cols=10)
            ws.append_row(['symbol', 'name', 'added_date', 'cost', 'shares', 'buy_date', 'notes', 'updated_at'])
        return ws
    except Exception as e:
        print(f'取得工作表失敗: {e}')
        return None

# ── 本地備份（Google Sheets 失敗時的後備）────────────────
LOCAL_FILE = 'data/watchlist.json'

def _load_local():
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            return data if data else []
    return []

def _save_local(watchlist):
    os.makedirs('data', exist_ok=True)
    with open(LOCAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

# ── 讀取 ──────────────────────────────────────────────────
def load_watchlist():
    ws = _get_worksheet()
    if not ws:
        return _load_local()
    try:
        rows = ws.get_all_records()
        result = []
        for row in rows:
            if not row.get('symbol'):
                continue
            result.append({
                'symbol': row.get('symbol', ''),
                'name': row.get('name', ''),
                'added_date': row.get('added_date', ''),
                'cost': float(row['cost']) if row.get('cost') else None,
                'shares': int(row['shares']) if row.get('shares') else None,
                'buy_date': row.get('buy_date') or None,
            })
        return result
    except Exception as e:
        print(f'從 Google Sheets 讀取失敗，改用本地: {e}')
        return _load_local()

# ── 寫入 ──────────────────────────────────────────────────
def save_watchlist(watchlist):
    _save_local(watchlist)
    ws = _get_worksheet()
    if not ws:
        return
    try:
        ws.clear()
        ws.append_row(['symbol', 'name', 'added_date', 'cost', 'shares', 'buy_date', 'notes', 'updated_at'])
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        for item in watchlist:
            ws.append_row([
                item.get('symbol', ''),
                item.get('name', ''),
                item.get('added_date', ''),
                item.get('cost', '') or '',
                item.get('shares', '') or '',
                item.get('buy_date', '') or '',
                '',
                now
            ])
    except Exception as e:
        print(f'寫入 Google Sheets 失敗: {e}')

# ── 判斷上市/上櫃 ─────────────────────────────────────────
def _check_symbol(symbol):
    import yfinance as yf
    try:
        hist = yf.Ticker(symbol).history(period='5d', timeout=5)
        return len(hist) > 0
    except:
        return False

def resolve_symbol(raw):
    if raw.upper().endswith('.TW') or raw.upper().endswith('.TWO'):
        return raw
    candidates = [raw + '.TW', raw + '.TWO']
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(_check_symbol, s): s for s in candidates}
        for f in as_completed(futures):
            symbol = futures[f]
            if f.result():
                return symbol
    return raw + '.TW'

# ── 新增 ──────────────────────────────────────────────────
def add_stock(symbol, name='', cost=None, shares=None, buy_date=None):
    from modules.stock_names import enrich_name
    watchlist = load_watchlist()
    symbol = resolve_symbol(symbol.strip())
    for s in watchlist:
        if s['symbol'] == symbol:
            return False, f'{symbol} 已在追蹤清單中'
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

# ── 刪除 ──────────────────────────────────────────────────
def remove_stock(symbol):
    watchlist = load_watchlist()
    new_list = [s for s in watchlist if s['symbol'] != symbol]
    if len(new_list) == len(watchlist):
        return False, f'{symbol} 不在追蹤清單中'
    save_watchlist(new_list)
    return True, f'已移除 {symbol}'

def get_watchlist():
    return load_watchlist()
