import os
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from dotenv import load_dotenv
from modules.auth import init_auth
from modules.database import SessionLocal
from modules.stock_service import get_user_stocks, add_stock, add_trade, remove_stock, update_trade, delete_trade, reorder_stocks

from werkzeug.middleware.proxy_fix import ProxyFix
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

from modules.database import init_db
try:
    init_db()
except Exception as e:
    print(f"[DB] 啟動時初始化失敗（稍後重試）: {e}")

init_auth(app)


# ── 分析日計算（台灣時間，14:30 後才算當日收盤）─────────────
def _analysis_day_tw():
    """最近有效的分析日：14:30 後才算今日；週末/假日往回找最近工作日。"""
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    wd = now_tw.weekday()       # 0=Mon … 4=Fri 5=Sat 6=Sun
    after_close = now_tw.hour > 14 or (now_tw.hour == 14 and now_tw.minute >= 30)
    if wd < 5 and after_close:  # 平日 14:30 後 → 今天
        return now_tw.date()
    # 其他：往前找最近工作日
    day = now_tw.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


# ── /print-report 用的 helpers ──────────────────────────────
import re
import mistune

_INLINE_STYLE_RE = re.compile(
    r'\s+style\s*=\s*(?:"[^"]*"|\'[^\']*\')',
    re.IGNORECASE,
)

# AI 輸出是 markdown + HTML 混合（### 標題、- bullet、**bold** + <table>/<span>）
# escape=False 保留原 HTML（table、span class 等）；plugins=['table'] 支援 GFM 表格
_MARKDOWN = mistune.create_markdown(escape=False, plugins=['table'])


def _strip_inline_styles(html):
    """剝除 HTML 內所有 inline style 屬性。
    對既有 DB 殘留 inline style 做 render-time 第二道防禦
    （第一道在 _clean_html_output:113 已做於寫入時）。"""
    if not html:
        return ''
    return _INLINE_STYLE_RE.sub('', html)


def _markdown_to_html(content):
    """把 AI 輸出的 markdown+HTML 混合內容轉成乾淨 HTML。
    後續再過 _strip_inline_styles 防舊資料殘留。"""
    if not content:
        return ''
    return _MARKDOWN(content)


def _format_price(value):
    """價格格式依 TWSE 申報價格升降單位（tick）：
    <50 元 → 2 位小數（tick 0.01–0.05）
    50–500 元 → 1 位小數（tick 0.10–0.50）
    ≥500 元 → 整數千分位（tick 1.00–5.00）
    """
    if value is None:
        return '—'
    v = float(value)
    if v < 50:
        return f'{v:,.2f}'
    elif v < 500:
        return f'{v:,.1f}'
    else:
        return f'{v:,.0f}'


def _render_one_block(s, a, q, idx, mode, personal_html=None):
    """產出單一持股/觀察區塊 HTML。
    personal_html: A 組 2026-05-20 — PersonalRecommendation.html cache 結果，
    若用戶尚未產生個人建議則為 None（PDF 該股 personal 段 skip）。

    s: Stock 物件（symbol, name, status, avg_cost, total_zhang, trades）
    a: StockAnalysis 物件 or None
    q: QuoteCache 物件 or None
    idx: 1-based 章節內序號
    mode: 'holding' or 'watching'
    """
    status_label = 'HOLD' if mode == 'holding' else 'WATCH'

    # 標頭：股價 + 漲跌
    if q and q.close is not None and q.prev_close:
        close = float(q.close)
        prev = float(q.prev_close)
        change = close - prev
        pct = (change / prev * 100) if prev else 0
        direction = 'bull' if change >= 0 else 'bear'
        arrow = '▲' if change >= 0 else '▼'
        price_str = _format_price(close)
        change_html = (
            f'<span class="change {direction}">'
            f'{arrow} {change:+.0f} / {pct:+.1f}%'
            f'</span>'
        )
        close_date_str = (
            f'close {q.cache_date.strftime("%Y-%m-%d")}'
            if hasattr(q, 'cache_date') and q.cache_date else 'close —'
        )
    else:
        price_str = '—'
        change_html = ''
        close_date_str = 'close —'

    # 數據列（僅 holding）
    data_row_html = ''
    if mode == 'holding' and s.status == 'holding' and s.trades:
        avg_cost = float(s.avg_cost) if s.avg_cost else 0.0
        qty = float(s.total_zhang) if s.total_zhang else 0.0
        if q and q.close is not None and avg_cost > 0:
            pnl_pct = (float(q.close) - avg_cost) / avg_cost * 100
            pnl_dir = 'bull' if pnl_pct >= 0 else 'bear'
            pnl_html = f'<strong class="{pnl_dir}">{pnl_pct:+.1f}%</strong>'
        else:
            pnl_html = '<strong class="muted">—</strong>'
        risk_str = f'{a.risk_pct}%' if a and a.risk_pct is not None else '—'
        data_row_html = f"""
  <div class="data-row">
    <div><span class="label">COST</span><br><strong>{avg_cost:,.2f}</strong></div>
    <div><span class="label">QTY</span><br><strong>{qty:.1f} 張</strong></div>
    <div><span class="label">P/L</span><br>{pnl_html}</div>
    <div><span class="label">RISK</span><br><strong class="amber">{risk_str}</strong></div>
  </div>"""

    # Pills 列（B 組 2026-05-20：DB schema 中性語意 + stop_loss 獨立欄）
    # long  : 箱底=support_price / 箱頂=resistance_price / 目標=target_price
    #         （2026-05-22 Bug B：long pill 顯示程式 swing 錨點，改標「箱底/箱頂」
    #          與內文 AI 的「支撐/壓力」明確區隔，避免同字不同數誤導）
    # short : 空標=support_price（下方目標）/ 空進=resistance_price（回測壓力）/
    #         空停=stop_loss（前高之上失效，B1c）
    # neutral: 撐/壓=AI 支撐壓力（anchor 為 None → fallback AI tag，值與內文一致故留原字）
    pills = []
    if a:
        from modules.ai_analyzer_v2 import phase_to_direction
        _dir = phase_to_direction(a.wyckoff_phase)
        if _dir == 'short':
            dir_badge = '空'
            pills.append(f'<span class="pill pill-ink"><span class="lbl">方向 </span>{dir_badge}</span>')
            # 順序：空進（最先看到的進場價）/ 空停 / 空標
            if a.resistance_price is not None:
                pills.append(f'<span class="pill pill-bull"><span class="lbl">空進 </span>{_format_price(a.resistance_price)}</span>')
            stop = getattr(a, 'stop_loss', None)
            if stop is not None:
                pills.append(f'<span class="pill pill-amber"><span class="lbl">空停 </span>{_format_price(stop)}</span>')
            if a.support_price is not None:
                pills.append(f'<span class="pill pill-support"><span class="lbl">空標 </span>{_format_price(a.support_price)}</span>')
            if a.wyckoff_phase:
                pills.append(f'<span class="pill pill-ink"><span class="lbl">威科夫 </span>{a.wyckoff_phase}</span>')
        else:
            dir_badge = '多' if _dir == 'long' else '觀望'
            pills.append(f'<span class="pill pill-ink"><span class="lbl">方向 </span>{dir_badge}</span>')
            # long 用程式錨點語意「箱底/箱頂」；neutral pill 為 AI 支撐壓力故留「撐/壓」
            sup_lbl, res_lbl = ('箱底', '箱頂') if _dir == 'long' else ('撐', '壓')
            if a.support_price is not None:
                pills.append(f'<span class="pill pill-support"><span class="lbl">{sup_lbl} </span>{_format_price(a.support_price)}</span>')
            if a.resistance_price is not None:
                pills.append(f'<span class="pill pill-bull"><span class="lbl">{res_lbl} </span>{_format_price(a.resistance_price)}</span>')
            if a.target_price is not None:
                pills.append(f'<span class="pill pill-amber"><span class="lbl">目標 </span>{_format_price(a.target_price)}</span>')
            if a.wyckoff_phase:
                pills.append(f'<span class="pill pill-ink"><span class="lbl">威科夫 </span>{a.wyckoff_phase}</span>')
    # 觀察版把風險合進 pills
    if mode == 'watching' and a and a.risk_pct is not None:
        pills.append(f'<span class="pill pill-amber-outline"><span class="lbl">風險 </span>{a.risk_pct}%</span>')
    # plan §三十一：建議動作 pill（emoji 開頭判 PDF pill 配色）
    action_pill = getattr(a, 'action_pill', None) if a else None
    if action_pill:
        if action_pill.startswith('🟢'):
            _pcls = 'pill-bull'      # 進取（追進/加碼/續抱）→ 紅（台股漲色）
        elif action_pill.startswith('🟡') or action_pill.startswith('🟠'):
            _pcls = 'pill-amber'     # 等待/警戒
        elif action_pill.startswith('🔴'):
            _pcls = 'pill-support'   # 退出/論點作廢 → 綠（台股跌色）
        else:
            _pcls = 'pill-amber-outline'  # 觀望 → 中性 outline
        pills.append(f'<span class="pill {_pcls}"><span class="lbl">建議 </span>{action_pill}</span>')
    pills_html = f'<div class="pills">{"".join(pills)}</div>' if pills else ''

    # 分析內容：markdown→HTML 後再剝 inline style
    if a and a.html_content:
        rendered = _markdown_to_html(a.html_content)
        rendered = _strip_inline_styles(rendered)
        body_html = f'<div class="analysis-wrap">{rendered}</div>'
    else:
        body_html = '<div class="no-analysis">尚無分析資料</div>'

    # A 組 2026-05-20：個人建議區塊（從 PersonalRecommendation cache 注入）
    if personal_html:
        personal_clean = _strip_inline_styles(personal_html)
        personal_html_block = (
            f'<div class="personal-rec">'
            f'<div class="personal-rec-title">▍ 個人化操作建議</div>'
            f'<div class="personal-rec-body">{personal_clean}</div>'
            f'</div>'
        )
    else:
        personal_html_block = ''
    # 變數名稱與 f-string template 對齊
    personal_html = personal_html_block

    # 組裝
    return f"""
<div class="stock-block">
  <div class="stock-block-header">
    <div class="stock-ident">
      <div class="stock-name-row">
        <span class="stock-name">{s.name}</span>
        <span class="stock-symbol">{s.symbol}</span>
      </div>
      <div class="stock-price-row">
        <span class="price-num">{price_str}</span>
        {change_html}
      </div>
    </div>
    <div class="stock-meta-right">
      <div class="idx-tag">[{idx:02d} · {status_label}]</div>
      <div class="close-date">{close_date_str}</div>
    </div>
  </div>{data_row_html}
  {pills_html}
  {body_html}
  {personal_html}
</div>"""


def _render_stock_blocks(stocks, analyses, quotes, mode, personals=None):
    """A 組 2026-05-20：personals = {symbol: PersonalRecommendation.html} 從 print_report 注入。"""
    personals = personals or {}
    parts = []
    for idx, s in enumerate(stocks, start=1):
        a = analyses.get(s.symbol)
        q = quotes.get(s.symbol)
        parts.append(_render_one_block(s, a, q, idx=idx, mode=mode,
                                       personal_html=personals.get(s.symbol)))
    return ''.join(parts)


# ── 偵錯（找完問題後移除）───────────────────────���────────
@app.route('/debug-oauth')
def debug_oauth():
    from modules.auth import oauth
    redirect_uri = url_for('auth.callback', _external=True)
    auth_url = oauth.google.create_authorization_url(redirect_uri)
    return f"""
    <p>Redirect URI Flask產生: <code>{redirect_uri}</code></p>
    <p>Client ID: <code>{os.getenv('GOOGLE_CLIENT_ID','')[:30]}...</code></p>
    <p>Secret末尾: <code>...{os.getenv('GOOGLE_CLIENT_SECRET','')[-6:]}</code></p>
    """

# ── 頁面路由 ───────────────────────────────────────��──────

@app.route('/')
def index():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect('/dashboard')
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/stock/<int:stock_id>')
@login_required
def stock_detail(stock_id):
    db = SessionLocal()
    try:
        from modules.models import Stock
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return redirect('/dashboard')

        total = stock.total_zhang if stock.status == 'holding' and stock.trades else None
        avg   = float(stock.avg_cost) if stock.avg_cost else None

        class StockView:
            pass
        sv = StockView()
        sv.id          = stock.id
        sv.symbol      = stock.symbol
        sv.name        = stock.name
        sv.status      = stock.status
        sv.avg_cost    = avg
        sv.total_zhang = float(total) if total else None

        return render_template('stock.html', stock=sv)
    finally:
        db.close()


# ── 市場資料 API ──────────────────────────────────────────

# 輕量行情記憶體快取：{ 'SYMBOL_YYYY-MM-DD': {... , '_cached_at_utc': dt} }
_quote_cache: dict = {}


def _post_close_tw(now_utc=None) -> bool:
    """台股 14:30 後（含 14:30）→ True；否則 False。now_utc 注入用於測試。"""
    from datetime import datetime as _dt, timedelta as _td
    n = now_utc if now_utc is not None else _dt.utcnow()
    tw = n + _td(hours=8)
    return tw.hour > 14 or (tw.hour == 14 and tw.minute >= 30)


def _today_close_threshold_utc(now_utc=None):
    """今日 TW 14:30 對應的 UTC datetime（naive，與 QuoteCache.cached_at 同型）。"""
    from datetime import datetime as _dt, timedelta as _td
    n = now_utc if now_utc is not None else _dt.utcnow()
    today_tw = (n + _td(hours=8)).date()
    return _dt(today_tw.year, today_tw.month, today_tw.day, 6, 30, 0)


def _bars_to_spark(bars_list):
    """daily_bars list[dict] → spark_bars list[20 個 OHLC]，給前端畫迷你日 K"""
    if not bars_list:
        return []
    return [
        {'o': b['open'], 'h': b['high'], 'l': b['low'], 'c': b['close']}
        for b in bars_list[-20:]
    ]


def _strip_internal(d):
    """剝除底線開頭的內部欄位（如 _cached_at_utc），不外露給 client。"""
    return {k: v for k, v in d.items() if not k.startswith('_')}


def _upsert_quote_cache(db, symbol, today_tw, data, now_utc=None):
    """寫/覆寫 QuoteCache 一筆。失敗（含並發 IntegrityError）吃掉並 rollback。"""
    from datetime import datetime as _dt
    from modules.models import QuoteCache as _QC
    stamp = now_utc if now_utc is not None else _dt.utcnow()
    try:
        exists = db.query(_QC).filter_by(symbol=symbol, cache_date=today_tw).first()
        if exists:
            exists.open       = data.get('open')
            exists.high       = data.get('high')
            exists.low        = data.get('low')
            exists.close      = data.get('close')
            exists.prev_close = data.get('prev_close')
            exists.cached_at  = stamp
        else:
            db.add(_QC(
                symbol=symbol, cache_date=today_tw,
                open=data.get('open'), high=data.get('high'),
                low=data.get('low'), close=data.get('close'),
                prev_close=data.get('prev_close'),
                cached_at=stamp,
            ))
        db.commit()
    except Exception as e:
        print(f"[quote] upsert QuoteCache 失敗 {symbol}: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _try_market_data_cache(db, symbol, today_tw):
    """從今日 MarketDataCache 拆 OHLC + spark。回 dict 或 None。"""
    import json as _json
    from modules.models import MarketDataCache as _MDC
    mkt = db.query(_MDC).filter_by(symbol=symbol, cache_date=today_tw).first()
    if not mkt:
        return None
    try:
        bars = _json.loads(mkt.data_json).get('daily_bars', [])
    except Exception:
        return None
    if len(bars) < 2:
        return None
    last, prev = bars[-1], bars[-2]
    return {
        'symbol':     symbol,
        'open':       last['open'],
        'high':       last['high'],
        'low':        last['low'],
        'close':      last['close'],
        'prev_close': prev['close'],
        'spark_bars': _bars_to_spark(bars),
    }


def _try_quote_cache_db(db, symbol, today_tw):
    """從 QuoteCache 讀 + 從最近 MarketDataCache 補 spark。回 (dict, cached_at) 或 (None, None)。"""
    import json as _json
    from modules.models import QuoteCache as _QC, MarketDataCache as _MDC
    qc = db.query(_QC).filter_by(symbol=symbol, cache_date=today_tw).first()
    if not qc or qc.close is None:
        return None, None
    spark = []
    mkt = (db.query(_MDC).filter_by(symbol=symbol)
             .order_by(_MDC.cache_date.desc()).first())
    if mkt:
        try:
            bars = _json.loads(mkt.data_json).get('daily_bars', [])
            spark = _bars_to_spark(bars)
        except Exception:
            pass
    data = {
        'symbol':     symbol,
        'open':       float(qc.open) if qc.open is not None else None,
        'high':       float(qc.high) if qc.high is not None else None,
        'low':        float(qc.low) if qc.low is not None else None,
        'close':      float(qc.close),
        'prev_close': float(qc.prev_close) if qc.prev_close is not None else None,
        'spark_bars': spark,
    }
    return data, qc.cached_at


def _resolve_quote(db, symbol, today_tw, now_utc, get_yahoo_quote=None):
    """看板行情核心讀取邏輯。

    Post-close（TW 14:30 後）：
      1. 先試 MarketDataCache（14:30 batch 寫的權威收盤）→ 命中即 upsert QuoteCache 並回傳
      2. 記憶體 / QuoteCache 若 cached_at < 今日 14:30 視為 stale → 繞過
    Pre-close：照原行為 _quote_cache → QuoteCache → MarketDataCache → Yahoo。

    Yahoo 命中時同步 upsert QuoteCache。失敗回 None。
    """
    key = f'{symbol}_{today_tw}'
    post_close = _post_close_tw(now_utc=now_utc)
    threshold = _today_close_threshold_utc(now_utc=now_utc)

    # ① post-close：先試 MarketDataCache（權威收盤）
    if post_close:
        data = _try_market_data_cache(db, symbol, today_tw)
        if data is not None:
            data['_cached_at_utc'] = now_utc
            _quote_cache[key] = data
            _upsert_quote_cache(db, symbol, today_tw, data, now_utc=now_utc)
            return _strip_internal(data)

    # ② 記憶體：post-close 時需檢查 staleness
    entry = _quote_cache.get(key)
    if entry is not None:
        cached_at = entry.get('_cached_at_utc')
        if post_close and cached_at is not None and cached_at < threshold:
            _quote_cache.pop(key, None)
        else:
            return _strip_internal(entry)

    # ③ QuoteCache (DB)：post-close 時同樣檢查 staleness
    data, cached_at = _try_quote_cache_db(db, symbol, today_tw)
    if data is not None:
        if not (post_close and cached_at is not None and cached_at < threshold):
            data['_cached_at_utc'] = cached_at
            _quote_cache[key] = data
            return _strip_internal(data)

    # ④ 非 post-close 時也試 MarketDataCache（保留舊 fallback）
    if not post_close:
        data = _try_market_data_cache(db, symbol, today_tw)
        if data is not None:
            data['_cached_at_utc'] = now_utc
            _quote_cache[key] = data
            return _strip_internal(data)

    # ⑤ Yahoo
    if get_yahoo_quote is None:
        from modules.data_enricher import get_stock_quote as _yq
        get_yahoo_quote = _yq
    data = get_yahoo_quote(symbol)
    if data is None:
        return None
    if 'spark_bars' not in data:
        import json as _json
        from modules.models import MarketDataCache as _MDC
        try:
            mkt = (db.query(_MDC).filter_by(symbol=symbol)
                     .order_by(_MDC.cache_date.desc()).first())
            if mkt:
                bars = _json.loads(mkt.data_json).get('daily_bars', [])
                data['spark_bars'] = _bars_to_spark(bars)
        except Exception:
            pass
        data.setdefault('spark_bars', [])
    data['_cached_at_utc'] = now_utc
    _quote_cache[key] = data
    _upsert_quote_cache(db, symbol, today_tw, data, now_utc=now_utc)
    return _strip_internal(data)


@app.route('/api/market/<symbol>/info')
@login_required
def api_market_info(symbol):
    from modules.data_enricher import get_stock_info
    info = get_stock_info(symbol)
    if info is None:
        return jsonify({'error': f'找不到 {symbol}'}), 404
    return jsonify(info)


@app.route('/api/market/search')
@login_required
def api_market_search():
    """依股名（部分子字串）回傳候選清單，最多 10 筆。前端輸入名稱自動帶代號用。
    排序：完全相符 > 開頭相符 > 包含；同類按代號長度（短的＝普通股優先於權證等）。"""
    from modules.stock_names import STOCK_NAMES
    q = (request.args.get('q') or '').strip()
    if len(q) < 1:
        return jsonify([])
    matches = []
    for code, name in STOCK_NAMES.items():
        if q == name:
            rank = 0
        elif name.startswith(q):
            rank = 1
        elif q in name:
            rank = 2
        else:
            continue
        matches.append((rank, len(code), code, name))
    matches.sort()  # rank ASC, code length ASC
    return jsonify([
        {'symbol': code + '.TW', 'name': name}
        for _, _, code, name in matches[:10]
    ])


@app.route('/api/market/<symbol>/quote')
@login_required
def api_market_quote(symbol):
    """輕量行情（OHLC + 漲跌）：看板用。實際讀取邏輯見 _resolve_quote。"""
    from datetime import datetime as _dt, timedelta as _td
    now_utc = _dt.utcnow()
    today = (now_utc + _td(hours=8)).date()
    db = SessionLocal()
    try:
        result = _resolve_quote(db, symbol, today, now_utc)
    finally:
        db.close()
    if result is None:
        return jsonify({'error': f'無法取得 {symbol} 行情'}), 404
    return jsonify(result)


@app.route('/api/market/<symbol>/data')
@login_required
def api_market_data(symbol):
    """完整市場資料：股票詳情頁用，DB 當日快取、跨用戶共用"""
    import json
    from datetime import datetime as _dt, timedelta as _td
    from modules.models import MarketDataCache
    from modules.data_enricher import get_full_stock_data
    today = (_dt.utcnow() + _td(hours=8)).date()
    db = SessionLocal()
    try:
        cached = db.query(MarketDataCache).filter_by(
            symbol=symbol, cache_date=today
        ).first()
        if cached:
            print(f"[market/data] 快取命中 {symbol}")
            return jsonify(json.loads(cached.data_json))

        print(f"[market/data] 快取 miss，抓 Yahoo {symbol}")
        data = get_full_stock_data(symbol)
        if data is None:
            return jsonify({'error': f'無法取得 {symbol} 資料'}), 404

        try:
            db.add(MarketDataCache(
                symbol=symbol, cache_date=today,
                data_json=json.dumps(data, ensure_ascii=False)
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[market/data] 快取寫入失敗 {symbol}: {e}")

        return jsonify(data)
    finally:
        db.close()


# ── AI 分析 API ───────────────────────────────────────────

@app.route('/api/stocks/<int:stock_id>/analysis')
@login_required
def api_get_analysis(stock_id):
    """讀取市場快取分析：先找今日，找不到 fallback 最新一筆（不限日期）"""
    from datetime import date as dt_date
    from modules.models import Stock, StockAnalysis
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        today = _analysis_day_tw()
        # ① 今日快取
        cached  = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        is_today = cached is not None

        # ② fallback：最新一筆（歷史）
        if not cached or not cached.html_content:
            cached = (
                db.query(StockAnalysis)
                .filter(
                    StockAnalysis.symbol == stock.symbol,
                    StockAnalysis.analysis_type == 'daily',
                    StockAnalysis.html_content.isnot(None),
                )
                .order_by(StockAnalysis.analysis_date.desc())
                .first()
            )
            is_today = False

        if not cached or not cached.html_content:
            return jsonify({'cached': False})

        from modules.ai_analyzer_v2 import _clean_html_output
        return jsonify({
            'cached':         True,
            'is_today':       is_today,
            'analysis_date':  cached.analysis_date.isoformat(),
            'html':           _clean_html_output(cached.html_content),
            'risk_pct':       cached.risk_pct,
            'support':        float(cached.support_price)    if cached.support_price    else None,
            'resistance':     float(cached.resistance_price) if cached.resistance_price else None,
            'target_pnf':     float(cached.target_price)     if cached.target_price     else None,
            'wyckoff_phase':  cached.wyckoff_phase,
            'generated_at':   cached.generated_at.strftime('%H:%M') if cached.generated_at else None,
        })
    finally:
        db.close()


@app.route('/api/stocks/<int:stock_id>/analyze', methods=['POST'])
@login_required
def api_analyze_stock(stock_id):
    """產生市場分析（第一段）並存入跨用戶快取"""
    from datetime import date as dt_date
    import datetime as _dt
    from modules.models import Stock, StockAnalysis
    from modules.data_enricher import get_full_stock_data
    from modules.ai_analyzer_v2 import analyze_market_only
    from decimal import Decimal

    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        today = _analysis_day_tw()
        force = request.args.get('force', '0') == '1'
        # 已有今日快取且非強制重分析，直接回傳
        existing = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        if existing and existing.html_content and not force:
            return jsonify({
                'html':          existing.html_content,
                'risk_pct':      existing.risk_pct,
                'support':       float(existing.support_price)    if existing.support_price    else None,
                'resistance':    float(existing.resistance_price) if existing.resistance_price else None,
                'target_pnf':    float(existing.target_price)     if existing.target_price     else None,
                'wyckoff_phase': existing.wyckoff_phase,
                'from_cache':    True,
            })

        # force=1 且今日已有快取 → 檢查台灣時間（UTC+8）及冷卻期
        if existing and existing.html_content and force:
            tw_now = _dt.datetime.utcnow() + _dt.timedelta(hours=8)
            if tw_now.hour < 15:
                return jsonify({'error': 'CUTOFF|15:00'}), 429
            if existing.generated_at:
                elapsed = (_dt.datetime.utcnow() - existing.generated_at).total_seconds()
                if elapsed < 4 * 3600:
                    unlock_tw = existing.generated_at + _dt.timedelta(hours=12)
                    return jsonify({'error': f'COOLDOWN|{unlock_tw.strftime("%H:%M")}'}), 429

        enriched = get_full_stock_data(stock.symbol)
        if enriched is None:
            return jsonify({'error': f'無法取得 {stock.symbol} 市場資料'}), 503

        # 優化1 2026-05-22：持股時報表加「六、持倉部位建議」（user-agnostic）
        _is_holding = bool(stock.status == 'holding' and stock.trades)

        result = analyze_market_only(
            name=stock.name, symbol=stock.symbol,
            enriched_data=enriched, news_list=[], is_holding=_is_holding,
        )

        # B 組 2026-05-20：DB 寫入 anchor 優先（程式鎖定），AI tag 當 fallback
        # 2026-05-22 Bug B：目標 pill 與內文同標「目標」→ 必須同值，故直接採
        # target_pnf（內文 P&F 來源），不再 fallback swing target_anchor（lookback 不同會差）
        _sup = result.get('support_anchor')    or result.get('support')
        _res = result.get('resistance_anchor') or result.get('resistance')
        _tgt = result.get('target_pnf')
        _stp = result.get('stop_loss_anchor')
        _elo = result.get('entry_low')   # plan §三十三
        _ehi = result.get('entry_high')  # plan §三十三

        if existing:
            existing.html_content     = result['html']
            existing.risk_pct         = result['risk_pct']
            existing.support_price    = Decimal(str(_sup)) if _sup else None
            existing.resistance_price = Decimal(str(_res)) if _res else None
            existing.target_price     = Decimal(str(_tgt)) if _tgt else None
            existing.stop_loss        = Decimal(str(_stp)) if _stp else None
            existing.entry_low        = Decimal(str(_elo)) if _elo else None
            existing.entry_high       = Decimal(str(_ehi)) if _ehi else None
            existing.wyckoff_phase    = result['wyckoff_phase']
            existing.action_pill      = result.get('action_pill')  # plan §三十一
            existing.generated_at     = _dt.datetime.utcnow()
        else:
            db.add(StockAnalysis(
                symbol=stock.symbol, analysis_date=today, analysis_type='daily',
                html_content=result['html'], risk_pct=result['risk_pct'],
                support_price=Decimal(str(_sup)) if _sup else None,
                resistance_price=Decimal(str(_res)) if _res else None,
                target_price=Decimal(str(_tgt)) if _tgt else None,
                stop_loss=Decimal(str(_stp)) if _stp else None,
                entry_low=Decimal(str(_elo)) if _elo else None,
                entry_high=Decimal(str(_ehi)) if _ehi else None,
                wyckoff_phase=result['wyckoff_phase'],
                action_pill=result.get('action_pill'),  # plan §三十一
            ))
        db.commit()

        return jsonify({
            'html':          result['html'],
            'risk_pct':      result['risk_pct'],
            'support':       result['support'],
            'resistance':    result['resistance'],
            'target_pnf':    result['target_pnf'],
            'wyckoff_phase': result['wyckoff_phase'],
            'from_cache':    False,
        })
    finally:
        db.close()


@app.route('/api/stocks/<int:stock_id>/recommend', methods=['POST'])
@login_required
def api_recommend_stock(stock_id):
    """產生個人化操作建議（第二段），使用市場快取資料。
    A 組 2026-05-20：結果寫入 PersonalRecommendation cache，print PDF 從此表讀。
    """
    from datetime import date as dt_date
    from modules.models import Stock, StockAnalysis, PersonalRecommendation
    from modules.data_enricher import get_stock_info
    from modules.ai_analyzer_v2 import generate_personal_recommendation

    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404

        today = _analysis_day_tw()
        cached = db.query(StockAnalysis).filter_by(
            symbol=stock.symbol, analysis_date=today, analysis_type='daily'
        ).first()
        if not cached or not cached.html_content:
            return jsonify({'error': '尚無市場分析，請先產生分析'}), 404

        # 嘗試讀今日既有 cache（同 user × symbol × date 已產生過則直接回）
        existing_rec = db.query(PersonalRecommendation).filter_by(
            user_id=current_user.id, symbol=stock.symbol, analysis_date=today
        ).first()
        if existing_rec:
            return jsonify({'html': existing_rec.html, 'from_cache': True})

        info = get_stock_info(stock.symbol)
        current_price = info['price'] if info else 0

        avg   = float(stock.avg_cost)    if stock.avg_cost    else None
        total = float(stock.total_zhang) if stock.total_zhang else None

        # 從 DB 快取取近期 K 棒
        import json as _json
        from modules.models import MarketDataCache
        recent_bars = []
        mkt_cache = db.query(MarketDataCache).filter_by(
            symbol=stock.symbol, cache_date=today
        ).first()
        if mkt_cache:
            try:
                recent_bars = _json.loads(mkt_cache.data_json).get('daily_bars', [])[-5:]
            except Exception:
                pass

        html = generate_personal_recommendation(
            name=stock.name, symbol=stock.symbol,
            current_price=current_price,
            wyckoff_phase=cached.wyckoff_phase or '未知',
            risk_pct=cached.risk_pct or 50,
            support=float(cached.support_price)    if cached.support_price    else None,
            resistance=float(cached.resistance_price) if cached.resistance_price else None,
            target_pnf=float(cached.target_price)  if cached.target_price    else None,
            status=stock.status,
            avg_cost=avg,
            total_zhang=total,
            recent_bars=recent_bars,
        )

        # 寫入 cache（同 key 已存在則 update，理論上前面 existing_rec 已 return）
        db.add(PersonalRecommendation(
            user_id=current_user.id, symbol=stock.symbol,
            analysis_date=today, html=html,
        ))
        db.commit()

        return jsonify({'html': html, 'from_cache': False})
    finally:
        db.close()


# ── 持股 CRUD API ─────────────────────────────────────────

@app.route('/api/stocks')
@login_required
def api_get_stocks():
    db = SessionLocal()
    try:
        return jsonify(get_user_stocks(db, current_user.id))
    finally:
        db.close()


@app.route('/api/stocks/add', methods=['POST'])
@login_required
def api_add_stock():
    data = request.json
    db = SessionLocal()
    try:
        stock = add_stock(
            db, current_user.id,
            symbol=data['symbol'],
            name=data['name'],
            status=data.get('status', 'watching'),
            buy_price=data.get('buy_price'),
            quantity_zhang=data.get('quantity_zhang'),
            buy_date=data.get('buy_date'),
        )
        return jsonify({'ok': True, 'id': stock.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/stocks/reorder', methods=['PATCH'])
@login_required
def api_reorder_stocks():
    """body: {"order": [stock_id, stock_id, ...]} — 依此順序寫 display_order"""
    data = request.json or {}
    ids = data.get('order') or []
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return jsonify({'ok': False, 'error': 'order 須為 int 陣列'}), 400
    db = SessionLocal()
    try:
        updated = reorder_stocks(db, current_user.id, ids)
        return jsonify({'ok': True, 'updated': updated})
    finally:
        db.close()


@app.route('/api/stocks/<int:stock_id>/trades')
@login_required
def api_get_trades(stock_id):
    db = SessionLocal()
    try:
        from modules.models import Stock
        stock = db.query(Stock).filter_by(id=stock_id, user_id=current_user.id).first()
        if not stock:
            return jsonify({'error': '股票不存在'}), 404
        return jsonify({
            'trades':      [{'id': t.id, 'buy_price': float(t.buy_price),
                             'quantity_zhang': float(t.quantity_zhang),
                             'buy_date': t.buy_date.isoformat() if t.buy_date else None}
                            for t in stock.trades],
            'total_zhang': float(stock.total_zhang) if stock.total_zhang else 0,
            'avg_cost':    float(stock.avg_cost) if stock.avg_cost else None,
        })
    finally:
        db.close()


@app.route('/api/trades/<int:trade_id>', methods=['PUT'])
@login_required
def api_update_trade(trade_id):
    data = request.json
    db = SessionLocal()
    try:
        trade = update_trade(db, current_user.id, trade_id,
                             quantity_zhang=data['quantity_zhang'],
                             buy_price=data.get('buy_price'),
                             buy_date=data.get('buy_date'))
        return jsonify({'ok': True, 'trade_id': trade.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/trades/<int:trade_id>', methods=['DELETE'])
@login_required
def api_delete_trade(trade_id):
    db = SessionLocal()
    try:
        delete_trade(db, current_user.id, trade_id)
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/stocks/trade', methods=['POST'])
@login_required
def api_add_trade():
    data = request.json
    db = SessionLocal()
    try:
        trade = add_trade(
            db, current_user.id,
            stock_id=data['stock_id'],
            buy_price=data['buy_price'],
            quantity_zhang=data['quantity_zhang'],
            buy_date=data.get('buy_date'),
        )
        return jsonify({'ok': True, 'trade_id': trade.id})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/admin/clear-today-cache', methods=['POST'])
@login_required
def api_clear_today_cache():
    """⚠️ 測試用：清除所有 StockAnalysis + DailyMarketSummary 快取（含歷史）"""
    if current_user.role != 'admin':
        return jsonify({'error': '無權限'}), 403
    from modules.models import StockAnalysis, DailyMarketSummary
    db = SessionLocal()
    try:
        deleted = db.query(StockAnalysis).delete()
        db.query(DailyMarketSummary).delete()
        db.commit()
        return jsonify({'deleted': deleted, 'date': 'all'})
    finally:
        db.close()


@app.route('/api/news/regenerate', methods=['POST'])
@login_required
def api_regenerate_news():
    """重新抓取財經新聞並呼叫 AI 產生 DailyMarketSummary（清快取後使用）"""
    from modules.models import DailyMarketSummary
    from modules.ai_analyzer_v2 import analyze_daily_news
    from modules.data_fetcher import get_tw_news_rss, get_global_markets
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    today = datetime.now(TW).date()

    db = SessionLocal()
    try:
        news = get_tw_news_rss(15)
        twii_price, twii_change_pct = None, None
        try:
            markets = get_global_markets()
            twii_data = markets.get('台灣加權', {})
            # Freshness 驗證：last_date 必須是今日（TW），否則不注入給 AI，
            # 避免 prompt 餵昨日數值導致 AI 忠實複述「今日大盤 X 點」實際是昨日的 X
            twii_last = twii_data.get('last_date')
            if twii_last == str(today):
                twii_price = twii_data.get('price')
                twii_change_pct = twii_data.get('change')
            else:
                print(f"[regenerate-news] TWII 資料非今日（{twii_last} vs {today}），不注入大盤點位")
        except Exception:
            pass

        html_news = analyze_daily_news(news, twii_price=twii_price, twii_change_pct=twii_change_pct)

        db.query(DailyMarketSummary).filter_by(summary_date=today).delete()
        db.add(DailyMarketSummary(summary_date=today, html_content=html_news))
        db.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/stocks/remove', methods=['POST'])
@login_required
def api_remove_stock():
    data = request.json
    db = SessionLocal()
    try:
        remove_stock(db, current_user.id, data['stock_id'])
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/print-report')
@login_required
def print_report():
    from modules.models import Stock, StockAnalysis, WeeklyReport, QuoteCache, DailyMarketSummary
    from sqlalchemy import func, case
    from datetime import datetime, timezone, timedelta, date
    TW = timezone(timedelta(hours=8))

    db = SessionLocal()
    try:
        # 排序與 dashboard 看板一致：display_order 升冪、NULL 排最後
        # （複製 stock_service.get_user_stocks 的排序邏輯，但保留 ORM 物件
        #  以便取用 s.trades / s.avg_cost / s.total_zhang 等 property）
        stocks = (db.query(Stock)
                  .filter_by(user_id=current_user.id)
                  .order_by(case((Stock.display_order.is_(None), 1), else_=0),
                            Stock.display_order,
                            Stock.created_at)
                  .all())
        if not stocks:
            return '尚無持股資料', 404

        # 顯示切換：週末視窗（週五 14:30 ~ 週一 09:00）→ 週報；其餘 → 每日新聞
        now_tw = datetime.now(TW)
        wd, h, m = now_tw.weekday(), now_tw.hour, now_tw.minute
        show_weekly = (
            (wd == 4 and (h > 14 or (h == 14 and m >= 30))) or  # 週五 14:30+
            wd in (5, 6) or                                      # 週六、週日
            (wd == 0 and h < 9)                                  # 週一 09:00 前
        )
        if show_weekly:
            weekly = db.query(WeeklyReport).order_by(WeeklyReport.week_start.desc()).first()
            weekly_range = (f"{weekly.week_start.strftime('%Y/%m/%d')} ~ "
                            f"{weekly.week_end.strftime('%Y/%m/%d')}") if weekly else ''
            daily_news = None
        else:
            weekly = None
            weekly_range = ''
            # 取最近一筆（不限今天）：批次 14:30 才跑，早上開報表昨天的仍有效
            daily_news = (db.query(DailyMarketSummary)
                          .order_by(DailyMarketSummary.summary_date.desc())
                          .first())

        symbols = [s.symbol for s in stocks]

        # 最新 daily 分析（每支股一筆）
        subq = (
            db.query(StockAnalysis.symbol,
                     func.max(StockAnalysis.analysis_date).label('max_date'))
            .filter(StockAnalysis.symbol.in_(symbols),
                    StockAnalysis.analysis_type == 'daily',
                    StockAnalysis.html_content.isnot(None))
            .group_by(StockAnalysis.symbol)
            .subquery()
        )
        rows = (
            db.query(StockAnalysis)
            .join(subq, (StockAnalysis.symbol == subq.c.symbol) &
                        (StockAnalysis.analysis_date == subq.c.max_date))
            .all()
        )
        analyses = {r.symbol: r for r in rows}

        # 各股最近一筆 quote（不限今天）：批次 14:30 才跑，早上也顯示昨日收盤
        # 同 Bug 6 改法（DailyMarketSummary 已採相同做法）
        subq_q = (
            db.query(QuoteCache.symbol,
                     func.max(QuoteCache.cache_date).label('max_date'))
            .filter(QuoteCache.symbol.in_(symbols))
            .group_by(QuoteCache.symbol)
            .subquery()
        )
        quote_rows = (
            db.query(QuoteCache)
            .join(subq_q,
                  (QuoteCache.symbol == subq_q.c.symbol) &
                  (QuoteCache.cache_date == subq_q.c.max_date))
            .all()
        )
        quotes = {q.symbol: q for q in quote_rows}

        # A 組 2026-05-20：讀 PersonalRecommendation cache（per user × per stock × today）
        from modules.models import PersonalRecommendation
        rec_rows = (db.query(PersonalRecommendation)
                    .filter(PersonalRecommendation.user_id == current_user.id,
                            PersonalRecommendation.symbol.in_(symbols),
                            PersonalRecommendation.analysis_date == _analysis_day_tw())
                    .all())
        personals = {r.symbol: r.html for r in rec_rows}

        # 拆 holdings / watching
        holdings = [s for s in stocks if s.status == 'holding']
        watching = [s for s in stocks if s.status == 'watching']
        holdings_html = _render_stock_blocks(holdings, analyses, quotes, mode='holding', personals=personals)
        watching_html = _render_stock_blocks(watching, analyses, quotes, mode='watching', personals=personals)

        return render_template(
            'print_report.html',
            date_str=now_tw.strftime('%Y/%m/%d %H:%M'),
            user_name=current_user.name,
            holding_count=len(holdings),
            watching_count=len(watching),
            holdings_html=holdings_html,
            watching_html=watching_html,
            weekly=weekly,
            weekly_range=weekly_range,
            daily_news=daily_news,
        )
    finally:
        db.close()


@app.route('/weekly-report')
@login_required
def weekly_report():
    from modules.models import WeeklyReport
    db = SessionLocal()
    try:
        report = db.query(WeeklyReport).order_by(WeeklyReport.week_start.desc()).first()
        return render_template('weekly_report.html', report=report)
    finally:
        db.close()


@app.route('/api/weekly-report/generate', methods=['POST'])
@login_required
def api_generate_weekly_report():
    if current_user.role != 'admin':
        return jsonify({'error': '無權限'}), 403

    import threading
    from run_weekly_report import main as weekly_main

    def run():
        try:
            weekly_main()
        except Exception as e:
            print(f"[api] 手動週報失敗: {e}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'ok': True})


# ── Email 分享 PDF 報表 ──────────────────────────────────

@app.route('/api/contacts')
@login_required
def api_list_contacts():
    """列出當前用戶的 email 通訊錄（最近用過的優先）"""
    from modules.models import EmailContact
    db = SessionLocal()
    try:
        rows = (db.query(EmailContact)
                .filter_by(user_id=current_user.id)
                .order_by(EmailContact.last_used_at.desc())
                .all())
        return jsonify([
            {'id': r.id, 'email': r.email, 'name': r.name}
            for r in rows
        ])
    finally:
        db.close()


def _smtp_send_ipv4(sender, password, recipients, msg_str):
    """強制走 IPv4 連 Gmail SMTP（雲端容器常見 IPv6 outbound 障礙的解法）。
    先試 587 STARTTLS，失敗再 fallback 到 465 SSL。"""
    import socket as _sk
    import smtplib

    def _ipv4_socket(host, port, timeout):
        addrs = _sk.getaddrinfo(host, port, _sk.AF_INET, _sk.SOCK_STREAM)
        if not addrs:
            raise OSError(f'無 IPv4 位址 for {host}')
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(addrs[0][4])
        return s

    class _IPv4SMTP(smtplib.SMTP):
        def _get_socket(self, host, port, timeout):
            return _ipv4_socket(host, port, timeout)

    class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
        def _get_socket(self, host, port, timeout):
            sock = _ipv4_socket(host, port, timeout)
            return self.context.wrap_socket(sock, server_hostname=host)

    last_err = None
    for attempt in (('STARTTLS', 587), ('SSL', 465)):
        mode, port = attempt
        try:
            if mode == 'STARTTLS':
                with _IPv4SMTP('smtp.gmail.com', port, timeout=20) as server:
                    server.starttls()
                    server.login(sender, password)
                    server.sendmail(sender, recipients, msg_str)
            else:
                with _IPv4SMTP_SSL('smtp.gmail.com', port, timeout=20) as server:
                    server.login(sender, password)
                    server.sendmail(sender, recipients, msg_str)
            return mode  # 成功
        except Exception as e:
            last_err = f'{mode}/{port}: {e}'
            print(f"[smtp] {last_err}")
    raise RuntimeError(last_err or '未知 SMTP 錯誤')


@app.route('/api/share/dashboard-pdf', methods=['POST'])
@login_required
def api_share_dashboard_pdf():
    """multipart：pdf 檔 + emails JSON list；強制 IPv4 SMTP，BCC 隱藏多收件人"""
    import json as _json
    from datetime import datetime as _dt, date as _date
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication
    from email.utils import formataddr
    from modules.models import EmailContact

    pdf_file = request.files.get('pdf')
    emails_raw = request.form.get('emails') or '[]'
    try:
        emails = _json.loads(emails_raw)
    except Exception:
        return jsonify({'ok': False, 'error': 'emails 格式錯誤'}), 400
    emails = [e.strip() for e in emails if isinstance(e, str) and '@' in e]
    if not pdf_file or not emails:
        return jsonify({'ok': False, 'error': '需要 pdf 檔與至少 1 個收件人'}), 400

    pdf_bytes = pdf_file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        return jsonify({'ok': False, 'error': 'PDF 超過 10MB'}), 400

    sender = os.getenv('EMAIL_SENDER')
    password = os.getenv('EMAIL_PASSWORD')
    if not sender or not password:
        return jsonify({'ok': False, 'error': 'SMTP 未設定（EMAIL_SENDER/PASSWORD）'}), 500

    today = _date.today().strftime('%Y/%m/%d')
    fname_date = _date.today().strftime('%Y%m%d')
    msg = MIMEMultipart()
    msg['From'] = formataddr((current_user.name, sender))
    msg['To'] = sender              # 主要收件人放自己（自留一份）
    # 不在 MIME header 放 Bcc（標準作法，避免外洩；改靠 sendmail 的 to_addrs）
    msg['Subject'] = f'【{current_user.name}】{today} 投資建議書'
    body = (
        f'您好，\n\n'
        f'這是 {current_user.name} 的本日投資建議書 PDF，請見附件。\n\n'
        f'本報表為自動化系統產出，僅供參考，不構成實際投資建議。\n'
    )
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
    pdf_part.add_header('Content-Disposition', 'attachment',
                        filename=('utf-8', '', f'投資建議書_{fname_date}.pdf'))
    msg.attach(pdf_part)

    try:
        mode = _smtp_send_ipv4(sender, password, [sender] + emails, msg.as_string())
        print(f"[share] 寄送成功（{mode}），收件人 {len(emails)} 位")
    except Exception as e:
        return jsonify({'ok': False, 'error': f'寄送失敗: {e}'}), 500

    # 寫入/更新通訊錄
    db = SessionLocal()
    try:
        now = _dt.utcnow()
        for em in emails:
            existing = db.query(EmailContact).filter_by(
                user_id=current_user.id, email=em
            ).first()
            if existing:
                existing.last_used_at = now
            else:
                db.add(EmailContact(user_id=current_user.id, email=em, last_used_at=now))
        db.commit()
    finally:
        db.close()

    return jsonify({'ok': True, 'sent_to': emails})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
