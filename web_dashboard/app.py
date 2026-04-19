from flask import Flask, request, jsonify
import threading, os, sys
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
.progress-wrap{background:white;border-radius:8px;padding:16px;border:1px solid #e0e0e0;margin-bottom:16px;display:none}
.progress-bar{height:6px;background:#e0e0e0;border-radius:3px;margin:8px 0}
.progress-fill{height:100%;background:#1a237e;border-radius:3px;transition:width .3s}
.status-msg{font-size:13px;color:#666}
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

  <div id="progress-wrap" class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="pbar" style="width:0%"></div></div>
    <div class="status-msg" id="status-msg">處理中...</div>
  </div>

  <div class="btn-grid">
    <div class="btn-card">
      <h4>每日晨報</h4>
      <p>全球財經 + 美債/黃金/石油 + 持股追蹤 + AI分析</p>
      <button class="btn btn-blue" onclick="generate('daily')">立即產生並寄送</button>
    </div>
    <div class="btn-card">
      <h4>週報總結</h4>
      <p>本週回顧 + 下週標的建議</p>
      <button class="btn btn-teal" onclick="generate('weekly')">立即產生並寄送</button>
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
      <thead><tr><th>股票</th><th>代號</th><th>現價</th><th>漲跌</th><th>成本</th><th>持股數</th><th>損益</th><th>操作</th></tr></thead>
      <tbody id="watchlist-body"><tr><td colspan="8" style="text-align:center;color:#888;padding:16px">載入中...</td></tr></tbody>
    </table>
  </div>

  <div class="section">
    <h3>最近產生紀錄</h3>
    <div id="report-list"><div style="color:#888;font-size:13px">載入中...</div></div>
  </div>

</div>
<script>
function showMsg(text, ok) {
  const el = document.getElementById('msg');
  el.textContent = text;
  el.className = 'msg ' + (ok ? 'msg-ok' : 'msg-err');
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 4000);
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
  const data = {
    symbol: symbol,
    name: document.getElementById('f-name').value.trim() || symbol,
    cost: document.getElementById('f-cost').value || null,
    shares: document.getElementById('f-shares').value || null,
    buy_date: document.getElementById('f-date').value || null
  };
  fetch('/api/watchlist/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
    .then(r=>r.json()).then(d=>{
      showMsg(d.message, d.success);
      if (d.success) {
        document.getElementById('f-symbol').value = '';
        document.getElementById('f-name').value = '';
        document.getElementById('f-cost').value = '';
        document.getElementById('f-shares').value = '';
        document.getElementById('f-date').value = '';
        updateWatchlist();
      }
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

function generate(type) {
  const wrap = document.getElementById('progress-wrap');
  if (wrap.style.display !== 'none') return;
  wrap.style.display = 'block';
  document.getElementById('pbar').style.width = '15%';
  document.getElementById('status-msg').textContent = '正在處理，約需 1-2 分鐘...';
  fetch('/api/generate/' + type, {method:'POST'}).then(r=>r.json()).then(d=>{
    document.getElementById('pbar').style.width = '100%';
    document.getElementById('status-msg').textContent = d.message;
    setTimeout(() => {
      wrap.style.display = 'none';
      document.getElementById('pbar').style.width = '0%';
      updateReports();
    }, 3000);
  });
}

updateWatchlist();
updateReports();
</script>
</body></html>'''

@app.route('/')
def index():
    return DASHBOARD

@app.route('/api/watchlist')
def api_watchlist():
    watchlist = get_watchlist()
    stocks = []
    for item in watchlist:
        try:
            ticker = yf.Ticker(item['symbol'])
            hist = ticker.history(period='2d')
            price, change = None, 0
            if len(hist) >= 2:
                price = round(hist['Close'].iloc[-1], 2)
                prev = hist['Close'].iloc[-2]
                change = round(((price - prev) / prev) * 100, 2)
        except:
            price, change = None, 0
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

@app.route('/api/generate/daily', methods=['POST'])
def generate_daily():
    forced_type = None
    def run():
        try:
            from modules.report_scheduler import get_report_type, get_week_range
            from modules.ai_analyzer import (analyze_global_market, analyze_taiwan_market,
                                              analyze_macro_assets, analyze_watchlist_stock,
                                              get_sector_recommendations,
                                              analyze_weekly_global, analyze_weekly_taiwan,
                                              analyze_weekly_watchlist)
            from modules.pdf_generator import generate_daily_report, generate_weekly_report
            from modules.email_sender import send_report, send_weekly_report

            report_type = get_report_type(force=forced_type)
            monday, friday = get_week_range()
            week_range = f'{monday.strftime("%Y/%m/%d")} ~ {friday.strftime("%Y/%m/%d")}'

            global_markets = get_global_markets()
            commodities = get_commodities()
            news = get_financial_news()
            macro_data = get_macro_assets()
            taiwan_stocks = get_taiwan_stocks()
            technical_results = analyze_all_stocks(taiwan_stocks)
            livermore_signals = analyze_all_signals(technical_results)
            for name, data in taiwan_stocks.items():
                if 'history' in data:
                    technical_results[name]['patterns'] = detect_patterns(data['history'])
            macro_analysis = analyze_macro_assets(macro_data)

            watchlist = get_watchlist()
            watchlist_analysis = []
            if watchlist:
                watchlist_stocks = get_watchlist_stocks(watchlist)
                watch_tech = analyze_all_stocks(watchlist_stocks)
                for item in watchlist:
                    name = item['name']
                    symbol = item['symbol']
                    if name in watch_tech:
                        tech = watch_tech[name]
                        hist = watchlist_stocks[name].get('history')
                        patterns = detect_patterns(hist) if hist is not None else []
                        stock_news = [n for n in news if name in n.get('title', '')]
                        if report_type == 'weekly':
                            ai_advice = analyze_weekly_watchlist(name, symbol, tech, patterns, stock_news, week_range, item.get('cost'))
                        else:
                            ai_advice = analyze_watchlist_stock(name, symbol, tech, patterns, stock_news, item.get('cost'))
                        tech['cost'] = item.get('cost')
                        watchlist_analysis.append({'name': name, 'symbol': symbol, 'technical': tech, 'patterns': patterns, 'ai_advice': ai_advice})

            sector_recommendations = get_sector_recommendations(global_markets, technical_results, macro_data)

            if report_type == 'daily':
                global_analysis = analyze_global_market(global_markets, commodities, news)
                taiwan_analysis = analyze_taiwan_market(global_analysis, technical_results, livermore_signals)
                report_path = generate_daily_report(
                    global_markets, commodities, news,
                    global_analysis, taiwan_analysis,
                    technical_results, livermore_signals,
                    macro_data, macro_analysis,
                    watchlist_analysis, sector_recommendations
                )
                send_report(report_path)
            else:
                global_weekly = analyze_weekly_global(global_markets, commodities, news, macro_data, week_range)
                taiwan_weekly = analyze_weekly_taiwan(global_weekly, technical_results, livermore_signals, week_range)
                report_path = generate_weekly_report(
                    global_markets, commodities, news,
                    global_weekly, taiwan_weekly,
                    technical_results, livermore_signals,
                    macro_data, macro_analysis,
                    watchlist_analysis, sector_recommendations,
                    week_range
                )
                send_weekly_report(report_path)
        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()
    threading.Thread(target=run).start()
    return jsonify({'message': '報表產生中，系統自動判斷日報或週報，完成後寄送 Email！約需 1-2 分鐘。'})

@app.route('/api/generate/weekly', methods=['POST'])
def generate_weekly():
    return jsonify({'message': '週報功能即將完成！'})

if __name__ == '__main__':
    print('投資建議系統啟動中...')
    print('請開啟瀏覽器前往 http://localhost:5000')
    app.run(debug=False, host='0.0.0.0', port=5000)