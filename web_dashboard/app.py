from flask import Flask, request, jsonify, Response
import threading, os, sys, json, queue, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_fetcher import (get_global_markets, get_commodities,
                                   get_financial_news, get_taiwan_stocks,
                                   get_macro_assets, get_watchlist_stocks)
from modules.technical import analyze_all_stocks
from modules.livermore import analyze_all_signals
from modules.candlestick import detect_patterns
from modules.ai_analyzer import (analyze_global_market, analyze_taiwan_market,
                                  analyze_macro_assets, analyze_watchlist_stock,
                                  get_sector_recommendations)
from modules.pdf_generator import generate_daily_report
from modules.email_sender import send_report
from modules.watchlist import get_watchlist, add_stock, remove_stock
import config, yfinance as yf

app = Flask(__name__)

# 每個 session 用一個 queue 來傳遞進度
progress_queues = {}
# 全域鎖：防止同時產生兩份報表
_is_generating = False

DASHBOARD = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>投資建議系統</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Microsoft JhengHei",sans-serif;background:#f0f2f5;color:#333}
.topbar{background:#1a237e;color:white;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}
.topbar h1{font-size:18px}
.badge{background:#4caf50;padding:4px 12px;border-radius:20px;font-size:12px}
.container{max-width:1100px;margin:24px auto;padding:0 16px}
.section{background:white;border-radius:8px;padding:20px;margin-bottom:16px;border:1px solid #e0e0e0}
.section h3{font-size:15px;font-weight:600;color:#1a237e;margin-bottom:14px;border-bottom:2px solid #1a237e;padding-bottom:6px}
.btn-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
.btn-card{background:white;border:1px solid #e0e0e0;border-radius:8px;padding:18px;cursor:pointer}
.btn-card h4{font-size:14px;color:#1a237e;margin-bottom:6px}
.btn-card p{font-size:12px;color:#888;margin-bottom:12px}
.btn{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-family:inherit;color:white}
.btn-blue{background:#1a237e}.btn-blue:hover{background:#283593}
.btn-teal{background:#00695c}.btn-teal:hover{background:#00796b}
.btn-red{background:#c62828}.btn-red:hover{background:#b71c1c}
.btn-gray{background:#757575}.btn-gray:hover{background:#616161}
.btn:disabled{opacity:0.5;cursor:not-allowed}

/* 進度條區塊 */
.progress-wrap{background:white;border-radius:8px;padding:20px;border:1px solid #e0e0e0;margin-bottom:16px;display:none}
.progress-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.progress-title{font-size:14px;font-weight:600;color:#1a237e}
.progress-pct{font-size:14px;font-weight:600;color:#1a237e}
.progress-bar{height:8px;background:#e0e0e0;border-radius:4px;margin-bottom:12px;overflow:hidden}
.progress-fill{height:100%;background:linear-gradient(90deg,#1a237e,#5c6bc0);border-radius:4px;transition:width 0.5s ease}
.progress-fill.done{background:linear-gradient(90deg,#2e7d32,#66bb6a)}
.progress-fill.error{background:linear-gradient(90deg,#c62828,#ef5350)}
.step-list{display:flex;flex-direction:column;gap:6px}
.step-item{display:flex;align-items:center;gap:8px;font-size:13px;color:#aaa;transition:color 0.3s}
.step-item.active{color:#1a237e;font-weight:600}
.step-item.done{color:#2e7d32}
.step-item.error{color:#c62828}
.step-dot{width:8px;height:8px;border-radius:50%;background:#ddd;flex-shrink:0;transition:background 0.3s}
.step-item.active .step-dot{background:#1a237e;box-shadow:0 0 0 3px #c5cae9}
.step-item.done .step-dot{background:#2e7d32}
.step-item.error .step-dot{background:#c62828}
.step-spinner{width:14px;height:14px;border:2px solid #c5cae9;border-top-color:#1a237e;border-radius:50%;animation:spin 0.8s linear infinite;flex-shrink:0;display:none}
.step-item.active .step-spinner{display:inline-block}
.step-item.active .step-dot{display:none}
@keyframes spin{to{transform:rotate(360deg)}}

.form-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:14px}
.form-group{display:flex;flex-direction:column;gap:4px}
.form-group label{font-size:12px;color:#666}
.form-group input{padding:7px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;width:130px}
.watchlist-table{width:100%;border-collapse:collapse;font-size:13px}
.watchlist-table th{background:#e8eaf6;padding:8px;text-align:left}
.watchlist-table td{padding:8px;border-bottom:1px solid #f0f0f0}
.tag-up{color:#e74c3c;font-weight:500}
.tag-down{color:#27ae60;font-weight:500}
.hist-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #f5f5f5}
.hist-item:last-child{border-bottom:none}
.hist-badge{background:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:20px;font-size:11px}
.msg{padding:10px 14px;border-radius:6px;font-size:13px;margin-bottom:10px;display:none}
.msg-ok{background:#e8f5e9;color:#2e7d32}
.msg-err{background:#ffebee;color:#c62828}
</style>
</head>
<body>
<div class="topbar">
  <h1>投資建議系統 · 控制台</h1>
  <span class="badge">系統運行中</span>
</div>
<div class="container">

  <div id="msg" class="msg"></div>

  <!-- 進度條區塊 -->
  <div id="progress-wrap" class="progress-wrap">
    <div class="progress-header">
      <span class="progress-title" id="progress-title">正在產生報表...</span>
      <span class="progress-pct" id="progress-pct">0%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" id="pbar" style="width:0%"></div>
    </div>
    <div class="step-list" id="step-list"></div>
  </div>

  <div class="btn-grid">
    <div class="btn-card">
      <h4>每日晨報</h4>
      <p>全球財經 + 美債/黃金/石油 + 持股追蹤 + AI分析</p>
      <button class="btn btn-blue" id="btn-daily" onclick="generate('daily')">立即產生並寄送</button>
    </div>
    <div class="btn-card">
      <h4>週報總結</h4>
      <p>本週回顧 + 下週標的建議</p>
      <button class="btn btn-teal" id="btn-weekly" onclick="generate('weekly')">立即產生並寄送</button>
    </div>
  </div>

  <div class="section">
    <h3>持股追蹤管理</h3>
    <div class="form-row">
      <div class="form-group">
        <label>股票代號（必填）</label>
        <input id="f-symbol" placeholder="例：2330" />
      </div>
      <div class="form-group">
        <label>股票名稱（選填）</label>
        <input id="f-name" placeholder="例：台積電" />
      </div>
      <div class="form-group">
        <label>買進成本（選填）</label>
        <input id="f-cost" placeholder="例：950" type="number" />
      </div>
      <div class="form-group">
        <label>持股數量（選填）</label>
        <input id="f-shares" placeholder="例：1000" type="number" />
      </div>
      <div class="form-group">
        <label>買進日期（選填）</label>
        <input id="f-date" type="date" />
      </div>
      <div class="form-group">
        <label>&nbsp;</label>
        <button class="btn btn-blue" onclick="addStock()">新增追蹤</button>
      </div>
    </div>

    <table class="watchlist-table">
      <thead><tr><th>股票</th><th>代號</th><th>現值</th><th>漲跌</th><th>成本</th><th>持股數</th><th>損益</th><th>操作</th></tr></thead>
      <tbody id="watchlist-body"><tr><td colspan="8" style="text-align:center;color:#888;padding:16px">載入中...</td></tr></tbody>
    </table>
  </div>

  <div class="section">
    <h3>最近產生紀錄</h3>
    <div id="report-list"><div style="color:#888;font-size:13px">載入中...</div></div>
  </div>

</div>
<script>
const STEPS = {
  daily: [
    { key: 'fetch_global',    label: '抓取全球市場資料' },
    { key: 'fetch_taiwan',    label: '抓取台股資料' },
    { key: 'fetch_news',      label: '抓取財經新聞' },
    { key: 'fetch_watchlist', label: '抓取持股追蹤資料' },
    { key: 'technical',       label: '進行技術分析' },
    { key: 'ai_global',       label: 'AI 分析全球市場' },
    { key: 'ai_taiwan',       label: 'AI 分析台股' },
    { key: 'ai_watchlist',    label: 'AI 分析持股追蹤' },
    { key: 'ai_sector',       label: 'AI 分析產業投資方向' },
    { key: 'generate_pdf',    label: '產生 PDF 報表' },
    { key: 'send_email',      label: '寄送 Email' },
  ],
  weekly: [
    { key: 'fetch_global',    label: '抓取全球市場資料' },
    { key: 'fetch_taiwan',    label: '抓取台股資料' },
    { key: 'fetch_news',      label: '抓取財經新聞' },
    { key: 'fetch_watchlist', label: '抓取持股追蹤資料' },
    { key: 'technical',       label: '進行技術分析' },
    { key: 'ai_global',       label: 'AI 分析本週全球市場' },
    { key: 'ai_taiwan',       label: 'AI 分析本週台股' },
    { key: 'ai_watchlist',    label: 'AI 分析本週持股' },
    { key: 'ai_sector',       label: 'AI 推薦下週標的' },
    { key: 'generate_pdf',    label: '產生週報 PDF' },
    { key: 'send_email',      label: '寄送 Email' },
  ]
};

let currentType = null;
let eventSource = null;

function showMsg(text, ok) {
  const el = document.getElementById('msg');
  el.textContent = text;
  el.className = 'msg ' + (ok ? 'msg-ok' : 'msg-err');
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 5000);
}

function renderSteps(type) {
  const steps = STEPS[type];
  document.getElementById('step-list').innerHTML = steps.map(s =>
    `<div class="step-item" id="step-${s.key}">
      <div class="step-spinner"></div>
      <div class="step-dot"></div>
      <span>${s.label}</span>
    </div>`
  ).join('');
}

function setStep(key, state) {
  const el = document.getElementById('step-' + key);
  if (!el) return;
  el.className = 'step-item ' + state;
}

function setProgress(pct, title) {
  document.getElementById('pbar').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  if (title) document.getElementById('progress-title').textContent = title;
}

function generate(type) {
  if (currentType) return;
  currentType = type;

  // 禁用按鈕
  document.getElementById('btn-daily').disabled = true;
  document.getElementById('btn-weekly').disabled = true;

  // 顯示進度區塊
  const wrap = document.getElementById('progress-wrap');
  wrap.style.display = 'block';
  document.getElementById('pbar').className = 'progress-fill';
  renderSteps(type);
  setProgress(5, '正在啟動...');

  // 先呼叫 POST 啟動任務
  fetch('/api/generate/' + type, {method:'POST'})
    .then(r => {
      if (r.status === 429) {
        // 後端正在執行中
        currentType = null;
        document.getElementById('btn-daily').disabled = false;
        document.getElementById('btn-weekly').disabled = false;
        document.getElementById('progress-wrap').style.display = 'none';
        showMsg('⚠️ 報表正在產生中，請勿重複點擊，完成後會自動寄送 Email', false);
        return null;
      }
      return r.json();
    })
    .then(d => {
      if (!d) return;
      const jobId = d.job_id;
      // 用 SSE 接收進度
      eventSource = new EventSource('/api/progress/' + jobId);
      eventSource.onmessage = function(e) {
        const data = JSON.parse(e.data);

        if (data.type === 'step_start') {
          setStep(data.key, 'active');
          setProgress(data.pct, data.label + '...');
        } else if (data.type === 'step_done') {
          setStep(data.key, 'done');
          setProgress(data.pct, data.label + ' ✓');
        } else if (data.type === 'done') {
          setProgress(100, '✅ 完成！');
          document.getElementById('pbar').className = 'progress-fill done';
          eventSource.close();
          currentType = null;
          document.getElementById('btn-daily').disabled = false;
          document.getElementById('btn-weekly').disabled = false;
          showMsg(data.message, true);
          setTimeout(() => {
            wrap.style.display = 'none';
            setProgress(0);
            updateReports();
          }, 4000);
        } else if (data.type === 'error') {
          setProgress(100, '❌ 發生錯誤');
          document.getElementById('pbar').className = 'progress-fill error';
          eventSource.close();
          currentType = null;
          document.getElementById('btn-daily').disabled = false;
          document.getElementById('btn-weekly').disabled = false;
          showMsg('錯誤：' + data.message, false);
          setTimeout(() => { wrap.style.display = 'none'; setProgress(0); }, 5000);
        }
      };
      eventSource.onerror = function() {
        // SSE 中斷（手機切換 App 或網路不穩）
        // 不解除鎖定，因為後台可能還在執行
        // 顯示提示讓用戶知道
        document.getElementById('status-msg') &&
          (document.getElementById('status-msg').textContent = '連線中斷，報表仍在背景執行，請稍後查收 Email');
        eventSource.close();
        // 30 秒後才解除鎖定，避免重複觸發
        setTimeout(() => {
          currentType = null;
          document.getElementById('btn-daily').disabled = false;
          document.getElementById('btn-weekly').disabled = false;
        }, 30000);
      };
    });
}

function updateWatchlist() {
  fetch('/api/watchlist').then(r=>r.json()).then(d=>{
    const tb = document.getElementById('watchlist-body');
    if (!d.stocks || d.stocks.length === 0) {
      tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888;padding:16px">尚無追蹤標的</td></tr>';
      return;
    }
    tb.innerHTML = d.stocks.map(s => {
      const changeClass = s.change >= 0 ? 'tag-up' : 'tag-down';
      const sign = s.change >= 0 ? '+' : '';
      let pnl = '--';
      if (s.cost && s.price) {
        const p = ((s.price - s.cost) / s.cost * 100).toFixed(2);
        pnl = `<span class="${p>=0?'tag-up':'tag-down'}">${p>=0?'+':''}${p}%</span>`;
      }
      return `<tr>
        <td>${s.name}</td>
        <td>${s.symbol}</td>
        <td>${s.price ? 'NT$'+s.price.toLocaleString() : '--'}</td>
        <td class="${changeClass}">${sign}${s.change}%</td>
        <td>${s.cost ? 'NT$'+s.cost : '--'}</td>
        <td>${s.shares ? s.shares.toLocaleString() : '--'}</td>
        <td>${pnl}</td>
        <td><button class="btn btn-red" style="padding:4px 10px;font-size:12px" onclick="removeStock('${s.symbol}')">刪除</button></td>
      </tr>`;
    }).join('');
  });
}

function addStock() {
  const symbol = document.getElementById('f-symbol').value.trim();
  if (!symbol) { showMsg('請輸入股票代號', false); return; }
  const btn = document.querySelector('button[onclick="addStock()"]');
  btn.disabled = true;
  btn.textContent = '查詢中...';
  const data = {
    symbol: symbol,
    name: document.getElementById('f-name').value.trim() || symbol,
    cost: document.getElementById('f-cost').value || null,
    shares: document.getElementById('f-shares').value || null,
    buy_date: document.getElementById('f-date').value || null
  };
  fetch('/api/watchlist/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
    .then(r=>r.json()).then(d=>{
      btn.disabled = false;
      btn.textContent = '新增追蹤';
      showMsg(d.message, d.success);
      if (d.success) {
        document.getElementById('f-symbol').value = '';
        document.getElementById('f-name').value = '';
        document.getElementById('f-cost').value = '';
        document.getElementById('f-shares').value = '';
        document.getElementById('f-date').value = '';
        updateWatchlist();
      }
    }).catch(() => {
      btn.disabled = false;
      btn.textContent = '新增追蹤';
      showMsg('新增失敗，請稍後再試', false);
    });
}

function removeStock(symbol) {
  if (!confirm('確定要刪除 ' + symbol + ' 嗎？')) return;
  fetch('/api/watchlist/remove', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol})})
    .then(r=>r.json()).then(d=>{
      showMsg(d.message, d.success);
      if (d.success) updateWatchlist();
    });
}

function updateReports() {
  fetch('/api/reports').then(r=>r.json()).then(d=>{
    const el = document.getElementById('report-list');
    if (!d.reports || d.reports.length === 0) {
      el.innerHTML = '<div style="color:#888;font-size:13px">尚無報表紀錄</div>';
      return;
    }
    el.innerHTML = d.reports.map(r =>
      `<div class="hist-item">
        <div><div style="font-size:13px">${r.name}</div><div style="font-size:12px;color:#888">${r.time}</div></div>
        <span class="hist-badge">已產生</span>
      </div>`
    ).join('');
  });
}

updateWatchlist();
updateReports();
</script>
</body></html>'''

@app.route('/')
def index():
    return DASHBOARD

# ── SSE 進度推送 ──────────────────────────────────────────
@app.route('/api/progress/<job_id>')
def progress_stream(job_id):
    def stream():
        q = progress_queues.get(job_id)
        if not q:
            yield f"data: {json.dumps({'type':'error','message':'找不到任務'})}\n\n"
            return
        while True:
            try:
                msg = q.get(timeout=120)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get('type') in ('done', 'error'):
                    break
            except:
                break
        progress_queues.pop(job_id, None)
    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

def push(q, msg):
    """推送進度訊息到 queue"""
    q.put(msg)

STEP_PCT = {
    'fetch_global': 10, 'fetch_taiwan': 18, 'fetch_news': 25,
    'fetch_watchlist': 32, 'technical': 42, 'ai_global': 52,
    'ai_taiwan': 62, 'ai_watchlist': 74, 'ai_sector': 82,
    'generate_pdf': 90, 'send_email': 97
}

# ── API 路由 ──────────────────────────────────────────────
@app.route('/api/watchlist')
def api_watchlist():
    import requests as _req
    watchlist = get_watchlist()
    # 一次查詢所有股票
    def get_price(item):
        symbol = item['symbol']
        raw = symbol.replace('.TW','').replace('.TWO','')
        ex = 'otc' if '.TWO' in symbol else 'tse'
        ch = f'{ex}_{raw}.tw'
        try:
            r = _req.get('https://mis.twse.com.tw/stock/api/getStockInfo.jsp',
                params={'ex_ch': ch, 'json': '1', 'delay': '0'}, timeout=5)
            d = r.json()['msgArray'][0]
            z = d.get('z',''); pz = d.get('pz',''); y = d.get('y','')
            curr = float(z if z and z != '-' else (pz if pz and pz != '-' else y or 0))
            prev = float(d.get('y') or curr)
            change = round(((curr - prev) / prev) * 100, 2) if prev else 0
            return round(curr, 2), change
        except:
            return None, 0
    from concurrent.futures import ThreadPoolExecutor
    stocks = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(get_price, item): item for item in watchlist}
        for f, item in futures.items():
            price, change = f.result()
            stocks.append({
                'symbol': item['symbol'],
                'name': item['name'],
                'price': price,
                'change': change,
                'cost': item.get('cost'),
                'shares': item.get('shares')
            })
    return jsonify({'stocks': stocks})

@app.route('/api/watchlist/add', methods=['POST'])
def api_add():
    data = request.json
    success, message = add_stock(
        data.get('symbol'), data.get('name'),
        data.get('cost'), data.get('shares'), data.get('buy_date')
    )
    return jsonify({'success': success, 'message': message})

@app.route('/api/watchlist/remove', methods=['POST'])
def api_remove():
    symbol = request.json.get('symbol')
    success, message = remove_stock(symbol)
    return jsonify({'success': success, 'message': message})


@app.route('/api/test_twse')
def test_twse():
    import requests as _req
    try:
        r = _req.get('https://mis.twse.com.tw/stock/api/getStockInfo.jsp',
            params={'ex_ch': 'tse_2330.tw', 'json': '1', 'delay': '0'}, timeout=5, verify=False)
        d = r.json()
        return jsonify({'ok': True, 'data': d.get('msgArray', [{}])[0]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
@app.route('/api/reports')
def api_reports():
    reports = []
    if os.path.exists(config.REPORTS_DIR):
        files = sorted(os.listdir(config.REPORTS_DIR), reverse=True)[:10]
        for f in files:
            if f.endswith('.html'):
                import datetime
                mtime = os.path.getmtime(os.path.join(config.REPORTS_DIR, f))
                t = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                reports.append({'name': f, 'time': t})
    return jsonify({'reports': reports})

@app.route('/api/generate/<report_type>', methods=['POST'])
def generate_report(report_type):
    global _is_generating
    if _is_generating:
        return jsonify({'error': 'busy', 'message': '報表產生中，請稍後再試'}), 429
    import uuid
    job_id = str(uuid.uuid4())[:8]
    q = queue.Queue()
    progress_queues[job_id] = q
    _is_generating = True

    def run():
        try:
            from modules.report_scheduler import get_report_type, get_week_range
            from modules.ai_analyzer import (analyze_global_market, analyze_taiwan_market,
                                              analyze_macro_assets, analyze_watchlist_stock,
                                              get_sector_recommendations,
                                              analyze_weekly_global, analyze_weekly_taiwan,
                                              analyze_weekly_watchlist,
                                              analyze_watchlist_parallel)
            from modules.pdf_generator import generate_daily_report, generate_weekly_report
            from modules.email_sender import send_report, send_weekly_report
            from concurrent.futures import ThreadPoolExecutor

            def step(key, label=None):
                if not label:
                    label = key
                push(q, {'type':'step_start','key':key,'label':label,'pct':max(0,STEP_PCT.get(key,0)-5)})

            def done_step(key, label=None):
                if not label:
                    label = key
                push(q, {'type':'step_done','key':key,'label':label,'pct':STEP_PCT.get(key,0)})

            actual_type = get_report_type(force=None)
            from modules.report_scheduler import get_week_range
            monday, friday = get_week_range()
            week_range = f'{monday.strftime("%Y/%m/%d")} ~ {friday.strftime("%Y/%m/%d")}'

            # ── 所有資料來源同時平行抓取 ─────────────────────
            step('fetch_global', '抓取全球市場資料')
            step('fetch_taiwan', '抓取台股資料')
            step('fetch_news', '抓取財經新聞')

            with ThreadPoolExecutor(max_workers=5) as ex:
                f_global    = ex.submit(get_global_markets)
                f_commodity = ex.submit(get_commodities)
                f_taiwan    = ex.submit(get_taiwan_stocks)
                f_news      = ex.submit(get_financial_news)
                f_macro     = ex.submit(get_macro_assets)
                global_markets = f_global.result()
                commodities    = f_commodity.result()
                taiwan_stocks  = f_taiwan.result()
                news           = f_news.result()
                macro_data     = f_macro.result()

            done_step('fetch_global', '抓取全球市場資料')
            done_step('fetch_taiwan', '抓取台股資料')
            done_step('fetch_news', '抓取財經新聞')

            step('fetch_watchlist', '抓取持股追蹤資料')
            watchlist = get_watchlist()
            # 持股抓取與全局技術分析同時進行
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_watchlist_stocks = ex.submit(get_watchlist_stocks, watchlist) if watchlist else None
                watchlist_stocks = f_watchlist_stocks.result() if f_watchlist_stocks else {}
            done_step('fetch_watchlist', '抓取持股追蹤資料')

            step('technical', '進行技術分析')
            technical_results = analyze_all_stocks(taiwan_stocks)
            livermore_signals = analyze_all_signals(technical_results)
            for name, data in taiwan_stocks.items():
                if 'history' in data:
                    technical_results[name]['patterns'] = detect_patterns(data['history'])
            macro_analysis = analyze_macro_assets(macro_data)

            # 抓取大盤（台灣加權）技術數據，確保 AI 使用真實數字
            twii_data = None
            try:
                twii_hist = yf.Ticker('^TWII', session=curl_session).history(period='90d')
                if len(twii_hist) >= 60:
                    from modules.technical import analyze_stock
                    twii_stock_data = {
                        'price': round(twii_hist['Close'].iloc[-1], 2),
                        'change': round(((twii_hist['Close'].iloc[-1] - twii_hist['Close'].iloc[-2]) / twii_hist['Close'].iloc[-2]) * 100, 2),
                        'volume': int(twii_hist['Volume'].iloc[-1]),
                        'history': twii_hist
                    }
                    twii_data = analyze_stock(twii_stock_data)
            except Exception as e:
                print(f'大盤技術分析失敗: {e}')
            done_step('technical', '進行技術分析')

            step('ai_global', 'AI 分析全球市場')
            if actual_type == 'weekly':
                global_analysis = analyze_weekly_global(global_markets, commodities, news, macro_data, week_range)
            else:
                global_analysis = analyze_global_market(global_markets, commodities, news)
            done_step('ai_global', 'AI 分析全球市場')

            # ── AI 分析台股（先跑完，避免與持股分析搶 rate limit）──
            step('ai_taiwan', 'AI 分析台股')
            if actual_type == 'weekly':
                taiwan_analysis = analyze_weekly_taiwan(global_analysis, technical_results, livermore_signals, week_range, twii_data)
            else:
                taiwan_analysis = analyze_taiwan_market(global_analysis, technical_results, livermore_signals, twii_data)
            done_step('ai_taiwan', 'AI 分析台股')

            # ── AI 分析持股追蹤（分批執行）────────────────────────
            step('ai_watchlist', 'AI 分析持股追蹤')
            watch_tech = analyze_all_stocks(watchlist_stocks) if watchlist else {}
            if watchlist:
                watchlist_analysis = analyze_watchlist_parallel(
                    watchlist, watchlist_stocks, watch_tech, news,
                    week_range=week_range, is_weekly=(actual_type == 'weekly')
                )
            else:
                watchlist_analysis = []
            done_step('ai_watchlist', 'AI 分析持股追蹤')

            step('ai_sector', 'AI 分析產業投資方向')
            sector_recommendations = get_sector_recommendations(global_markets, technical_results, macro_data, watchlist_analysis)
            done_step('ai_sector', 'AI 分析產業投資方向')

            step('generate_pdf', '產生報表')
            if actual_type == 'daily':
                report_path = generate_daily_report(
                    global_markets, commodities, news,
                    global_analysis, taiwan_analysis,
                    technical_results, livermore_signals,
                    macro_data, macro_analysis,
                    watchlist_analysis, sector_recommendations
                )
            else:
                report_path = generate_weekly_report(
                    global_markets, commodities, news,
                    global_analysis, taiwan_analysis,
                    technical_results, livermore_signals,
                    macro_data, macro_analysis,
                    watchlist_analysis, sector_recommendations,
                    week_range
                )
            done_step('generate_pdf', '產生報表')

            step('send_email', '寄送 Email')
            if actual_type == 'daily':
                send_report(report_path)
            else:
                send_weekly_report(report_path)
            done_step('send_email', '寄送 Email')

            type_label = '日報' if actual_type == 'daily' else '週報'
            push(q, {'type':'done','message':f'✅ {type_label}已產生並寄送成功！'})

        except Exception as e:
            import traceback
            traceback.print_exc()
            push(q, {'type':'error','message':str(e)})
        finally:
            global _is_generating
            _is_generating = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'job_id': job_id})

if __name__ == '__main__':
    print('投資建議系統啟動中...')
    print('請開啟瀏覽器前往 http://localhost:5000')
    app.run(debug=False, host='0.0.0.0', port=5000)
