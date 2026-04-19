import pandas as pd
import numpy as np
import config

def calculate_ma(hist, periods=[5, 20, 60]):
    result = {}
    for period in periods:
        if len(hist) >= period:
            result[f'MA{period}'] = round(hist['Close'].rolling(window=period).mean().iloc[-1], 2)
        else:
            result[f'MA{period}'] = None
    return result

def calculate_rsi(hist, period=14):
    if len(hist) < period + 1:
        return None
    delta = hist['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)

def calculate_volume_ratio(hist, period=20):
    if len(hist) < period:
        return None
    avg_volume = hist['Volume'].rolling(window=period).mean().iloc[-1]
    curr_volume = hist['Volume'].iloc[-1]
    if avg_volume > 0:
        return round(curr_volume / avg_volume, 2)
    return None

def get_trend(hist):
    if len(hist) < 60:
        return '資料不足'
    curr_price = hist['Close'].iloc[-1]
    ma5 = hist['Close'].rolling(5).mean().iloc[-1]
    ma20 = hist['Close'].rolling(20).mean().iloc[-1]
    ma60 = hist['Close'].rolling(60).mean().iloc[-1]
    if ma5 > ma20 > ma60 and curr_price > ma5:
        return '強勢多頭'
    elif ma5 > ma20 and curr_price > ma20:
        return '多頭'
    elif ma5 < ma20 < ma60 and curr_price < ma5:
        return '強勢空頭'
    elif ma5 < ma20 and curr_price < ma20:
        return '空頭'
    else:
        return '盤整'

def analyze_stock(stock_data):
    hist = stock_data['history']
    ma = calculate_ma(hist)
    rsi = calculate_rsi(hist)
    volume_ratio = calculate_volume_ratio(hist)
    trend = get_trend(hist)
    curr_price = stock_data['price']

    support = round(hist['Low'].rolling(20).min().iloc[-1], 2)
    resistance = round(hist['High'].rolling(20).max().iloc[-1], 2)

    signals = []
    if ma.get('MA5') and ma.get('MA20'):
        if ma['MA5'] > ma['MA20']:
            signals.append('MA5上穿MA20（黃金交叉）')
    if rsi:
        if rsi < config.RSI_OVERSOLD:
            signals.append(f'RSI={rsi} 超賣區間（可能反彈）')
        elif rsi > config.RSI_OVERBOUGHT:
            signals.append(f'RSI={rsi} 超買區間（注意回調）')
        else:
            signals.append(f'RSI={rsi} 正常區間')
    if volume_ratio and volume_ratio > config.VOLUME_RATIO:
        signals.append(f'成交量放大 {volume_ratio}倍（強勢訊號）')

   # 斐波那契計算目標價（華爾街標準方法）
    recent_low = hist['Low'].rolling(20).min().iloc[-1]
    recent_high = hist['High'].rolling(20).max().iloc[-1]
    swing = curr_price - recent_low  # 波段幅度

    # 進場區間：當前價 ±0.5%
    entry_low = round(curr_price * 0.995, 2)
    entry_high = round(curr_price * 1.005, 2)

    # 第一目標：前20日高點（近期壓力位）
    target1 = round(recent_high, 2)

    # 第二目標：斐波那契 1.618 延伸
    target2 = round(recent_low + swing * 1.618, 2)

    # 停損：近期支撐下方3%（跌破支撐確認出場）
    atr_values = hist['High'] - hist['Low']
    atr = atr_values.rolling(14).mean().iloc[-1]
    # 停損：取「現價-2倍ATR」和「近期支撐-1%」兩者中較高的值
    stop_atr = round(curr_price - atr * 2, 2)
    stop_support = round(support * 0.99, 2)
    stop_loss = max(stop_atr, stop_support)
    stop_loss = round(stop_loss, 2)

    # 確保目標價合理（至少比現價高2%）
    if target1 <= curr_price * 1.02:
        target1 = round(curr_price * 1.05, 2)
    if target2 <= target1:
        target2 = round(target1 * 1.08, 2)

    return {
        'price': curr_price,
        'change': stock_data['change'],
        'trend': trend,
        'MA5': ma.get('MA5'),
        'MA20': ma.get('MA20'),
        'MA60': ma.get('MA60'),
        'RSI': rsi,
        'volume_ratio': volume_ratio,
        'support': support,
        'resistance': resistance,
        'signals': signals,
        'entry_low': entry_low,
        'entry_high': entry_high,
        'target1': target1,
        'target2': target2,
        'stop_loss_price': stop_loss,
    }

def analyze_all_stocks(taiwan_stocks):
    result = {}
    for name, data in taiwan_stocks.items():
        if 'history' in data:
            result[name] = analyze_stock(data)
    return result