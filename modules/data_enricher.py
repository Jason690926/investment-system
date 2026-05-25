"""
data_enricher.py
為 Phase 2 新增的資料擴充層：週K、月K、MACD、MA、成交量(張)
不修改舊 data_fetcher.py，保持 main.py 現有流程不受影響
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone


def _patch_missing_close(df):
    """Bug5：Yahoo 偶爾對某日漏回 Close，整列 dropna 會少一根 K 棒。
    若 Close 缺但 High/Low 在，用當日 (High+Low)/2 補；High/Low 也缺才 drop。"""
    mask = df['Close'].isna() & df['High'].notna() & df['Low'].notna()
    df.loc[mask, 'Close'] = (df.loc[mask, 'High'] + df.loc[mask, 'Low']) / 2
    return df.dropna(subset=['Close'])


def _chart_json_to_df(d: dict, interval: str) -> pd.DataFrame:
    """把 Yahoo v8 chart result dict 轉成 OHLCV DataFrame。

    Bug A（spec 2026-05-22）兩項修正：
      A1 — Yahoo 對 1wk/1mo 會在序列尾端多塞一根 spurious 即時棒
            （timestamp == meta.regularMarketTime、值＝當日日K，非期間聚合），予以剔除。
            1d 不受影響、Yahoo 未附時也不過砍。
      A2 — 用 meta.gmtoffset 把 timestamp 校正為交易所當地日期，避免 UTC 伺服器
            把週/月棒（期間起始 00:00）日期位移成前一日。
    """
    ts   = list(d['timestamp'])
    q    = d['indicators']['quote'][0]
    cols = {k: list(q[k]) for k in ('open', 'high', 'low', 'close', 'volume')}
    meta = d.get('meta', {}) or {}

    # ── A1：剔除 1wk/1mo 尾端 spurious 即時棒 ──
    if interval in ('1wk', '1mo') and len(ts) >= 2:
        rmt = meta.get('regularMarketTime')
        if rmt is not None and ts[-1] == rmt:
            ts = ts[:-1]
            cols = {k: v[:-1] for k, v in cols.items()}

    # ── A2：用 gmtoffset 校正成交易所當地日期 ──
    gmtoffset = meta.get('gmtoffset', 0) or 0
    idx = pd.to_datetime([
        (datetime.fromtimestamp(t, tz=timezone.utc)
         + timedelta(seconds=gmtoffset)).replace(tzinfo=None)
        for t in ts
    ])
    df = pd.DataFrame({
        'Open':   cols['open'],
        'High':   cols['high'],
        'Low':    cols['low'],
        'Close':  cols['close'],
        'Volume': cols['volume'],
    }, index=idx)
    df.index.name = 'Date'
    return df


def _synthesize_in_progress_bar(
    daily_df: pd.DataFrame,
    period_df: pd.DataFrame,
    freq: str,  # 'W' 或 'M'
    *,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """C1 / Bug S1+W1（2026-05-24）— 合成進行中週/月棒。

    Yahoo 1wk/1mo 的「進行中」棒被 Bug A 剔除後（或從未提供），週/月末根 close
    會 = 前一交易日日 close（少當日）。本函式用當日 daily K roll-up 合成「進行中」
    週/月棒並覆寫/append 到 period_df 尾端。

    Args:
        daily_df:  日 K DataFrame（index=Date，含 Open/High/Low/Close/Volume）
        period_df: 已抓到的週 K 或月 K DataFrame
        freq:      'W'（週）或 'M'（月）
        today:     基準日（測試覆寫用，預設 TW now）

    Returns:
        若當期內有 daily bars，回傳含合成棒的新 DataFrame；否則回傳 period_df 不變。

    合成規則：
        open   = 當期第一日 open
        high   = max(highs)
        low    = min(lows)
        close  = 最新日 close
        volume = sum(volumes)
        Date   = 當期起始日（週=週一、月=該月 1 日）
    """
    if today is None:
        today = pd.Timestamp.now(tz='Asia/Taipei').normalize().tz_localize(None)
    else:
        today = pd.Timestamp(today)

    if freq == 'W':
        period_start = today - pd.Timedelta(days=today.weekday())
    elif freq == 'M':
        period_start = today.replace(day=1)
    else:
        raise ValueError(f"freq 必須是 'W' 或 'M'，收到 {freq!r}")
    period_start = period_start.normalize()

    if daily_df is None or len(daily_df) == 0:
        return period_df

    in_period = daily_df[daily_df.index >= period_start]
    if len(in_period) == 0:
        return period_df

    synth = {
        'Open':   float(in_period['Open'].iloc[0]),
        'High':   float(in_period['High'].max()),
        'Low':    float(in_period['Low'].min()),
        'Close':  float(in_period['Close'].iloc[-1]),
        'Volume': float(in_period['Volume'].sum()),
    }
    synth_row = pd.DataFrame([synth], index=pd.DatetimeIndex([period_start], name='Date'))

    if period_df is None or len(period_df) == 0:
        return synth_row

    if period_df.index[-1] == period_start:
        out = period_df.iloc[:-1].copy()
        return pd.concat([out, synth_row])
    return pd.concat([period_df, synth_row])


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
        return _patch_missing_close(_chart_json_to_df(d, interval))
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
                    consecutive_bear: int,
                    close_strict_up_3: bool = False,
                    bull_count_6: int = 0) -> str:
    """綜合 → 結構旗標。判定順序：已轉弱 > 未轉弱（含強勢上漲否決）> 轉折中。

    強勢上漲否決（2026-05-25, plan §三十 Bug A）：即使 _hl_trend 因 lows 不
    嚴格升回「轉折」，只要 close 嚴格上揚或近 6 月陽月數 ≥ 4，仍視為結構
    未轉弱（涵蓋東捷型強勢起漲、中間有 1 月修正陰的案例）。
    """
    if monthly_structure == '資料不足':
        return '資料不足'
    if (price_vs_ma60 == '在下' or monthly_structure == '跌'
            or consecutive_bear >= 2):
        return '結構已轉弱'
    if price_vs_ma60 == '在上' and consecutive_bear <= 1 and (
        monthly_structure in ('升', '橫')
        or close_strict_up_3
        or bull_count_6 >= 4
    ):
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
        # 強勢上漲否決指標（2026-05-25, plan §三十 Bug A）
        'monthly_close_strict_up_3': False,
        'monthly_bull_count_6':      0,
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
        # 強勢上漲否決指標
        if len(completed) >= 3:
            c3 = closes[-3:]
            result['monthly_close_strict_up_3'] = (c3[0] < c3[1] < c3[2])
        result['monthly_bull_count_6'] = sum(
            1 for b in completed[-6:] if float(b['close']) > float(b['open'])
        )

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
        close_strict_up_3=result['monthly_close_strict_up_3'],
        bull_count_6=result['monthly_bull_count_6'],
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

    # C1 / Bug S1+W1：用當日 daily K roll-up 合成進行中週/月棒（覆寫/append 到尾端）
    if weekly is not None:
        weekly = _synthesize_in_progress_bar(daily, weekly, 'W')
    if monthly is not None:
        monthly = _synthesize_in_progress_bar(daily, monthly, 'M')

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
