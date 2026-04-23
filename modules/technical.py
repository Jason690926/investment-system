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
    actual_period = min(period, len(hist) - 1)
    if actual_period < 5:
        return None
    avg_volume = hist['Volume'].rolling(window=actual_period).mean().iloc[-1]
    curr_volume = hist['Volume'].iloc[-1]
    if avg_volume > 0:
        return round(curr_volume / avg_volume, 2)
    return None

def get_trend(hist):
    n = len(hist)
    curr_price = hist['Close'].iloc[-1]

    # 資料不足 60 天時，用較短的均線判斷
    if n >= 60:
        ma5  = hist['Close'].rolling(5).mean().iloc[-1]
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
    elif n >= 20:
        ma5  = hist['Close'].rolling(5).mean().iloc[-1]
        ma20 = hist['Close'].rolling(20).mean().iloc[-1]
        if ma5 > ma20 and curr_price > ma5:
            return '多頭'
        elif ma5 < ma20 and curr_price < ma5:
            return '空頭'
        else:
            return '盤整'
    elif n >= 5:
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        return '多頭' if curr_price > ma5 else '空頭'
    else:
        return '資料不足'

def analyze_stock(stock_data):
    hist = stock_data['history']
    n = len(hist)
    ma = calculate_ma(hist)
    rsi = calculate_rsi(hist)
    volume_ratio = calculate_volume_ratio(hist)
    trend = get_trend(hist)
    curr_price = stock_data['price']

    # 支撐壓力：依資料量調整計算週期
    lookback = min(20, n - 1)
    support    = round(hist['Low'].rolling(lookback).min().iloc[-1], 2)
    resistance = round(hist['High'].rolling(lookback).max().iloc[-1], 2)

    # 第二支撐/壓力（10日）
    lookback2 = min(10, n - 1)
    support2   = round(hist['Low'].rolling(lookback2).min().iloc[-1], 2)
    resistance2 = round(hist['High'].rolling(lookback2).max().iloc[-1], 2)

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

    # 斐波那契計算目標價
    recent_low  = hist['Low'].rolling(lookback).min().iloc[-1]
    recent_high = hist['High'].rolling(lookback).max().iloc[-1]
    swing = curr_price - recent_low

    entry_low  = round(curr_price * 0.995, 2)
    entry_high = round(curr_price * 1.005, 2)
    target1 = round(recent_high, 2)
    target2 = round(recent_low + swing * 1.618, 2)

    # ATR 停損
    atr_lookback = min(14, n - 1)
    atr_values = hist['High'] - hist['Low']
    atr = atr_values.rolling(atr_lookback).mean().iloc[-1]
    stop_atr     = round(curr_price - atr * 2, 2)
    stop_support = round(support * 0.99, 2)
    stop_loss    = round(max(stop_atr, stop_support), 2)

    # 確保目標價合理
    if target1 <= curr_price * 1.02:
        target1 = round(curr_price * 1.05, 2)
    if target2 <= target1:
        target2 = round(target1 * 1.08, 2)

    # 計算今日量和5日均量（提供給 AI 分析用）
    vol_today = int(hist['Volume'].iloc[-1]) if len(hist) >= 1 else 0
    vol_5d_avg = int(hist['Volume'].iloc[-5:].mean()) if len(hist) >= 5 else vol_today

    return {
        'price': curr_price,
        'change': stock_data['change'],
        'change_5d': stock_data.get('change_5d'),
        'change_20d': stock_data.get('change_20d'),
        'trend': trend,
        'MA5': ma.get('MA5'),
        'MA20': ma.get('MA20'),
        'MA60': ma.get('MA60'),
        'RSI': rsi,
        'volume': vol_today,
        'volume_5d_avg': vol_5d_avg,
        'volume_ratio': volume_ratio,
        'support': support,
        'support2': support2,
        'resistance': resistance,
        'resistance2': resistance2,
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
