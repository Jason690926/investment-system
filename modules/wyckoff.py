import numpy as np

def analyze_wyckoff(hist, technical_data):
    """
    威科夫量價分析
    回傳：階段、量價關係、關鍵事件
    """
    if hist is None or len(hist) < 20:
        return {
            'phase': '資料不足',
            'phase_desc': '需要更多歷史資料才能判斷威科夫階段',
            'effort_result': '無法判斷',
            'effort_desc': '',
            'events': [],
            'summary': '資料不足，無法進行威科夫分析'
        }

    c = hist['Close'].values
    v = hist['Volume'].values
    h = hist['High'].values
    l = hist['Low'].values
    o = hist['Open'].values
    n = len(c)

    # ===== 1. 四大階段判斷 =====
    phase, phase_desc = _detect_phase(c, v, h, l, technical_data)

    # ===== 2. 量價關係（努力 vs 結果）=====
    effort_result, effort_desc = _analyze_effort_result(c, v, h, l)

    # ===== 3. 關鍵事件偵測 =====
    events = _detect_wyckoff_events(c, v, h, l, o, technical_data)

    # ===== 4. 綜合摘要 =====
    summary = _build_summary(phase, effort_result, events)

    return {
        'phase': phase,
        'phase_desc': phase_desc,
        'effort_result': effort_result,
        'effort_desc': effort_desc,
        'events': events,
        'summary': summary
    }


def _detect_phase(c, v, h, l, tech):
    """判斷威科夫四大階段"""
    n = len(c)
    # 近20日價格區間
    price_range_20 = max(h[-20:]) - min(l[-20:])
    price_center_20 = (max(h[-20:]) + min(l[-20:])) / 2
    curr_price = c[-1]

    # 均線方向
    ma5  = tech.get('MA5')
    ma20 = tech.get('MA20')
    ma60 = tech.get('MA60')
    trend = tech.get('trend', '')
    rsi  = tech.get('RSI', 50) or 50

    # 近20日量能變化
    vol_early = np.mean(v[-20:-10]) if n >= 20 else np.mean(v)
    vol_late  = np.mean(v[-10:])
    vol_trend = vol_late / vol_early if vol_early > 0 else 1.0

    # 近20日價格波動率
    price_changes = np.abs(np.diff(c[-20:])) / c[-21:-1]
    volatility = np.mean(price_changes)

    # 判斷邏輯
    if trend in ['強勢多頭', '多頭']:
        if rsi > 70 and vol_trend < 0.8:
            # 上漲末段量縮 → 可能進入派發
            return '派發期（Distribution）', \
                '價格在高位，量能開始萎縮，主力可能正在出貨。需注意是否出現量增不漲或高位震盪。'
        else:
            return '上漲期（Markup）', \
                '趨勢向上，量價配合良好，主力推升階段。可順勢持有，逢回測支撐加碼。'

    elif trend in ['強勢空頭', '空頭']:
        if rsi < 30 and vol_trend < 0.8:
            # 下跌末段量縮 → 可能進入累積
            return '累積期（Accumulation）', \
                '價格在低位，量能萎縮，跌勢趨緩，主力可能開始低吸。注意是否出現 Spring 彈簧訊號。'
        else:
            return '下跌期（Markdown）', \
                '趨勢向下，空方主導。不建議進場，等待明確止跌訊號（縮量止跌、Spring）再考慮布局。'

    else:  # 盤整
        if vol_trend < 0.7 and volatility < 0.015:
            return '累積期（Accumulation）', \
                '價格橫盤整理，量能持續萎縮，波動率低。可能是主力低調吸籌，等待放量突破訊號。'
        elif vol_trend > 1.3 and rsi > 60:
            return '派發期（Distribution）', \
                '高位橫盤，量能放大但價格未有效突破，主力可能在震盪中出貨，需謹慎。'
        else:
            return '累積期（Accumulation）', \
                '盤整走勢，方向未明。觀察量能與突破方向，放量向上為買進訊號，放量向下需迴避。'


def _analyze_effort_result(c, v, h, l):
    """
    分析量價關係（努力 vs 結果）
    努力 = 成交量（能量投入）
    結果 = 價格變動幅度（實際效果）
    """
    if len(c) < 5:
        return '無法判斷', ''

    # 近5日的努力（量）與結果（價格變化）
    recent_vol   = v[-5:]
    recent_moves = np.abs(c[-5:] - c[-6:-1]) / c[-6:-1]  # 每日漲跌幅

    avg_vol  = np.mean(v[-20:]) if len(v) >= 20 else np.mean(v)
    avg_move = np.mean(np.abs(np.diff(c[-20:])) / c[-21:-1]) if len(c) >= 20 else 0.01

    # 今日數據
    today_vol   = v[-1]
    today_move  = abs(c[-1] - c[-2]) / c[-2] if c[-2] > 0 else 0
    today_up    = c[-1] > c[-2]

    vol_ratio  = today_vol / avg_vol if avg_vol > 0 else 1.0
    move_ratio = today_move / avg_move if avg_move > 0 else 1.0

    # 判斷邏輯
    if vol_ratio > 1.5 and move_ratio > 1.5:
        if today_up:
            return '量價齊揚（健康多頭）', \
                f'今日量能放大至均量的 {vol_ratio:.1f} 倍，價格漲幅也同步放大。努力與結果相符，多方動能強勁，趨勢可信賴。'
        else:
            return '量增價跌（空方主導）', \
                f'今日量能放大至均量的 {vol_ratio:.1f} 倍，但價格下跌。大量賣壓湧現，空方控盤，需警惕進一步下跌。'

    elif vol_ratio > 1.5 and move_ratio < 0.5:
        if today_up:
            return '努力 > 結果（上漲力竭）', \
                f'今日成交量大（均量 {vol_ratio:.1f} 倍），但漲幅很小。大量買盤卻換不到漲幅，代表賣壓沉重，多方力竭訊號，需警惕轉折。'
        else:
            return '努力 > 結果（下跌吸收）', \
                f'今日成交量大（均量 {vol_ratio:.1f} 倍），但跌幅有限。大量賣壓被買盤吸收，止跌訊號，可能即將反彈。'

    elif vol_ratio < 0.6 and move_ratio > 1.2:
        if today_up:
            return '努力 < 結果（主力拉抬）', \
                f'今日量能僅均量的 {vol_ratio:.1f} 倍，但漲幅大。小量推升大漲，代表籌碼集中，主力控盤明顯，上漲阻力小。'
        else:
            return '努力 < 結果（無量下跌）', \
                f'今日量能僅均量的 {vol_ratio:.1f} 倍，但跌幅較大。無量下跌代表持股者惜售，技術性回調為主，非主力出貨。'

    elif vol_ratio < 0.6 and move_ratio < 0.5:
        return '量縮價穩（籌碼鎖定）', \
            f'今日量能萎縮（均量 {vol_ratio:.1f} 倍），價格波動也小。籌碼高度鎖定，觀望氣氛濃，等待方向選擇。'

    else:
        return '量價正常（無特殊訊號）', \
            f'今日量能（均量 {vol_ratio:.1f} 倍）與價格變動均在正常範圍，無明顯威科夫訊號。'


def _detect_wyckoff_events(c, v, h, l, o, tech):
    """偵測威科夫關鍵事件"""
    events = []
    if len(c) < 10:
        return events

    support   = tech.get('support', min(l[-20:]))
    resistance = tech.get('resistance', max(h[-20:]))
    avg_vol   = np.mean(v[-20:]) if len(v) >= 20 else np.mean(v)

    # ===== Spring（彈簧）=====
    # 跌破支撐後當日或次日快速拉回
    if (l[-1] < support * 0.99 and c[-1] > support and
            v[-1] > avg_vol * 1.2):
        events.append({
            'name': '🌱 Spring（彈簧）',
            'type': 'bullish',
            'desc': f'今日盤中跌破支撐 {round(support,1)} 元後快速收復，且量能放大。這是威科夫最重要的看多訊號，代表主力在低點吸籌，假跌破真做多。'
        })

    # ===== Upthrust（上推測試）=====
    # 突破壓力後快速回落
    if (h[-1] > resistance * 1.01 and c[-1] < resistance and
            v[-1] > avg_vol * 1.2):
        events.append({
            'name': '⬆️ Upthrust（上推）',
            'type': 'bearish',
            'desc': f'今日盤中突破壓力 {round(resistance,1)} 元後快速回落，且量能放大。假突破訊號，主力在高點出貨，需警惕下跌風險。'
        })

    # ===== SOT（次級測試）=====
    # 縮量回測支撐守住
    if (abs(c[-1] - support) / support < 0.02 and
            c[-1] > support * 0.99 and
            v[-1] < avg_vol * 0.7):
        events.append({
            'name': '🔍 SOT（次級測試）',
            'type': 'bullish',
            'desc': f'今日縮量回測支撐 {round(support,1)} 元附近守住，量能萎縮代表賣壓減少，支撐有效確認，可考慮分批進場。'
        })

    # ===== Sign of Strength（強勢訊號）=====
    # 放量突破壓力
    if (c[-1] > resistance and c[-2] <= resistance and
            v[-1] > avg_vol * 1.5):
        events.append({
            'name': '💪 SOS（強勢突破）',
            'type': 'bullish',
            'desc': f'今日放量突破壓力 {round(resistance,1)} 元，量能達均量 {round(v[-1]/avg_vol,1)} 倍。威科夫強勢訊號，上漲期開始，可積極做多。'
        })

    # ===== Sign of Weakness（弱勢訊號）=====
    # 放量跌破支撐
    if (c[-1] < support and c[-2] >= support and
            v[-1] > avg_vol * 1.5):
        events.append({
            'name': '⚠️ SOW（弱勢跌破）',
            'type': 'bearish',
            'desc': f'今日放量跌破支撐 {round(support,1)} 元，量能達均量 {round(v[-1]/avg_vol,1)} 倍。威科夫弱勢訊號，下跌期可能開始，建議減碼或停損。'
        })

    # ===== 量能高峰（Climax）=====
    # 近期最大量，且出現在趨勢末端
    max_vol_20 = max(v[-20:])
    if v[-1] == max_vol_20 and v[-1] > avg_vol * 2.5:
        price_up = c[-1] > c[-5]
        if price_up:
            events.append({
                'name': '🚨 BC（買盤高潮）',
                'type': 'bearish',
                'desc': f'今日成交量創近20日新高（均量 {round(v[-1]/avg_vol,1)} 倍），且出現在上漲末端。可能是買盤高潮，主力大量出貨，需警惕趨勢反轉。'
            })
        else:
            events.append({
                'name': '📢 SC（賣盤高潮）',
                'type': 'bullish',
                'desc': f'今日成交量創近20日新高（均量 {round(v[-1]/avg_vol,1)} 倍），且出現在下跌末端。可能是賣盤高潮，恐慌性拋售尾聲，底部訊號。'
            })

    return events


def _build_summary(phase, effort_result, events):
    """建立威科夫綜合摘要"""
    bullish_events = [e for e in events if e['type'] == 'bullish']
    bearish_events = [e for e in events if e['type'] == 'bearish']

    if bearish_events:
        bias = '⚠️ 偏空（建議謹慎）'
    elif bullish_events:
        bias = '✅ 偏多（可積極操作）'
    else:
        bias = '⏳ 中性（觀望等待）'

    event_names = '、'.join([e['name'] for e in events]) if events else '無特殊事件'
    return f"階段：{phase} ｜ 量價：{effort_result} ｜ 事件：{event_names} ｜ 偏向：{bias}"