/* ── Stock Detail ─────────────────────────────────────── */

let enrichedData = null;
let chart = null;
let candleSeries = null;
let volumeSeries = null;
let currentTF = 'daily';

/* ── Tabs ─────────────────────────────────────────────── */
function switchTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'chart' && enrichedData && !chart) buildChart();
}

/* ── Timeframe ────────────────────────────────────────── */
function switchTF(tf, btn) {
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentTF = tf;
  if (enrichedData) updateChartData();
}

/* ── Load Market Data ─────────────────────────────────── */
async function loadMarketData() {
  try {
    const data = await api(`/api/market/${STOCK_SYMBOL}/data`);
    enrichedData = data;
    updateHeader(data);
    updateInfoRow(data);
    buildChart();
  } catch (e) {
    document.getElementById('d-change').textContent = '資料載入失敗';
    console.error(e);
  }
}

function updateHeader(d) {
  document.getElementById('d-price').textContent = d.price ? `${d.price} 元` : '—';

  if (d.daily_bars && d.daily_bars.length >= 2) {
    const last  = d.daily_bars[d.daily_bars.length - 1];
    const prev  = d.daily_bars[d.daily_bars.length - 2];
    const chgPct = prev.close ? ((last.close - prev.close) / prev.close * 100) : null;
    const { text, cls } = formatChange(chgPct);
    const el = document.getElementById('d-change');
    el.textContent = text;
    el.className = 'detail-change ' + cls;
  }

  if (AVG_COST && d.price) {
    const pnl = (d.price - AVG_COST) / AVG_COST * 100;
    const { text, cls } = formatChange(pnl);
    const pnlEl = document.getElementById('d-pnl');
    if (pnlEl) { pnlEl.textContent = text; pnlEl.className = 'info-value ' + cls; }
  }
}

function updateInfoRow(d) {
  const set = (id, val, suffix = '') => {
    const el = document.getElementById(id);
    if (el) el.textContent = val != null ? `${val}${suffix}` : '—';
  };
  set('d-ma5',  d.ma5,  ' 元');
  set('d-ma20', d.ma20, ' 元');
  set('d-ma60', d.ma60, ' 元');

  const hist = d.macd?.histogram;
  const macdEl = document.getElementById('d-macd');
  if (macdEl && hist != null) {
    macdEl.textContent = hist > 0 ? `+${hist}` : `${hist}`;
    macdEl.className = 'info-value ' + (hist > 0 ? 'up' : hist < 0 ? 'down' : 'flat');
  }
  set('d-vol',  d.volume_zhang,       ' 張');
  set('d-vol5', d.volume_5d_avg_zhang,' 張');
}

/* ── Chart ────────────────────────────────────────────── */
function buildChart() {
  const container = document.getElementById('chart-container');
  if (!container || chart) return;

  chart = LightweightCharts.createChart(container, {
    layout:    { background: { color: '#161b22' }, textColor: '#8b949e' },
    grid:      { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#30363d' },
    timeScale: { borderColor: '#30363d', timeVisible: true },
    width:  container.offsetWidth,
    height: container.offsetHeight,
  });

  candleSeries = chart.addCandlestickSeries({
    upColor:   '#3fb950', downColor: '#f85149',
    borderUpColor: '#3fb950', borderDownColor: '#f85149',
    wickUpColor:   '#3fb950', wickDownColor:   '#f85149',
  });

  volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'vol',
  });
  chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

  window.addEventListener('resize', () => {
    chart.applyOptions({ width: container.offsetWidth });
  });

  updateChartData();
}

function updateChartData() {
  if (!enrichedData || !candleSeries) return;

  const bars = currentTF === 'weekly'  ? enrichedData.weekly_bars
             : currentTF === 'monthly' ? enrichedData.monthly_bars
             :                           enrichedData.daily_bars;

  if (!bars || bars.length === 0) return;

  const candles = bars.map(b => ({
    time:  b.date,
    open:  b.open,
    high:  b.high,
    low:   b.low,
    close: b.close,
  }));
  const volumes = bars.map((b, i) => ({
    time:  b.date,
    value: b.volume_zhang || 0,
    color: b.close >= b.open ? 'rgba(63,185,80,.4)' : 'rgba(248,81,73,.4)',
  }));

  candleSeries.setData(candles);
  volumeSeries.setData(volumes);
  chart.timeScale().fitContent();

  const label = { daily: `日K（${bars.length}根）`, weekly: `週K（${bars.length}根）`, monthly: `月K（${bars.length}根）` };
  document.getElementById('chart-range-label').textContent = label[currentTF] || '';
}

/* ── Analysis ─────────────────────────────────────────── */
async function runAnalysis() {
  const area = document.getElementById('analysis-area');
  area.innerHTML = '<div class="loading"><div class="spinner"></div> 三宗師分析中，約需 20-40 秒…</div>';

  try {
    const res = await api(`/api/stocks/${STOCK_ID}/analyze`, { method: 'POST' });

    let riskHtml = '';
    if (res.risk_pct != null) {
      const rc = riskClass(res.risk_pct);
      riskHtml = `
      <div class="risk-summary">
        <div class="risk-box">
          <div class="label">風險係數</div>
          <div class="value ${rc}">${res.risk_pct}%</div>
        </div>
        ${res.support    ? `<div class="risk-box"><div class="label">關鍵支撐</div><div class="value up">${res.support} 元</div></div>` : ''}
        ${res.resistance ? `<div class="risk-box"><div class="label">關鍵壓力</div><div class="value down">${res.resistance} 元</div></div>` : ''}
        ${res.target_pnf ? `<div class="risk-box"><div class="label">P&F概念目標</div><div class="value" style="color:var(--purple)">${res.target_pnf} 元</div></div>` : ''}
        ${res.wyckoff_phase ? `<div class="risk-box"><div class="label">威科夫階段</div><div class="value" style="font-size:16px;color:var(--blue)">${res.wyckoff_phase}</div></div>` : ''}
      </div>`;
    }

    area.innerHTML = riskHtml + `<div id="analysis-content">${res.html}</div>`;
  } catch (e) {
    area.innerHTML = `<div class="analysis-trigger"><p style="color:var(--red)">分析失敗：${e.message}</p>
      <button class="btn btn-ghost" onclick="runAnalysis()">重試</button></div>`;
  }
}

/* ── Delete ───────────────────────────────────────────── */
async function confirmDelete() {
  if (!confirm(`確定要刪除「${STOCK_NAME}」嗎？此操作不可恢復。`)) return;
  try {
    await api('/api/stocks/remove', { method: 'POST', body: JSON.stringify({ stock_id: STOCK_ID }) });
    toast(`${STOCK_NAME} 已刪除`);
    setTimeout(() => location.href = '/dashboard', 800);
  } catch (e) {
    toast(e.message, 'error');
  }
}

loadMarketData();
