import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import config

# ── 單檔抓取（供平行化使用）────────────────────────────────
def _fetch_ticker(name, symbol, period='2d'):
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if len(hist) >= 2:
            prev = hist['Close'].iloc[-2]
            curr = hist['Close'].iloc[-1]
            change = ((curr - prev) / prev) * 100
            return name, {
                'price': round(curr, 2),
                'change': round(change, 2),
                'symbol': symbol
            }
    except:
        pass
    return name, {'price': 0, 'change': 0, 'symbol': symbol}

def _fetch_taiwan_ticker(name, symbol):
    try:
        hist = yf.Ticker(symbol).history(period='60d')
        if len(hist) > 0:
            curr = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            change = ((curr - prev) / prev) * 100
            return name, {
                'symbol': symbol,
                'price': round(curr, 2),
                'change': round(change, 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'history': hist
            }
    except:
        pass
    return name, None

# ── 全球市場（平行）──────────────────────────────────────
def get_global_markets():
    symbols = {
        '美國道瓊': '^DJI',
        '美國S&P500': '^GSPC',
        '美國納斯達克': '^IXIC',
        '日本日經225': '^N225',
        '香港恆生': '^HSI',
        '上海綜合': '000001.SS',
        '台灣加權': '^TWII',
        '英國富時100': '^FTSE',
        '德國DAX': '^GDAXI',
    }
    result = {}
    with ThreadPoolExecutor(max_workers=9) as ex:
        futures = {ex.submit(_fetch_ticker, n, s): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            result[name] = data
    return result

# ── 大宗商品（平行）──────────────────────────────────────
def get_commodities():
    symbols = {
        '黃金': 'GC=F',
        '原油(WTI)': 'CL=F',
        '美元指數': 'DX-Y.NYB',
        '美元/台幣': 'TWD=X',
    }
    result = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_ticker, n, s): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            result[name] = data
    return result

# ── 總體資產（平行）──────────────────────────────────────
def get_macro_assets():
    symbols = {
        '美國10年期公債殖利率': '^TNX',
        '黃金現貨': 'GC=F',
        'WTI原油': 'CL=F',
        '美元指數': 'DX-Y.NYB',
        '美國2年期公債殖利率': '^IRX',
    }
    result = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_ticker, n, s, '5d'): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            result[name] = data
    return result

# ── 台股（平行）──────────────────────────────────────────
def get_taiwan_stocks(symbols=None):
    if symbols is None:
        symbols = {
            '台積電': '2330.TW',
            '鴻海': '2317.TW',
            '聯發科': '2454.TW',
            '台達電': '2308.TW',
            '富邦金': '2881.TW',
            '國泰金': '2882.TW',
            '中華電': '2412.TW',
            '統一超': '2912.TW',
        }
    result = {}
    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as ex:
        futures = {ex.submit(_fetch_taiwan_ticker, n, s): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            if data:
                result[name] = data
    return result

# ── 財經新聞 ──────────────────────────────────────────────
def get_financial_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        'q': 'stock market OR economy OR Federal Reserve OR Taiwan semiconductor',
        'language': 'en',
        'sortBy': 'publishedAt',
        'pageSize': 10,
        'apiKey': config.NEWS_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get('status') == 'ok':
            return [{
                'title': a.get('title', ''),
                'description': a.get('description', ''),
                'source': a.get('source', {}).get('name', ''),
                'publishedAt': a.get('publishedAt', '')
            } for a in data.get('articles', [])]
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
    return []

# ── 持股追蹤（平行）──────────────────────────────────────
def get_watchlist_stocks(watchlist):
    symbols = {item['name']: item['symbol'] for item in watchlist}
    result = get_taiwan_stocks(symbols)
    for item in watchlist:
        name = item['name']
        if name in result:
            result[name]['cost'] = item.get('cost')
            result[name]['shares'] = item.get('shares')
            result[name]['buy_date'] = item.get('buy_date')
    return result

# ── 一次抓全部（平行）────────────────────────────────────
def get_all_data():
    print("平行抓取所有資料中...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_global    = ex.submit(get_global_markets)
        f_commodity = ex.submit(get_commodities)
        f_taiwan    = ex.submit(get_taiwan_stocks)
        f_news      = ex.submit(get_financial_news)
        global_markets = f_global.result()
        commodities    = f_commodity.result()
        taiwan_stocks  = f_taiwan.result()
        news           = f_news.result()
    return {
        'global_markets': global_markets,
        'commodities': commodities,
        'taiwan_stocks': taiwan_stocks,
        'news': news,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
