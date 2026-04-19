import pandas as pd
import numpy as np

def detect_patterns(hist):
    """
    偵測K線型態，回傳發現的型態清單
    """
    if len(hist) < 5:
        return []

    patterns = []
    o = hist['Open'].values
    h = hist['High'].values
    l = hist['Low'].values
    c = hist['Close'].values
    v = hist['Volume'].values

    # 最近幾根K線
    i = len(c) - 1  # 最新
    body = abs(c[i] - o[i])
    total = h[i] - l[i]
    upper_shadow = h[i] - max(c[i], o[i])
    lower_shadow = min(c[i], o[i]) - l[i]

    if total == 0:
        return []

    body_ratio = body / total

    # ===== 單K線型態 =====

    # 錘子線（底部反轉看多）
    if (lower_shadow > body * 2 and
        upper_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] > o[i]):
        patterns.append({
            'name': '錘子線',
            'type': 'bullish',
            'desc': '下影線很長，代表空方打壓後多方反攻，底部反轉訊號，可考慮買進',
            'strength': 'medium'
        })

    # 倒錘子線（底部反轉看多）
    if (upper_shadow > body * 2 and
        lower_shadow < body * 0.3 and
        body_ratio > 0.1):
        patterns.append({
            'name': '倒錘子線',
            'type': 'bullish',
            'desc': '上影線很長但收在低點，底部出現代表多方嘗試反攻，需隔日確認',
            'strength': 'weak'
        })

    # 射擊之星（頂部反轉看空）
    if (upper_shadow > body * 2 and
        lower_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] < o[i]):
        patterns.append({
            'name': '射擊之星',
            'type': 'bearish',
            'desc': '高點出現長上影線，多方拉高後被空方壓回，頂部反轉訊號，注意賣出',
            'strength': 'medium'
        })

    # 墓碑十字（強烈頂部訊號）
    if (upper_shadow > total * 0.7 and
        lower_shadow < total * 0.05 and
        body_ratio < 0.1):
        patterns.append({
            'name': '墓碑十字',
            'type': 'bearish',
            'desc': '開收盤幾乎在低點，上方長影線代表多方完全潰敗，強烈賣出訊號',
            'strength': 'strong'
        })

    # 十字星（市場猶豫）
    if body_ratio < 0.1 and total > 0:
        patterns.append({
            'name': '十字星',
            'type': 'neutral',
            'desc': '開收盤幾乎相同，市場多空力道相當，方向待確認，需觀察下一根K線',
            'strength': 'weak'
        })

    # 大陽線（強勢多頭）
    if c[i] > o[i] and body_ratio > 0.7:
        patterns.append({
            'name': '大陽線',
            'type': 'bullish',
            'desc': '實體很長的紅K，多方力道強勁，趨勢向上確認訊號',
            'strength': 'medium'
        })

    # 大陰線（強勢空頭）
    if c[i] < o[i] and body_ratio > 0.7:
        patterns.append({
            'name': '大陰線',
            'type': 'bearish',
            'desc': '實體很長的黑K，空方力道強勁，趨勢向下確認訊號',
            'strength': 'medium'
        })

    # ===== 雙K線型態 =====
    if i >= 1:
        o1, h1, l1, c1 = o[i-1], h[i-1], l[i-1], c[i-1]
        o0, h0, l0, c0 = o[i], h[i], l[i], c[i]

        # 多頭吞噬
        if (c1 < o1 and c0 > o0 and
            c0 > o1 and o0 < c1):
            patterns.append({
                'name': '多頭吞噬',
                'type': 'bullish',
                'desc': '今日大陽線完全吞噬昨日陰線，多方強勢反轉，底部出現為強烈買進訊號',
                'strength': 'strong'
            })

        # 空頭吞噬
        if (c1 > o1 and c0 < o0 and
            c0 < o1 and o0 > c1):
            patterns.append({
                'name': '空頭吞噬',
                'type': 'bearish',
                'desc': '今日大陰線完全吞噬昨日陽線，空方強勢反轉，頂部出現為強烈賣出訊號',
                'strength': 'strong'
            })

        # 烏雲蓋頂（酒田戰法）
        if (c1 > o1 and c0 < o0 and
            o0 > h1 and c0 < (o1 + c1) / 2 and c0 > o1):
            patterns.append({
                'name': '烏雲蓋頂',
                'type': 'bearish',
                'desc': '酒田戰法：昨日大陽線後今日跳空開高卻收低，空方反攻訊號，考慮減碼',
                'strength': 'strong'
            })

        # 曙光初現（酒田戰法）
        if (c1 < o1 and c0 > o0 and
            o0 < l1 and c0 > (o1 + c1) / 2 and c0 < o1):
            patterns.append({
                'name': '曙光初現',
                'type': 'bullish',
                'desc': '酒田戰法：昨日大陰線後今日跳空開低卻收高，多方反攻訊號，考慮買進',
                'strength': 'strong'
            })

    # ===== 三K線型態 =====
    if i >= 2:
        # 三白兵（強烈看多）
        if (c[i-2] > o[i-2] and c[i-1] > o[i-1] and c[i] > o[i] and
            c[i-1] > c[i-2] and c[i] > c[i-1] and
            o[i-1] > o[i-2] and o[i] > o[i-1]):
            patterns.append({
                'name': '三白兵',
                'type': 'bullish',
                'desc': '連續三根大陽線，每日收盤都比前日高，多方氣勢如虹，強烈買進訊號',
                'strength': 'strong'
            })

        # 三黑鴉（強烈看空）
        if (c[i-2] < o[i-2] and c[i-1] < o[i-1] and c[i] < o[i] and
            c[i-1] < c[i-2] and c[i] < c[i-1] and
            o[i-1] < o[i-2] and o[i] < o[i-1]):
            patterns.append({
                'name': '三黑鴉',
                'type': 'bearish',
                'desc': '連續三根大陰線，每日收盤都比前日低，空方氣勢如虹，強烈賣出訊號',
                'strength': 'strong'
            })

        # 早晨之星（底部反轉）
        if (c[i-2] < o[i-2] and
            abs(c[i-1] - o[i-1]) < (h[i-1] - l[i-1]) * 0.3 and
            c[i] > o[i] and c[i] > (o[i-2] + c[i-2]) / 2):
            patterns.append({
                'name': '早晨之星',
                'type': 'bullish',
                'desc': '酒田戰法：陰線+小實體+大陽線，底部強烈反轉訊號，適合買進',
                'strength': 'strong'
            })

        # 黃昏之星（頂部反轉）
        if (c[i-2] > o[i-2] and
            abs(c[i-1] - o[i-1]) < (h[i-1] - l[i-1]) * 0.3 and
            c[i] < o[i] and c[i] < (o[i-2] + c[i-2]) / 2):
            patterns.append({
                'name': '黃昏之星',
                'type': 'bearish',
                'desc': '酒田戰法：陽線+小實體+大陰線，頂部強烈反轉訊號，適合賣出',
                'strength': 'strong'
            })

    # ===== 酒田戰法：三山/三川（需要更多K線）=====
    if i >= 9:
        recent_high = max(h[i-9:i])
        recent_low = min(l[i-9:i])
        curr_price = c[i]

        # 三山頂（頭肩頂概念）
        highs = h[i-9:i]
        if (highs[2] >= highs[0] * 0.98 and highs[6] >= highs[0] * 0.98 and
            highs[4] < highs[2] * 0.97 and curr_price < recent_high * 0.97):
            patterns.append({
                'name': '三山頂（酒田）',
                'type': 'bearish',
                'desc': '酒田戰法：三次到達高點後無法突破，頂部確認，建議賣出或停損',
                'strength': 'strong'
            })

        # 三川底
        lows = l[i-9:i]
        if (lows[2] <= lows[0] * 1.02 and lows[6] <= lows[0] * 1.02 and
            lows[4] > lows[2] * 1.03 and curr_price > recent_low * 1.03):
            patterns.append({
                'name': '三川底（酒田）',
                'type': 'bullish',
                'desc': '酒田戰法：三次到達低點後止跌，底部確認，建議買進或加碼',
                'strength': 'strong'
            })

    return patterns

def get_pattern_summary(patterns):
    if not patterns:
        return '無明顯K線型態', 'neutral'

    bullish = [p for p in patterns if p['type'] == 'bullish']
    bearish = [p for p in patterns if p['type'] == 'bearish']
    strong_bullish = [p for p in bullish if p['strength'] == 'strong']
    strong_bearish = [p for p in bearish if p['strength'] == 'strong']

    if strong_bearish:
        return f'強烈賣出訊號：{strong_bearish[0]["name"]}', 'bearish'
    elif strong_bullish:
        return f'強烈買進訊號：{strong_bullish[0]["name"]}', 'bullish'
    elif bearish:
        return f'偏空訊號：{bearish[0]["name"]}', 'bearish'
    elif bullish:
        return f'偏多訊號：{bullish[0]["name"]}', 'bullish'
    else:
        return '市場猶豫觀望', 'neutral'