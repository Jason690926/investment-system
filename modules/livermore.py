import config

def check_entry_signal(name, technical_data):
    score = 0
    passed = []
    failed = []

    trend = technical_data.get('trend', '')
    rsi = technical_data.get('RSI')
    volume_ratio = technical_data.get('volume_ratio')
    price = technical_data.get('price')
    resistance = technical_data.get('resistance')

    if trend in ['強勢多頭', '多頭']:
        passed.append('✅ 趨勢向上')
        score += 30
    else:
        failed.append('❌ 趨勢不明確或偏空')

    if rsi is not None and 50 <= rsi <= config.RSI_OVERBOUGHT:
        passed.append(f'✅ RSI={rsi} 強勢區間')
        score += 25
    elif rsi is not None and rsi < 50:
        failed.append(f'❌ RSI={rsi} 偏弱')
    elif rsi is not None and rsi > config.RSI_OVERBOUGHT:
        failed.append(f'⚠️ RSI={rsi} 過熱，注意回調')

    if volume_ratio is not None and volume_ratio >= config.VOLUME_RATIO:
        passed.append(f'✅ 成交量放大 {volume_ratio}倍')
        score += 25
    else:
        vr = volume_ratio if volume_ratio is not None else 0
        failed.append(f'❌ 成交量不足（{vr}倍）')

    if trend != '盤整':
        passed.append('✅ 非盤整狀態')
        score += 20
    else:
        failed.append('❌ 目前盤整中，不建議進場')

    if score >= 80:
        recommendation = '強烈建議買進'
        action = 'BUY'
    elif score >= 55:
        recommendation = '可考慮買進'
        action = 'WATCH'
    else:
        recommendation = '暫時觀望'
        action = 'HOLD'

    key_point = None
    if price is not None and resistance is not None:
        if price >= resistance * 0.98:
            key_point = f'⚡ 接近突破關鍵點 {resistance}'

    # 建議進場價位（當前價附近 ±1%）
    # 計算進場區間
    entry_range = '--'
    if price and price > 0:
        entry_low = round(price * 0.995, 2)
        entry_high = round(price * 1.005, 2)
        entry_range = f'{entry_low} ~ {entry_high}'

    return {
        'name': name,
        'score': score,
        'action': action,
        'recommendation': recommendation,
        'passed': passed,
        'failed': failed,
        'key_point': key_point,
        'entry_price': price,
        'entry_range': entry_range,
        'stop_loss': technical_data.get('stop_loss_price', round(price * (1 + config.STOP_LOSS), 2)) if price else None,
        'target': technical_data.get('target1', round(price * 1.08, 2)) if price else None,
        'target2': technical_data.get('target2', round(price * 1.15, 2)) if price else None,
    }

def check_exit_signal(holding, current_price):
    cost = holding['cost']
    pnl_pct = ((current_price - cost) / cost) * 100
    if pnl_pct <= config.STOP_LOSS * 100:
        return {'action': 'SELL', 'reason': f'觸發停損 {round(pnl_pct, 2)}%'}
    elif pnl_pct >= 15:
        return {'action': 'SELL', 'reason': f'達到停利目標 +{round(pnl_pct, 2)}%'}
    else:
        return {'action': 'HOLD', 'reason': f'持續持有，目前損益 {round(pnl_pct, 2)}%'}

def check_pyramid(holding, current_price):
    cost = holding['cost']
    pnl_pct = ((current_price - cost) / cost) * 100
    if pnl_pct >= config.PYRAMID_PROFIT * 100:
        return {'action': 'ADD', 'reason': f'獲利 {round(pnl_pct, 2)}%，可考慮加碼 50%'}
    return {'action': 'HOLD', 'reason': '尚未達加碼條件'}

def analyze_all_signals(technical_results):
    signals = {}
    for name, data in technical_results.items():
        signals[name] = check_entry_signal(name, data)
    buy_signals = {k: v for k, v in signals.items() if v['action'] == 'BUY'}
    watch_signals = {k: v for k, v in signals.items() if v['action'] == 'WATCH'}
    return {
        'all': signals,
        'buy': buy_signals,
        'watch': watch_signals
    }