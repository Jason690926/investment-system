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
        import requests as _rq
        _r = _rq.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': '1d', 'range': '6mo'}, timeout=15)
        _d = _r.json()['chart']['result'][0]
        _ts = _d['timestamp']
        _q = _d['indicators']['quote'][0]
        hist = pd.DataFrame({
            'Close': _q['close'], 'Volume': _q['volume']
        }, index=pd.to_datetime([datetime.fromtimestamp(t) for t in _ts]))
        hist = hist.dropna(subset=['Close'])
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
                'symbol': symbol,
                'last_date': str(hist.index[-1].date() if hasattr(hist.index[-1], 'date') else hist.index[-1]),
            }
    except:
        pass
    return name, {'price': 0, 'change': 0, 'symbol': symbol, 'last_date': None}

def _fetch_taiwan_ticker(name, symbol):
    for attempt in range(2):
        try:
            import requests as _req2
            r = _req2.get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
                headers={'User-Agent': 'Mozilla/5.0'},
                params={'interval': '1d', 'range': '6mo'},
                timeout=15
            )
            data = r.json()['chart']['result'][0]
            import pandas as _pd2
            timestamps = data['timestamp']
            quotes = data['indicators']['quote'][0]
            hist = _pd2.DataFrame({
                'Open': quotes['open'], 'High': quotes['high'],
                'Low': quotes['low'], 'Close': quotes['close'],
                'Volume': quotes['volume'],
            }, index=_pd2.to_datetime([datetime.fromtimestamp(t) for t in timestamps]))
            hist.index.name = 'Date'
            hist = hist.dropna(subset=['Close'])
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
        import requests as _rq
        _r = _rq.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': '1d', 'range': '6mo'}, timeout=15)
        _d = _r.json()['chart']['result'][0]
        _ts, _q = _d['timestamp'], _d['indicators']['quote'][0]
        hist = pd.DataFrame({'Close': _q['close'], 'Volume': _q['volume']},
            index=pd.to_datetime([datetime.fromtimestamp(t) for t in _ts]))
        hist = hist.dropna(subset=['Close'])
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

def get_index_daily_closes(symbol: str = '^TWII', lookback: int = 40) -> dict:
    """取指數（預設大盤 ^TWII）近期日收盤，回傳 {'YYYY-MM-DD': close} 由舊到新。

    Bug D 大盤同期對比用：個股 daily_bars 依日期對齊此 dict 算相對強度。
    失敗回 {}（呼叫端據此不注入大盤對比區塊，誠實 > 錯誤，
    比照 7ee7950 twii freshness pattern）。"""
    try:
        import requests as _rq
        _r = _rq.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': '1d', 'range': '3mo'}, timeout=15)
        _d = _r.json()['chart']['result'][0]
        _ts = _d['timestamp']
        _cl = _d['indicators']['quote'][0]['close']
        out = {}
        for t, c in zip(_ts, _cl):
            if c is None:
                continue
            out[datetime.fromtimestamp(t).strftime('%Y-%m-%d')] = round(float(c), 2)
        if not out:
            return {}
        # 只留最後 lookback 個交易日（dict 在 py3.7+ 保留插入序）
        items = list(out.items())[-lookback:]
        return dict(items)
    except Exception:
        return {}


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

def get_tw_news_rss(n: int = 15) -> list:
    """Google News RSS 抓台股財經新聞（免費，無需 API Key）。
    只保留 12 小時內的新聞（plan §22 F-1）：用戶要求「財經分析必須是報表
    產生時間前 12 小時的新聞才列入」。一鍵分析會即時重生 NEWS，故 cutoff
    相對於本呼叫時刻 ≈ 報表產生時刻。盤前/隔夜可能很少甚至 0 筆，屬刻意
    取捨（誠實精簡 > 補舊文導致 AI 引用過期市場數據）。
    """
    import urllib.request
    import xml.etree.ElementTree as ET
    import urllib.parse
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    query = urllib.parse.quote('台股 投資 財經 科技股 半導體')
    url = f'https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            xml_data = r.read()
        root = ET.fromstring(xml_data)
        items = root.findall('.//item')
        result = []
        for item in items:
            if len(result) >= n:
                break
            title_el  = item.find('title')
            source_el = item.find('source')
            pub_el    = item.find('pubDate')
            title  = title_el.text  if title_el  is not None else ''
            source = source_el.text if source_el is not None else ''
            if not title:
                continue
            if pub_el is not None:
                try:
                    pub_dt = parsedate_to_datetime(pub_el.text)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass  # pubDate 解析失敗則保留該筆
            result.append({'title': title, 'source': source})
        return result
    except Exception as e:
        print(f'[news_rss] 抓取失敗: {e}')
        return []


def _filter_stock_news(items: list, name: str, cutoff, n: int = 5) -> list:
    """§四十二 個股新聞純過濾邏輯（可測試）。

    items: [{'title', 'source', 'pub_dt'(aware datetime | None)}]
    規則：
      - 標題必須含股名（Google News 搜尋模糊匹配不可信，標題含股名才算相關）
      - pub_dt < cutoff → 剔除；pub_dt=None（解析失敗）→ 保留（沿用
        get_tw_news_rss 寬容邏輯）；naive datetime 比較 TypeError → 保留
      - 最多 n 則
    回傳: [{'title', 'source', 'pub_label'}]，pub_label = 台灣時間
    'MM/DD HH:MM'（供 AI 分辨盤前/盤後消息；無 pub_dt → ''）
    """
    from datetime import timezone, timedelta
    TW = timezone(timedelta(hours=8))
    out = []
    for it in items:
        if len(out) >= n:
            break
        title = it.get('title') or ''
        if not title or name not in title:
            continue
        pub_dt = it.get('pub_dt')
        if pub_dt is not None:
            try:
                if pub_dt < cutoff:
                    continue
            except TypeError:
                pass  # naive datetime 無法與 aware cutoff 比較 → 保留
        label = ''
        if pub_dt is not None:
            try:
                label = pub_dt.astimezone(TW).strftime('%m/%d %H:%M')
            except Exception:
                label = ''
        out.append({'title': title, 'source': it.get('source') or '',
                    'pub_label': label})
    return out


def get_stock_news_rss(name: str, symbol: str = '', n: int = 5,
                       hours: int = 24) -> list:
    """§四十二：個股近 24h 新聞（Google News 搜尋 RSS，query=股名）。

    時窗 24h（涵蓋昨盤後重訊公告 + 今日盤中新聞 — 今日漲幅的催化劑常在
    昨盤後發布）。失敗模式：timeout 5s、任何 exception → 回 []（誠實降級，
    caller 走「暫無相關新聞」分支；絕不阻塞分析、不 retry）。
    限流：靠一鍵分析逐股天然間隔（每股間隔 AI 呼叫 20-60s），不加快取。
    symbol 僅供 log 標識，不參與查詢。
    """
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = urllib.parse.quote(name)
    url = (f'https://news.google.com/rss/search?q={query}'
           f'&hl=zh-TW&gl=TW&ceid=TW:zh-TW')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            xml_data = r.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall('.//item'):
            title_el  = item.find('title')
            source_el = item.find('source')
            pub_el    = item.find('pubDate')
            pub_dt = None
            if pub_el is not None and pub_el.text:
                try:
                    pub_dt = parsedate_to_datetime(pub_el.text)
                except Exception:
                    pub_dt = None
            items.append({
                'title':  title_el.text  if title_el  is not None else '',
                'source': source_el.text if source_el is not None else '',
                'pub_dt': pub_dt,
            })
        return _filter_stock_news(items, name, cutoff, n)
    except Exception as e:
        print(f'[stock_news] {symbol or name} 抓取失敗（誠實降級，'
              f'走無新聞分支）: {e}')
        return []


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