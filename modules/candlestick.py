import pandas as pd
import numpy as np

_MULTI_CANDLE = {
    '多頭吞噬': 2, '空頭吞噬': 2, '烏雲蓋頂': 2, '曙光初現': 2,
    '平頭頂': 2, '平頭底': 2,
    '早晨之星': 3, '黃昏之星': 3, '三白兵': 3, '三黑鴉': 3,
    '三空上升（酒田）': 3, '三空下降（酒田）': 3,
    '上升三法（酒田）': 5, '下降三法（酒田）': 5,
    '三山頂（酒田）': 40, '三川底（酒田）': 40,
}


def _twse_tick_size(price: float) -> float:
    """TWSE 申報價格升降單位（依股價區間決定最小變動單位）。
    用於平頭頂/底「同高」判定 — 兩根高點差 < 1 tick 才算同 tick 等高。
    """
    p = abs(float(price))
    if p < 10:    return 0.01
    if p < 50:    return 0.05
    if p < 100:   return 0.1
    if p < 500:   return 0.5
    if p < 1000:  return 1.0
    return 5.0


def _find_local_peaks(arr, min_gap: int = 3) -> list:
    """局部高點：左右各 min_gap 根都嚴格不超過它才算真實峰頂"""
    peaks = []
    n = len(arr)
    for k in range(min_gap, n - min_gap):
        if (arr[k] > max(arr[k - min_gap:k]) and
                arr[k] > max(arr[k + 1:k + min_gap + 1])):
            peaks.append((k, arr[k]))
    return peaks


def _find_local_troughs(arr, min_gap: int = 3) -> list:
    """局部低點：左右各 min_gap 根都嚴格不低於它才算真實谷底"""
    troughs = []
    n = len(arr)
    for k in range(min_gap, n - min_gap):
        if (arr[k] < min(arr[k - min_gap:k]) and
                arr[k] < min(arr[k + 1:k + min_gap + 1])):
            troughs.append((k, arr[k]))
    return troughs


def calc_swing_levels(bars: list, direction: str,
                       current_price: float = None) -> dict | None:
    """波段操作錨點（程式計算，AI 禁改）— spec 2026-05-19。

    取最後 60 根日K（不足 60 用全部，<20 回 None）的真實局部峰谷，
    取窗口內『最近一個』局部峰=波段高、最近一個局部谷=波段低。
    波段高低點僅在新局部峰谷形成時才變（=失效事件本身），故價格未
    觸及失效線時每日重跑錨點不動 → 論點不漂移（根治翻來覆去）。

    回傳 dict（資料不足回 None）：
      long :  invalidation=波段低  add_trigger=波段高  entry_zone=(波段低, mid)
      short:  invalidation=波段高  add_trigger=波段低  entry_zone=(mid, 波段高)
      neutral: range_low/range_high + flip_long(=波段高)/flip_short(=波段低)
      target: long/short 串 calc_pnf_target 對應方向；neutral=None
    """
    if direction not in ('long', 'short', 'neutral'):
        return None
    if not bars or len(bars) < 20:
        return None
    try:
        window = bars[-60:]
        highs = [float(b['high']) for b in window]
        lows  = [float(b['low'])  for b in window]
        peaks   = _find_local_peaks(highs, min_gap=3)
        troughs = _find_local_troughs(lows, min_gap=3)
        if not peaks or not troughs:
            return None
        swing_high = peaks[-1][1]      # 最近一個局部峰
        swing_low  = troughs[-1][1]    # 最近一個局部谷
        if swing_high <= swing_low:
            return None
        mid = (swing_low + swing_high) / 2.0

        if direction == 'neutral':
            return {
                'direction':   'neutral',
                'range_low':   swing_low,
                'range_high':  swing_high,
                'flip_long':   swing_high,
                'flip_short':  swing_low,
                'invalidation': None,
                'add_trigger':  None,
                'entry_zone':   None,
                'target':       None,
            }

        target = calc_pnf_target(bars, lookback=20,
                                 current_price=current_price,
                                 direction=direction)
        if direction == 'long':
            return {
                'direction':    'long',
                'range_low':    swing_low,
                'range_high':   swing_high,
                'invalidation': swing_low,
                'add_trigger':  swing_high,
                'entry_zone':   (swing_low, mid),
                'flip_long':    None,
                'flip_short':   None,
                'target':       target,
            }
        # short（long 幾何鏡像）
        return {
            'direction':    'short',
            'range_low':    swing_low,
            'range_high':   swing_high,
            'invalidation': swing_high,
            'add_trigger':  swing_low,
            'entry_zone':   (mid, swing_high),
            'flip_long':    None,
            'flip_short':   None,
            'target':       target,
        }
    except (KeyError, TypeError, ValueError, IndexError) as e:
        print(f'[candlestick] calc_swing_levels 失敗: {e}')
        return None


def detect_patterns(hist):
    """偵測K線型態，回傳發現的型態清單（酒田五法強化版）"""
    if len(hist) < 5:
        return []

    patterns = []
    o = hist['Open'].values
    h = hist['High'].values
    l = hist['Low'].values
    c = hist['Close'].values
    v = hist['Volume'].values

    i = len(c) - 1  # 最新一根

    body = abs(c[i] - o[i])
    total = h[i] - l[i]
    upper_shadow = h[i] - max(c[i], o[i])
    lower_shadow = min(c[i], o[i]) - l[i]

    if total == 0:
        return []

    body_ratio = body / total

    # 是否為跳空（與前一日比較）
    gap_up   = (i >= 1) and (l[i] > h[i-1])   # 今日最低 > 昨日最高
    gap_down = (i >= 1) and (h[i] < l[i-1])   # 今日最高 < 昨日最低

    # ===== 跳空型態（優先判斷）=====
    if gap_up:
        if c[i] >= o[i]:
            patterns.append({
                'name': '跳空大漲',
                'type': 'bullish',
                'desc': f'今日開盤跳空高開，多方氣勢強勁，缺口支撐在 {round(l[i],1)} 元，趨勢向上確認',
                'strength': 'strong'
            })
        else:
            patterns.append({
                'name': '跳空高開拉回',
                'type': 'neutral',
                'desc': f'今日跳空高開後收低，多方動能減弱，需觀察缺口 {round(l[i],1)}-{round(h[i-1],1)} 能否守住',
                'strength': 'medium'
            })

    if gap_down:
        if c[i] <= o[i]:
            patterns.append({
                'name': '跳空大跌',
                'type': 'bearish',
                'desc': f'今日開盤跳空低開，空方氣勢強勁，缺口壓力在 {round(h[i],1)} 元，趨勢向下確認',
                'strength': 'strong'
            })
        else:
            patterns.append({
                'name': '跳空低開反彈',
                'type': 'neutral',
                'desc': f'今日跳空低開後收高，多方逢低買進，需觀察缺口 {round(l[i-1],1)}-{round(h[i],1)} 能否補回',
                'strength': 'medium'
            })

    # ===== 單K線型態 =====

    # 錘子線（底部反轉看多）- 只在陽線出現
    if (not gap_up and not gap_down and
        lower_shadow > body * 2 and
        upper_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] > o[i]):
        patterns.append({
            'name': '錘子線',
            'type': 'bullish',
            'desc': '下影線很長，代表空方打壓後多方反攻，底部反轉訊號，可考慮買進',
            'strength': 'medium'
        })

    # 吊人線（頂部反轉看空）- 陰線出現在高位的長下影線
    if (not gap_up and not gap_down and
        lower_shadow > body * 2 and
        upper_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] < o[i]):
        patterns.append({
            'name': '吊人線',
            'type': 'bearish',
            'desc': '高位出現長下影線陰線，雖然下方有支撐但最終收黑，頂部警示訊號',
            'strength': 'medium'
        })

    # 射擊之星（頂部反轉看空）- 只在陰線出現，上影線長
    if (not gap_up and not gap_down and
        upper_shadow > body * 2 and
        lower_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] < o[i]):
        patterns.append({
            'name': '射擊之星',
            'type': 'bearish',
            'desc': '高點出現長上影線陰線，多方拉高後被空方壓回，頂部反轉訊號，注意賣出',
            'strength': 'medium'
        })

    # 倒錘子線（底部反轉看多）- 只在陽線出現，上影線長
    if (not gap_up and not gap_down and
        upper_shadow > body * 2 and
        lower_shadow < body * 0.3 and
        body_ratio > 0.1 and
        c[i] > o[i]):
        patterns.append({
            'name': '倒錘子線',
            'type': 'bullish',
            'desc': '底部出現長上影線陽線，多方嘗試反攻並守住收盤，需隔日確認',
            'strength': 'weak'
        })

    # 墓碑十字（強烈頂部訊號）
    if (not gap_up and not gap_down and
        upper_shadow > total * 0.7 and
        lower_shadow < total * 0.05 and
        body_ratio < 0.1):
        patterns.append({
            'name': '墓碑十字',
            'type': 'bearish',
            'desc': '開收盤幾乎在低點，上方長影線代表多方完全潰敗，強烈賣出訊號',
            'strength': 'strong'
        })

    # 蜻蜓十字（強烈底部訊號）：開收盤在高點，長下影線，無上影線
    if (not gap_up and not gap_down and
        body_ratio < 0.1 and
        lower_shadow > total * 0.6 and
        upper_shadow < total * 0.1):
        patterns.append({
            'name': '蜻蜓十字',
            'type': 'bullish',
            'desc': '酒田戰法：開收盤幾乎在最高點，下影線極長，空方打壓後多方完全收復，底部強烈反轉訊號',
            'strength': 'strong'
        })

    # 長腳十字（強烈不確定）：上下影線均長，多空激烈爭鬥
    if (not gap_up and not gap_down and
        body_ratio < 0.1 and
        upper_shadow > total * 0.3 and
        lower_shadow > total * 0.3):
        patterns.append({
            'name': '長腳十字',
            'type': 'neutral',
            'desc': '上下影線均長，多空激烈爭鬥後平手，市場方向高度不確定，需下一根確認',
            'strength': 'medium'
        })

    # 十字星（市場猶豫）- 排除墓碑十字、蜻蜓十字、長腳十字
    if (not gap_up and not gap_down and
        body_ratio < 0.1 and total > 0 and
        upper_shadow <= total * 0.7 and
        not (lower_shadow > total * 0.6 and upper_shadow < total * 0.1) and
        not (upper_shadow > total * 0.3 and lower_shadow > total * 0.3)):
        patterns.append({
            'name': '十字星',
            'type': 'neutral',
            'desc': '開收盤幾乎相同，市場多空力道相當，方向待確認，需觀察下一根K線',
            'strength': 'weak'
        })

    # 大陽線（強勢多頭）- 非跳空才顯示
    if (not gap_up and not gap_down and
        c[i] > o[i] and body_ratio > 0.7):
        patterns.append({
            'name': '大陽線',
            'type': 'bullish',
            'desc': '實體很長的紅K，無跳空缺口，多方持續力道強勁，趨勢向上確認訊號',
            'strength': 'medium'
        })

    # 大陰線（強勢空頭）- 非跳空才顯示
    if (not gap_up and not gap_down and
        c[i] < o[i] and body_ratio > 0.7):
        patterns.append({
            'name': '大陰線',
            'type': 'bearish',
            'desc': '實體很長的黑K，無跳空缺口，空方持續力道強勁，趨勢向下確認訊號',
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

        # 平頭頂（頂部壓力確認）：連兩根最高點同 tick + 前陽後陰
        # 容差改為 TWSE 申報單位（< 1 tick = 同 tick 等高），避免高價股 1 元誤判
        if (c1 > o1 and c0 < o0 and
                abs(h0 - h1) < _twse_tick_size(h1)):
            patterns.append({
                'name': '平頭頂',
                'type': 'bearish',
                'desc': '酒田戰法：連兩根最高點同 tick，多方兩次衝高均受壓回落，頂部壓力確認，注意轉折',
                'strength': 'medium'
            })

        # 平頭底（底部支撐確認）：連兩根最低點同 tick + 前陰後陽
        if (c1 < o1 and c0 > o0 and
                abs(l0 - l1) < _twse_tick_size(l1)):
            patterns.append({
                'name': '平頭底',
                'type': 'bullish',
                'desc': '酒田戰法：連兩根最低點同 tick，空方兩次打壓均被守住，底部支撐確認，可考慮布局',
                'strength': 'medium'
            })

    # ===== 三K線型態 =====
    if i >= 2:
        # 三白兵（酒田正規）：連三陽線 + 每根開盤在前根實體內（不跳空） + 上影線短（三根均檢查）
        if (c[i-2] > o[i-2] and c[i-1] > o[i-1] and c[i] > o[i] and
                c[i-1] > c[i-2] and c[i] > c[i-1] and
                o[i-1] >= o[i-2] and o[i-1] <= c[i-2] and
                o[i]   >= o[i-1] and o[i]   <= c[i-1] and
                (h[i-2] - c[i-2]) <= abs(c[i-2] - o[i-2]) * 0.3 and
                (h[i-1] - c[i-1]) <= abs(c[i-1] - o[i-1]) * 0.3 and
                (h[i]   - c[i])   <= abs(c[i]   - o[i])   * 0.3):
            patterns.append({
                'name': '三白兵',
                'type': 'bullish',
                'desc': '酒田戰法：連三根陽線穩步上攻，每根開盤收斂於前根實體內，無頭部阻力，多方意志堅定，強烈買進訊號',
                'strength': 'strong'
            })

        # 三黑鴉（酒田正規）：連三陰線 + 每根開盤在前根實體內（不跳空） + 下影線短（三根均檢查）
        if (c[i-2] < o[i-2] and c[i-1] < o[i-1] and c[i] < o[i] and
                c[i-1] < c[i-2] and c[i] < c[i-1] and
                o[i-1] <= o[i-2] and o[i-1] >= c[i-2] and
                o[i]   <= o[i-1] and o[i]   >= c[i-1] and
                (c[i-2] - l[i-2]) <= abs(c[i-2] - o[i-2]) * 0.3 and
                (c[i-1] - l[i-1]) <= abs(c[i-1] - o[i-1]) * 0.3 and
                (c[i]   - l[i])   <= abs(c[i]   - o[i])   * 0.3):
            patterns.append({
                'name': '三黑鴉',
                'type': 'bearish',
                'desc': '酒田戰法：連三根陰線穩步下跌，每根開盤收斂於前根實體內，無底部支撐，空方意志堅定，強烈賣出訊號',
                'strength': 'strong'
            })

        # 早晨之星（底部反轉）：第一根需為大陰線（實體 > 50% 振幅），第三根需大陽線
        if (c[i-2] < o[i-2] and
            abs(c[i-2] - o[i-2]) / max(h[i-2] - l[i-2], 1e-9) > 0.5 and
            abs(c[i-1] - o[i-1]) < (h[i-1] - l[i-1]) * 0.3 and
            c[i] > o[i] and
            abs(c[i] - o[i]) / max(h[i] - l[i], 1e-9) > 0.5 and
            c[i] > (o[i-2] + c[i-2]) / 2):
            patterns.append({
                'name': '早晨之星',
                'type': 'bullish',
                'desc': '酒田戰法：陰線+小實體+大陽線，底部強烈反轉訊號，適合買進',
                'strength': 'strong'
            })

        # 黃昏之星（頂部反轉）：第一根需為大陽線（實體 > 50% 振幅），第三根需大陰線
        if (c[i-2] > o[i-2] and
            abs(c[i-2] - o[i-2]) / max(h[i-2] - l[i-2], 1e-9) > 0.5 and
            abs(c[i-1] - o[i-1]) < (h[i-1] - l[i-1]) * 0.3 and
            c[i] < o[i] and
            abs(c[i] - o[i]) / max(h[i] - l[i], 1e-9) > 0.5 and
            c[i] < (o[i-2] + c[i-2]) / 2):
            patterns.append({
                'name': '黃昏之星',
                'type': 'bearish',
                'desc': '酒田戰法：陽線+小實體+大陰線，頂部強烈反轉訊號，適合賣出',
                'strength': 'strong'
            })

    # ===== 酒田戰法：三空 =====
    if i >= 3:
        # 三空上升：連三根跳空上漲 → 追漲已竭，逢高賣出
        if all(l[j] > h[j - 1] for j in [i - 2, i - 1, i]):
            patterns.append({
                'name': '三空上升（酒田）',
                'type': 'bearish',
                'desc': '酒田戰法：連續三根跳空上漲，追漲力道過度，缺口遲早回補，逢高宜減碼',
                'strength': 'strong'
            })
        # 三空下降：連三根跳空下跌 → 恐慌已竭，逢低買進
        if all(h[j] < l[j - 1] for j in [i - 2, i - 1, i]):
            patterns.append({
                'name': '三空下降（酒田）',
                'type': 'bullish',
                'desc': '酒田戰法：連續三根跳空下跌，恐慌殺盤過度，缺口遲早回補，逢低可留意',
                'strength': 'strong'
            })

    # ===== 酒田戰法：三法（趨勢持續確認）=====
    if i >= 4:
        # 上升三法：大陽線 → 3根小K棒整理在範圍內 → 大陽線突破
        first_bull = c[i-4] - o[i-4]
        if (first_bull > 0 and
                first_bull / max(h[i-4] - l[i-4], 1e-9) > 0.5 and
                all(l[j] >= l[i-4] and h[j] <= h[i-4] for j in range(i-3, i)) and
                c[i] > o[i] and c[i] > c[i-4] and
                (c[i] - o[i]) / max(h[i] - l[i], 1e-9) > 0.5):
            patterns.append({
                'name': '上升三法（酒田）',
                'type': 'bullish',
                'desc': '酒田戰法：大陽線後小幅回調整理，再以大陽線突破前高，多頭趨勢確認，可持股或加碼',
                'strength': 'strong'
            })

        # 下降三法：大陰線 → 3根小K棒整理在範圍內 → 大陰線跌破
        first_bear = o[i-4] - c[i-4]
        if (first_bear > 0 and
                first_bear / max(h[i-4] - l[i-4], 1e-9) > 0.5 and
                all(l[j] >= l[i-4] and h[j] <= h[i-4] for j in range(i-3, i)) and
                c[i] < o[i] and c[i] < c[i-4] and
                (o[i] - c[i]) / max(h[i] - l[i], 1e-9) > 0.5):
            patterns.append({
                'name': '下降三法（酒田）',
                'type': 'bearish',
                'desc': '酒田戰法：大陰線後小幅反彈整理，再以大陰線跌破前低，空頭趨勢確認，可出清或觀望',
                'strength': 'strong'
            })

    # ===== 酒田戰法：三山/三川（真實局部高低點偵測，40根窗口）=====
    if i >= 19:
        win_start = max(0, i - 39)
        h_win = h[win_start:i + 1]
        l_win = l[win_start:i + 1]

        # 三山頂：3個局部高點在相近水平（±3%），最後峰值在近15根內（避免舊高點每日重複觸發），且當前價格已從高點回落
        raw_peaks = _find_local_peaks(h_win, min_gap=3)
        spaced_peaks: list = []
        for pk in raw_peaks:
            if not spaced_peaks or pk[0] - spaced_peaks[-1][0] >= 5:
                spaced_peaks.append(pk)
        if len(spaced_peaks) >= 3:
            p1_h, p2_h, p3_h = (spaced_peaks[-3][1],
                                 spaced_peaks[-2][1],
                                 spaced_peaks[-1][1])
            avg_h = (p1_h + p2_h + p3_h) / 3
            bars_since_peak = (len(h_win) - 1) - spaced_peaks[-1][0]
            if (bars_since_peak <= 15 and
                    all(abs(px - avg_h) / avg_h <= 0.03 for px in (p1_h, p2_h, p3_h)) and
                    c[i] < avg_h * 0.97):
                patterns.append({
                    'name': '三山頂（酒田）',
                    'type': 'bearish',
                    'desc': f'酒田戰法：三次攻頂 {round(avg_h, 1)} 元均受壓回落，頂部確認，建議賣出或停損',
                    'strength': 'strong'
                })

        # 三川底：3個局部低點在相近水平（±3%），最後谷底在近15根內（避免舊低點每日重複觸發），且當前價格已從低點反彈
        raw_troughs = _find_local_troughs(l_win, min_gap=3)
        spaced_troughs: list = []
        for tr in raw_troughs:
            if not spaced_troughs or tr[0] - spaced_troughs[-1][0] >= 5:
                spaced_troughs.append(tr)
        if len(spaced_troughs) >= 3:
            t1_l, t2_l, t3_l = (spaced_troughs[-3][1],
                                 spaced_troughs[-2][1],
                                 spaced_troughs[-1][1])
            avg_l = (t1_l + t2_l + t3_l) / 3
            bars_since_trough = (len(l_win) - 1) - spaced_troughs[-1][0]
            if (bars_since_trough <= 15 and
                    all(abs(tx - avg_l) / avg_l <= 0.03 for tx in (t1_l, t2_l, t3_l)) and
                    c[i] > avg_l * 1.03):
                patterns.append({
                    'name': '三川底（酒田）',
                    'type': 'bullish',
                    'desc': f'酒田戰法：三次探底 {round(avg_l, 1)} 元均獲支撐反彈，底部確認，建議買進或加碼',
                    'strength': 'strong'
                })

    for p in patterns:
        p['candle_count'] = _MULTI_CANDLE.get(p['name'], 1)
    return patterns


def detect_from_bars(daily_bars: list) -> list:
    """將 data_enricher 格式的 daily_bars 轉換後呼叫 detect_patterns()"""
    if not daily_bars or len(daily_bars) < 5:
        return []
    try:
        df = pd.DataFrame([{
            'Open':   float(b['open']),
            'High':   float(b['high']),
            'Low':    float(b['low']),
            'Close':  float(b['close']),
            'Volume': float(b.get('volume_zhang', 0)),
        } for b in daily_bars])
        return detect_patterns(df)
    except Exception as e:
        print(f'[candlestick] detect_from_bars 失敗: {e}')
        return []


def _fallback_label(bar: dict) -> str:
    """無型態時的 fallback 標籤：陽/陰線(體型%) / 平盤。"""
    o = float(bar['open'])
    c = float(bar['close'])
    h = float(bar['high'])
    lv = float(bar['low'])
    total = h - lv
    if total <= 0:
        return '平盤'
    br = abs(c - o) / total
    if c > o:
        return f'陽線({br:.0%})'
    if c < o:
        return f'陰線({br:.0%})'
    return '平盤'


def label_bars(bars: list, timeframe: str = 'daily') -> dict:
    """
    為 bars 中每根 K 棒計算型態標籤，回傳 {date: 型態名稱} dict。
    供 _fmt_bars() 使用，讓 AI 不需自行命名型態。
    bars 需與 data_enricher 的 daily_bars / weekly_bars / monthly_bars 同格式。

    timeframe='monthly' 時排除「3+ 根組合型態」（早晨之星/黃昏之星/三白兵
    /三黑鴉/三川底/三山頂/三空/三法）— 月 K 一根=一個月，3 根組合在月線
    語境上構不成型態（語意不通）。

    D1 去重：當某根標到 `_MULTI_CANDLE[name] >= 3` 的多根組合型態時，若該
    型態在前 `_MULTI_CANDLE[name]` 根內已標過，當前根 fallback 為陽/陰線
    型態 — 避免撼訊「三川底連 3 天觸發」這種「整體型態被重複貼到每根」。
    """
    if not bars or len(bars) < 5:
        return {}
    result = {}
    label_history: list = []  # 平行 list，順序與 bars[4:] 對齊
    try:
        df = pd.DataFrame([{
            'Open':   float(b['open']),
            'High':   float(b['high']),
            'Low':    float(b['low']),
            'Close':  float(b['close']),
            'Volume': float(b.get('volume_zhang', 0)),
        } for b in bars])
        for i in range(4, len(df)):
            patterns = detect_patterns(df.iloc[:i + 1].copy())
            date = bars[i]['date']

            # D3：monthly 時過濾 3+ 根組合型態（語意上月線不適用）
            if timeframe == 'monthly':
                patterns = [p for p in patterns
                            if _MULTI_CANDLE.get(p['name'], 0) < 3]

            chosen_name = None
            if patterns:
                strong = [p for p in patterns if p['strength'] == 'strong']
                chosen = strong[0] if strong else patterns[0]
                chosen_name = chosen['name']

                # D1 去重：3+ 根組合型態在前 N 根已標過 → fallback
                span = _MULTI_CANDLE.get(chosen_name, 0)
                if span >= 3 and chosen_name in label_history[-span:]:
                    chosen_name = None  # 觸發 fallback

            if chosen_name:
                result[date] = chosen_name
                label_history.append(chosen_name)
            else:
                result[date] = _fallback_label(bars[i])
                label_history.append(None)
    except Exception as e:
        print(f'[candlestick] label_bars 失敗: {e}')
    return result


def calc_pnf_target(bars: list, lookback: int = 12,
                    current_price: float = None,
                    direction: str = 'long') -> float | None:
    """Darvas 箱體突破目標（等幅量度 Measured Move）

    掃描全部 bars，找最近一個有效盤整箱體，依 direction 決定方向：

    direction='long'（預設，向後相容）— 突破箱頂向上：
      箱頂：某根 bar 的 high，後 confirm 根均未超過（阻力確認）
      箱底：箱頂後窗口內最低點，後 confirm 根均未跌破（支撐確認）
      箱寬 ≤ max_range（排除趨勢段）
      目標 = 箱頂 + (箱頂 - 箱底)，突破後鎖定不漂移
      Filter A：current_price > 箱頂 × 1.02（突破確認）
      Filter B：target > current_price × 1.02（目標仍有預測力）

    direction='short' — 跌破箱底向下（long 的幾何鏡像）：
      箱底：某根 bar 的 low，後 confirm 根均未跌破（支撐確認）
      箱頂：箱底後窗口內最高點，後 confirm 根均未超過（阻力確認）
      箱寬 ≤ max_range（同 long）
      目標 = 箱底 - (箱頂 - 箱底)，跌破後鎖定不漂移
      Filter A：current_price < 箱底 × 0.98（跌破確認）
      Filter B：target < current_price × 0.98（目標仍有預測力）

    兩方向皆：找到箱體但未突破/跌破 → 往更早箱體找，全歷史無有效箱才回 None。

    lookback 決定確認週數與箱寬閾值（不截斷掃描範圍）：
      週K (lookback ≤ 14)：confirm=2，箱寬 ≤ 20%
      日K (lookback > 14)：confirm=3，箱寬 ≤ 15%
    """
    if not bars or len(bars) < 5:
        return None
    if direction not in ('long', 'short'):
        return None
    try:
        n         = len(bars)
        confirm   = 2 if lookback <= 14 else 3
        max_range = 0.20 if lookback <= 14 else 0.15

        highs = [float(b['high']) for b in bars]
        lows  = [float(b['low'])  for b in bars]
        cur   = float(current_price) if current_price is not None else None

        # Filter C reference：用相同 _find_local_peaks/_troughs（min_gap=3，與
        # calc_swing_levels 一致）取最近一個程式版「壓力線/支撐線」作為交叉檢查
        # 基準。修撼訊 case：P&F target=74 < AI 標壓力 74.7（兩來源不一致）。
        # long  ：target 必須 > swing_high × 1.02（突破壓力之上才有預測力）
        # short ：target 必須 < swing_low  × 0.98（跌破支撐之下才有預測力）
        swing_ref = None
        if direction == 'long':
            peaks = _find_local_peaks(highs, min_gap=3)
            swing_ref = peaks[-1][1] if peaks else None
        else:
            troughs = _find_local_troughs(lows, min_gap=3)
            swing_ref = troughs[-1][1] if troughs else None

        for i in range(n - confirm - 2, 0, -1):
            if direction == 'long':
                box_top = highs[i]

                # 箱頂確認：後 confirm 根 high 均未超過
                if not all(highs[j] <= box_top
                           for j in range(i + 1, min(i + confirm + 1, n))):
                    continue

                # 箱底：箱頂後窗口內最低點（confirm+4 根搜尋範圍）
                search_end = min(i + confirm + 5, n)
                window     = lows[i:search_end]
                box_bottom = min(window)
                low_idx    = i + window.index(box_bottom)

                # 箱底確認：後 confirm 根 low 均未跌破
                if low_idx + confirm >= n:
                    continue
                if not all(lows[j] >= box_bottom
                           for j in range(low_idx + 1, min(low_idx + confirm + 1, n))):
                    continue

                # 箱寬：排除趨勢段
                if box_bottom <= 0 or (box_top - box_bottom) / box_bottom > max_range:
                    continue

                target = box_top + (box_top - box_bottom)

                # 兩道 filter 都失敗就往更早的箱體找（不再硬 return None）：
                # Filter A：箱頂尚未突破（cur ≤ box_top × 1.02）→ 該箱還在形成中，
                #          可能更早有箱體已突破且 target 仍領先 cur，繼續往回找
                # Filter B：target 已被 cur 超過（target ≤ cur × 1.02）→ 該箱目標
                #          已達成過、無預測力，繼續往回找更大/更早的有效箱體
                if cur is not None:
                    if cur <= box_top * 1.02:
                        continue
                    if target <= cur * 1.02:
                        continue
                # Filter C：target 必須突破程式版壓力之上才有預測力
                if swing_ref is not None and target <= swing_ref * 1.02:
                    continue
            else:  # short — long 的幾何鏡像（箱底支撐錨點 → 跌破向下）
                box_bottom = lows[i]

                # 箱底確認：後 confirm 根 low 均未跌破
                if not all(lows[j] >= box_bottom
                           for j in range(i + 1, min(i + confirm + 1, n))):
                    continue

                # 箱頂：箱底後窗口內最高點（confirm+4 根搜尋範圍）
                search_end = min(i + confirm + 5, n)
                window     = highs[i:search_end]
                box_top    = max(window)
                high_idx   = i + window.index(box_top)

                # 箱頂確認：後 confirm 根 high 均未超過
                if high_idx + confirm >= n:
                    continue
                if not all(highs[j] <= box_top
                           for j in range(high_idx + 1, min(high_idx + confirm + 1, n))):
                    continue

                # 箱寬：排除趨勢段（同 long）
                if box_bottom <= 0 or (box_top - box_bottom) / box_bottom > max_range:
                    continue

                target = box_bottom - (box_top - box_bottom)

                # Filter A：箱底尚未跌破（cur ≥ box_bottom × 0.98）→ 繼續往回找
                # Filter B：target 已被 cur 跌穿（target ≥ cur × 0.98）→ 無預測力，往回找
                if cur is not None:
                    if cur >= box_bottom * 0.98:
                        continue
                    if target >= cur * 0.98:
                        continue
                # Filter C：target 必須跌破程式版支撐之下才有預測力
                if swing_ref is not None and target >= swing_ref * 0.98:
                    continue

            return round(target) if target >= 100 else round(target, 1)

        return None
    except Exception as e:
        print(f'[candlestick] calc_pnf_target 失敗: {e}')
        return None


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
