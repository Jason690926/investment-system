import yfinance as yf
from modules.yf_session import curl_session
import requests
from curl_cffi import requests as curl_requests

# 修正 Render 環境 IP 被 Yahoo 封鎖問題
_curl_session = curl_requests.Session(impersonate="chrome110")

import pandas as pd
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import config

TW = timezone(timedelta(hours=8))

# yfinance 1.3.0 使用 curl_cffi 自動處理 crumb，不需要自訂 session
import yfinance as yf

def _fetch_ticker(name, symbol, days=90):
    try:
        end = datetime.now(TW)
        start = end - timedelta(days=days)
        ticker = yf.Ticker(symbol, session=curl_session) if curl_session else yf.Ticker(symbol)
        hist = ticker.history(
            start=start.strftime('%Y-%m-%d'),
            end=(end + timedelta(days=1)).strftime('%Y-%m-%d'),
            auto_adjust=True
        )
        if len(hist) >= 2:
            curr = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change_1d = round(((curr - prev) / prev) * 100, 2)

            def pct(n):
                if len(hist) >= n:
                    p = float(hist['Close'].iloc[-n])
                    return round(((curr - p) / p) * 100, 2)
                return None

            return name, {
                'price': round(curr, 2),
                'change': change_1d,
                'change_7d': pct(7),
                'change_14d': pct(14),
                'change_30d': pct(30),
                'change_60d': pct(60),
                'symbol': symbol
            }
    except:
        pass
    return name, {'price': 0, 'change': 0, 'symbol': symbol}

def _fetch_taiwan_ticker(name, symbol):
    for attempt in range(2):
        try:
            end = datetime.now(TW)
            start = end - timedelta(days=120)
            ticker = yf.Ticker(symbol, session=curl_session) if curl_session else yf.Ticker(symbol)
            hist = ticker.history(
                start=start.strftime('%Y-%m-%d'),
                end=(end + timedelta(days=1)).strftime('%Y-%m-%d'),
                auto_adjust=True
            )
            if len(hist) >= 2:
                curr  = float(hist['Close'].iloc[-1])
                prev  = float(hist['Close'].iloc[-2])
                vol   = int(hist['Volume'].iloc[-1])
                vol_5 = int(hist['Volume'].iloc[-5:].mean()) if len(hist) >= 5 else vol
                change_1d = round(((curr - prev) / prev) * 100, 2)

                def pct(n):
                    if len(hist) >= n:
                        p = float(hist['Close'].iloc[-n])
                        return round(((curr - p) / p) * 100, 2)
                    return None

                last_date = hist.index[-1]
                if hasattr(last_date, 'date'):
                    last_date = last_date.date()
                today_tw = datetime.now(TW).date()
                days_diff = (today_tw - last_date).days
                if days_diff > 3:
                    print(f'⚠️ {name}({symbol}) 資料過舊：{last_date}（{days_diff}天前）')

                return name, {
                    'symbol': symbol,
                    'price': round(curr, 2),
                    'change': change_1d,
                    'change_5d': pct(5),
                    'change_20d': pct(20),
                    'volume': vol,
                    'volume_5d_avg': vol_5,
                    'history': hist,
                    'last_date': str(last_date)
                }
        except Exception as e:
            if attempt == 0:
                import time
                print(f'第一次抓取失敗 {name}({symbol})，重試中: {e}')
                time.sleep(2)
            else:
                print(f'抓取失敗 {name}({symbol}): {e}')
    return name, None

def _fetch_macro_ticker(name, symbol):
    try:
        end = datetime.now(TW)
        start = end - timedelta(days=90)
        ticker = yf.Ticker(symbol, session=curl_session) if curl_session else yf.Ticker(symbol)
        hist = ticker.history(
            start=start.strftime('%Y-%m-%d'),
            end=(end + timedelta(days=1)).strftime('%Y-%m-%d'),
            auto_adjust=True
        )
        if len(hist) < 2:
            return name, {'price': 0, 'change': 0, 'symbol': symbol}

        curr = float(hist['Close'].iloc[-1])
        prev = float(hist['Close'].iloc[-2])
        change_1d = round(((curr - prev) / prev) * 100, 2)

        def pct_change(days):
            if len(hist) >= days:
                past = float(hist['Close'].iloc[-days])
                return round(((curr - past) / past) * 100, 2)
            return None

        return name, {
            'price': round(curr, 3),
            'change': change_1d,
            'change_7d': pct_change(7),
            'change_14d': pct_change(14),
            'change_30d': pct_change(30),
            'change_60d': pct_change(60),
            'symbol': symbol
        }
    except:
        pass
    return name, {'price': 0, 'change': 0, 'symbol': symbol}

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
        futures = {ex.submit(_fetch_macro_ticker, n, s): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            result[name] = data
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
    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as ex:
        futures = {ex.submit(_fetch_taiwan_ticker, n, s): n for n, s in symbols.items()}
        for f in as_completed(futures):
            name, data = f.result()
            if data:
                result[name] = data
    return result

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
        'timestamp': datetime.now(TW).strftime('%Y-%m-%d %H:%M')
    }