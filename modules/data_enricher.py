"""
data_enricher.py
為 Phase 2 新增的資料擴充層：週K、月K、MACD、MA、成交量(張)
不修改舊 data_fetcher.py，保持 main.py 現有流程不受影響
"""
import requests
import pandas as pd
from datetime import datetime


def _patch_missing_close(df):
    """Bug5：Yahoo 偶爾對某日漏回 Close，整列 dropna 會少一根 K 棒。
    若 Close 缺但 High/Low 在，用當日 (High+Low)/2 補；High/Low 也缺才 drop。"""
    mask = df['Close'].isna() & df['High'].notna() & df['Low'].notna()
    df.loc[mask, 'Close'] = (df.loc[mask, 'High'] + df.loc[mask, 'Low']) / 2
    return df.dropna(subset=['Close'])


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
        return _patch_missing_close(df)
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


def _hl_trend(bars: list) -> str:
    """3 根 K 棒的高低點趨勢 → 升 / 跌 / 轉折 / 橫。bars 由舊到新。"""
    if not bars or len(bars) < 3:
        return '資料不足'
    h = [float(b['high']) for b in bars]
    l = [float(b['low']) for b in bars]
    highs_up = h[2] >= h[1] >= h[0]
    highs_dn = h[2] <= h[1] <= h[0]
    lows_up  = l[2] >= l[1] >= l[0]
    lows_dn  = l[2] <= l[1] <= l[0]
    if highs_up and lows_up:
        return '升'
    if highs_dn and lows_dn:
        return '跌'
    if highs_up or highs_dn or lows_up or lows_dn:
        return '轉折'
    return '橫'


def _consecutive_bear(bars: list) -> int:
    """從最新一根往回數，連續收陰（close<open）的根數。"""
    cnt = 0
    for b in reversed(bars):
        if float(b['close']) < float(b['open']):
            cnt += 1
        else:
            break
    return cnt


def _structure_flag(monthly_structure: str, price_vs_ma60: str,
                    consecutive_bear: int) -> str:
    """綜合三項 → 結構旗標。判定順序：已轉弱 > 未轉弱 > 轉折中。"""
    if monthly_structure == '資料不足':
        return '資料不足'
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    if (price_vs_ma60 == '在上' and monthly_structure in ('升', '橫')
            and consecutive_bear <= 1):
        return '結構未轉弱'
    return '結構轉折中'


def compute_monthly_structure(monthly_bars: list, weekly_bars: list,
                              price, ma60) -> dict:
    """從 12 月K + 26 週K + MA60 算出【月線結構客觀事實】。

    spec: docs/superpowers/specs/2026-05-21-wyckoff-phase-gate-design.md
    月K/週K 的最後一根視為進行中，結構一律用其前 3 根已收盤 bar。
    """
    result = {
        'monthly_structure':       '資料不足',
        'consecutive_bear_months': 0,
        'drawdown_from_peak':      None,
        'price_vs_ma60':           '未知',
        'structure_flag':          '資料不足',
        'weekly_momentum':         '資料不足',
        'weekly_hold_support':     False,
    }

    # 月K：需 >= 4 根（3 已收盤 + 1 進行中）
    if monthly_bars and len(monthly_bars) >= 4:
        completed = monthly_bars[:-1]
        result['monthly_structure']       = _hl_trend(completed[-3:])
        result['consecutive_bear_months'] = _consecutive_bear(completed)
        closes = [float(b['close']) for b in completed]
        peak = max(closes) if closes else 0
        if peak > 0 and price is not None:
            result['drawdown_from_peak'] = round((peak - float(price)) / peak * 100, 1)

    # 現價 vs 季線 MA60
    if price is not None and ma60:
        result['price_vs_ma60'] = '在上' if float(price) >= float(ma60) else '在下'

    # 週K 動能（唯讀）
    if weekly_bars and len(weekly_bars) >= 4:
        wcompleted = weekly_bars[:-1]
        w3 = wcompleted[-3:]
        result['weekly_momentum'] = _hl_trend(w3)
        wc = [float(b['close']) for b in w3]
        if len(wc) == 3 and min(wc) > 0:
            dispersion = (max(wc) - min(wc)) / (sum(wc) / 3)
            result['weekly_hold_support'] = bool(
                dispersion < 0.03 and wc[2] >= wc[1] and wc[2] >= wc[0]
            )

    result['structure_flag'] = _structure_flag(
        result['monthly_structure'],
        result['price_vs_ma60'],
        result['consecutive_bear_months'],
    )
    return result


def _normalize_symbol(symbol: str) -> str:
    """純數字代號自動補 .TW（台股）"""
    s = symbol.strip().upper()
    if s.isdigit():
        return s + '.TW'
    return s


_two_symbol_cache: dict[str, str] = {}

def _resolve_tw_symbol(symbol: str) -> str:
    """
    若 .TW 無法取得日K資料（上櫃股票），自動改用 .TWO。
    結果會 cache 避免重複探測。
    """
    if symbol in _two_symbol_cache:
        return _two_symbol_cache[symbol]
    if not symbol.endswith('.TW'):
        return symbol
    # 快速探測：只抓 5 天確認是否有效
    probe = _yahoo_ohlcv(symbol, '1d', '5d')
    if probe is not None and len(probe) >= 1:
        _two_symbol_cache[symbol] = symbol
        return symbol
    alt = symbol[:-3] + '.TWO'
    probe2 = _yahoo_ohlcv(alt, '1d', '5d')
    resolved = alt if (probe2 is not None and len(probe2) >= 1) else symbol
    _two_symbol_cache[symbol] = resolved
    print(f"[data_enricher] symbol resolve: {symbol} → {resolved}")
    return resolved


_tw_name_cache: dict[str, str] = {}

def _get_tw_chinese_name(code: str) -> str | None:
    """查 TWSE stockSearch → TWSE 月資料 title，回傳繁體中文名稱"""
    if code in _tw_name_cache:
        return _tw_name_cache[code]

    def _is_chinese(s: str) -> bool:
        return bool(s) and any(ord(c) > 127 for c in s)

    # 1. TWSE / TPEX 搜尋 API
    try:
        r = requests.get(
            'https://www.twse.com.tw/rwd/zh/api/stockSearch',
            params={'keyword': code, 'type': 'stock'},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=6
        )
        data = r.json()
        items = data if isinstance(data, list) else data.get('msgArray', [])
        for item in items:
            name = item.get('Name') or item.get('name') or item.get('stockName') or ''
            if _is_chinese(name):
                _tw_name_cache[code] = name
                return name
    except Exception:
        pass

    # 2. TWSE 月成交資料（title 欄位含中文名稱）
    try:
        from datetime import datetime as _dt
        date_str = _dt.now().strftime('%Y%m01')
        r = requests.get(
            'https://www.twse.com.tw/exchangeReport/STOCK_DAY',
            params={'response': 'json', 'date': date_str, 'stockNo': code},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=8
        )
        parts = r.json().get('title', '').split()
        if len(parts) >= 2 and _is_chinese(parts[1]):
            _tw_name_cache[code] = parts[1]
            return parts[1]
    except Exception:
        pass

    return None


def get_stock_info(symbol: str) -> dict | None:
    """快速查詢股票名稱與現價（不抓 OHLCV，省時間）"""
    from modules.stock_names import STOCK_NAMES
    symbol = _resolve_tw_symbol(_normalize_symbol(symbol))
    base = symbol.replace('.TWO', '').replace('.TW', '')  # 先剝 .TWO，避免 .replace('.TW') 把 .TWO 中的 .TW 吃掉只留 'O'
    try:
        r = requests.get(
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
            headers={'User-Agent': 'Mozilla/5.0'},
            params={'interval': '1d', 'range': '1d'},
            timeout=8
        )
        meta = r.json()['chart']['result'][0]['meta']
        yahoo_name = meta.get('longName') or meta.get('shortName') or ''
        # 優先：本地對照表 → TWSE/TPEX → Yahoo（通常英文，最後手段）
        name = STOCK_NAMES.get(base) or _get_tw_chinese_name(base) or yahoo_name
        return {
            'symbol': symbol,
            'name':   name,
            'price':  meta.get('regularMarketPrice'),
        }
    except Exception:
        name = STOCK_NAMES.get(base) or _get_tw_chinese_name(base) or ''
        return {'symbol': symbol, 'name': name, 'price': None} if name else None


def get_stock_quote(symbol: str) -> dict | None:
    """輕量行情：最近 ~30 日 K，回傳即時 OHLC + 20 根 spark_bars 給看板畫迷你日 K"""
    symbol = _resolve_tw_symbol(symbol)
    daily = _yahoo_ohlcv(symbol, '1d', '30d')
    if daily is None or len(daily) < 1:
        return None
    last = daily.iloc[-1]
    prev = daily.iloc[-2] if len(daily) >= 2 else None
    spark = daily.tail(20)
    return {
        'symbol':     symbol,
        'open':       round(float(last['Open']),  2),
        'high':       round(float(last['High']),  2),
        'low':        round(float(last['Low']),   2),
        'close':      round(float(last['Close']), 2),
        'prev_close': round(float(prev['Close']), 2) if prev is not None else None,
        'spark_bars': [
            {
                'o': round(float(r['Open']),  2),
                'h': round(float(r['High']),  2),
                'l': round(float(r['Low']),   2),
                'c': round(float(r['Close']), 2),
            }
            for _, r in spark.iterrows()
        ],
    }


def get_full_stock_data(symbol: str) -> dict | None:
    """
    回傳一支台股的完整分析資料：
    - daily:   最近 60 日 OHLCV + MA5/20/60 + MACD + 成交量(張)
    - weekly:  最近 26 週 OHLCV
    - monthly: 最近 12 月 OHLCV
    """
    symbol  = _resolve_tw_symbol(symbol)
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
