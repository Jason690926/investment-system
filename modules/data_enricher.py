"""
data_enricher.py
為 Phase 2 新增的資料擴充層：週K、月K、MACD、MA、成交量(張)
不修改舊 data_fetcher.py，保持 main.py 現有流程不受影響
"""
import requests
import pandas as pd
from datetime import datetime


def _yahoo_ohlcv(symbol: str, interval: str, range_: str) -> pd.DataFrame | None:
    """從 Yahoo Finance v8 API 抓指定週期的 OHLCV"""
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': interval, 'range': range_},
            timeout=15
        )
        d = r.json()['chart']['result'][0]
        q = d['indicators']['quote'][0]
        df = pd.DataFrame({
            'Open':   q['open'],
            'High':   q['high'],
            'Low':    q['low'],
            'Close':  q['close'],
            'Volume': q['volume'],
        }, index=pd.to_datetime([datetime.fromtimestamp(t) for t in d['timestamp']]))
        df.index.name = 'Date'
        return df.dropna(subset=['Close'])
    except Exception as e:
        print(f"[data_enricher] 抓取失敗 {symbol} {interval}: {e}")
        return None


def _calc_macd(close: pd.Series, fast=12, slow=26, signal=9) -> dict:
    ema_fast   = close.ewm(span=fast, adjust=False).mean()
    ema_slow   = close.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return {
        'macd':      round(float(macd_line.iloc[-1]),   3),
        'signal':    round(float(signal_line.iloc[-1]), 3),
        'histogram': round(float(histogram.iloc[-1]),   3),
    }


def _ohlcv_to_list(df: pd.DataFrame, n: int) -> list:
    """把最近 n 根 K 棒轉成 list of dict，成交量單位：張"""
    rows = df.tail(n)
    result = []
    for dt, row in rows.iterrows():
        vol_raw = row['Volume']
        vol_zhang = round(float(vol_raw) / 1000, 1) if vol_raw and vol_raw == vol_raw else None
        result.append({
            'date':   dt.strftime('%Y-%m-%d'),
            'open':   round(float(row['Open']),  2),
            'high':   round(float(row['High']),  2),
            'low':    round(float(row['Low']),   2),
            'close':  round(float(row['Close']), 2),
            'volume_zhang': vol_zhang,
        })
    return result


def get_stock_info(symbol: str) -> dict | None:
    """快速查詢股票名稱與現價（不抓 OHLCV，省時間）"""
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': '1d', 'range': '1d'},
            timeout=8
        )
        meta = r.json()['chart']['result'][0]['meta']
        return {
            'symbol': symbol,
            'name':   meta.get('longName') or meta.get('shortName') or '',
            'price':  meta.get('regularMarketPrice'),
        }
    except Exception:
        return None


def get_full_stock_data(symbol: str) -> dict | None:
    """
    回傳一支台股的完整分析資料：
    - daily:   最近 60 日 OHLCV + MA5/20/60 + MACD + 成交量(張)
    - weekly:  最近 26 週 OHLCV
    - monthly: 最近 12 月 OHLCV
    """
    daily   = _yahoo_ohlcv(symbol, '1d', '4mo')
    weekly  = _yahoo_ohlcv(symbol, '1wk', '6mo')
    monthly = _yahoo_ohlcv(symbol, '1mo', '2y')

    if daily is None or len(daily) < 5:
        return None

    close = daily['Close']
    vol   = daily['Volume']

    # MA
    ma5  = round(float(close.rolling(5).mean().iloc[-1]),  2) if len(close) >= 5  else None
    ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2) if len(close) >= 20 else None
    ma60 = round(float(close.rolling(60).mean().iloc[-1]), 2) if len(close) >= 60 else None

    # MACD（需要至少 35 根）
    macd = _calc_macd(close) if len(close) >= 35 else None

    # 成交量（張）
    vol_today     = round(float(vol.iloc[-1]) / 1000, 1)
    vol_5d_avg    = round(float(vol.tail(5).mean()) / 1000, 1) if len(vol) >= 5 else vol_today

    return {
        'symbol':       symbol,
        'price':        round(float(close.iloc[-1]), 2),
        'ma5':          ma5,
        'ma20':         ma20,
        'ma60':         ma60,
        'macd':         macd,
        'volume_zhang':     vol_today,
        'volume_5d_avg_zhang': vol_5d_avg,
        'daily_bars':   _ohlcv_to_list(daily,  60),
        'weekly_bars':  _ohlcv_to_list(weekly, 26) if weekly is not None else [],
        'monthly_bars': _ohlcv_to_list(monthly, 12) if monthly is not None else [],
    }
