import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
import config

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
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                change = ((curr_close - prev_close) / prev_close) * 100
                result[name] = {
                    'price': round(curr_close, 2),
                    'change': round(change, 2),
                    'symbol': symbol
                }
        except Exception as e:
            result[name] = {'price': 0, 'change': 0, 'symbol': symbol}
    return result

def get_commodities():
    symbols = {
        '黃金': 'GC=F',
        '原油(WTI)': 'CL=F',
        '美元指數': 'DX-Y.NYB',
        '美元/台幣': 'TWD=X',
    }
    result = {}
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                change = ((curr_close - prev_close) / prev_close) * 100
                result[name] = {
                    'price': round(curr_close, 2),
                    'change': round(change, 2)
                }
        except Exception as e:
            result[name] = {'price': 0, 'change': 0}
    return result

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
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='60d')
            if len(hist) > 0:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((curr - prev) / prev) * 100
                result[name] = {
                    'symbol': symbol,
                    'price': round(curr, 2),
                    'change': round(change, 2),
                    'volume': int(hist['Volume'].iloc[-1]),
                    'history': hist
                }
        except Exception as e:
            pass
    return result

def get_financial_news():
    url = f"https://newsapi.org/v2/everything"
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
            articles = []
            for article in data.get('articles', []):
                articles.append({
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', ''),
                    'publishedAt': article.get('publishedAt', '')
                })
            return articles
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
    return []

def get_all_data():
    print("正在抓取全球市場資料...")
    global_markets = get_global_markets()
    print("正在抓取大宗商品資料...")
    commodities = get_commodities()
    print("正在抓取台股資料...")
    taiwan_stocks = get_taiwan_stocks()
    print("正在抓取財經新聞...")
    news = get_financial_news()
    return {
        'global_markets': global_markets,
        'commodities': commodities,
        'taiwan_stocks': taiwan_stocks,
        'news': news,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
def get_macro_assets():
    """抓取美債/黃金/石油資料"""
    symbols = {
        '美國10年期公債殖利率': '^TNX',
        '黃金現貨': 'GC=F',
        'WTI原油': 'CL=F',
        '美元指數': 'DX-Y.NYB',
        '美國2年期公債殖利率': '^IRX',
    }
    result = {}
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d')
            if len(hist) >= 2:
                prev = hist['Close'].iloc[-2]
                curr = hist['Close'].iloc[-1]
                change = ((curr - prev) / prev) * 100
                result[name] = {
                    'price': round(curr, 3),
                    'change': round(change, 2),
                    'symbol': symbol
                }
        except Exception as e:
            result[name] = {'price': 0, 'change': 0, 'symbol': symbol}
    return result

def get_watchlist_stocks(watchlist):
    """根據watchlist抓取持股資料"""
    symbols = {item['name']: item['symbol'] for item in watchlist}
    result = get_taiwan_stocks(symbols)
    # 把watchlist的額外資訊附加進去
    for item in watchlist:
        name = item['name']
        if name in result:
            result[name]['cost'] = item.get('cost')
            result[name]['shares'] = item.get('shares')
            result[name]['buy_date'] = item.get('buy_date')
    return result