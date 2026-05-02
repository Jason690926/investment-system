/* ── Stock Detail ─────────────────────────────────────── */

let enrichedData = null;
let chart = null;
let candleSeries = null;
let volumeSeries = null;
let currentTF = 'daily';
let zoneSupport = null;
let zoneResistance = null;

/* ── Tabs ─────────────────────────────────────────────── */
function switchTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'chart') {
    if (enrichedData && !chart) buildChart();
    // 圖表顯示後才能計算座標，延遲一個 frame 再畫
    requestAnimationFrame(() => drawPriceZones());
  }
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
    const el = document.getElementById('d-change');
    el.innerHTML = `載入失敗：${e.message} <button class="btn btn-ghost btn-sm" onclick="loadMarketData()" style="margin-left:8px;">重試</button>`;
    el.className = 'detail-change down';
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
    drawPriceZones();
  });

  chart.timeScale().subscribeVisibleTimeRangeChange(drawPriceZones);

  chart.subscribeCrosshairMove(param => {
    const volEl = document.getElementById('d-vol');
    if (!volEl) return;
    if (!param.time) {
      if (enrichedData?.volume_zhang != null) volEl.textContent = `${enrichedData.volume_zhang} 張`;
      return;
    }
    const volData = param.seriesData.get(volumeSeries);
    if (volData !== undefined && volData !== null) {
      const val = typeof volData === 'object' ? volData.value : volData;
      volEl.textContent = val != null ? `${val} 張` : '—';
    }
  });

  updateChartData();
}

/* ── 支撐壓力色帶 ──────────────────────────────────────── */
function drawPriceZones() {
  const container = document.getElementById('chart-container');
  container.querySelectorAll('.zone-overlay').forEach(e => e.remove());
  if (!candleSeries || window.innerWidth < 768) return;
  if (!zoneSupport && !zoneResistance) return;

  const rightAxisWidth = 65;
  const w = container.offsetWidth - rightAxisWidth;

  function addZone(centerPrice, fillColor, borderColor) {
    if (!centerPrice) return;
    const yHigh = candleSeries.priceToCoordinate(centerPrice * 1.02);
    const yLow  = candleSeries.priceToCoordinate(centerPrice * 0.98);
    if (yHigh == null || yLow == null) return;
    const rawTop    = Math.min(yHigh, yLow);
    const rawBottom = rawTop + Math.max(Math.abs(yHigh - yLow), 6);
    // 限制在 chart container 範圍內，避免溢出蓋住上方 info row
    const chartH = container.offsetHeight;
    const top    = Math.max(0, rawTop);
    const bottom = Math.min(rawBottom, chartH);
    const height = bottom - top;
    if (height <= 0) return;
    const el = document.createElement('div');
    el.className = 'zone-overlay';
    el.style.cssText = `position:absolute;pointer-events:none;z-index:2;
      left:0;width:${w}px;top:${top}px;height:${height}px;
      background:${fillColor};
      border-top:1px dashed ${borderColor};
      border-bottom:1px dashed ${borderColor};`;
    container.appendChild(el);
  }

  addZone(zoneSupport,    'rgba(63,185,80,0.12)',  'rgba(63,185,80,0.8)');
  addZone(zoneResistance, 'rgba(248,81,73,0.12)',  'rgba(248,81,73,0.8)');
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

  // 根據 bar 數量動態調整成交量佔高比例，避免月K/週K 重疊
  const topMargin = bars.length <= 12 ? 0.88 : bars.length <= 26 ? 0.85 : 0.80;
  chart.priceScale('vol').applyOptions({ scaleMargins: { top: topMargin, bottom: 0 } });

  chart.timeScale().fitContent();

  const label = { daily: `日K（${bars.length}根）`, weekly: `週K（${bars.length}根）`, monthly: `月K（${bars.length}根）` };
  document.getElementById('chart-range-label').textContent = label[currentTF] || '';
}

/* ── Analysis ─────────────────────────────────────────── */
async function loadCachedAnalysis() {
  try {
    const res = await api(`/api/stocks/${STOCK_ID}/analysis`);
    if (res.cached) showAnalysis(res);
  } catch (e) { /* 無快取，保持預設按鈕狀態 */ }
}

function showAnalysis(res) {
  const area = document.getElementById('analysis-area');
  zoneSupport    = res.support    || null;
  zoneResistance = res.resistance || null;
  let riskHtml = '';
  if (res.risk_pct != null) {
    const rc = riskClass(res.risk_pct);
    riskHtml = `
    <div class="risk-summary">
      <div class="risk-box"><div class="label">風險係數</div><div class="value ${rc}">${res.risk_pct}%</div></div>
      ${res.support    ? `<div class="risk-box"><div class="label">關鍵支撐</div><div class="value up">${res.support} 元</div></div>` : ''}
      ${res.resistance ? `<div class="risk-box"><div class="label">關鍵壓力</div><div class="value down">${res.resistance} 元</div></div>` : ''}
      ${res.target_pnf ? `<div class="risk-box"><div class="label">P&F概念目標</div><div class="value" style="color:var(--purple)">${res.target_pnf} 元</div></div>` : ''}
      ${res.wyckoff_phase ? `<div class="risk-box"><div class="label">威科夫階段</div><div class="value" style="font-size:16px;color:var(--blue)">${res.wyckoff_phase}</div></div>` : ''}
    </div>
    ${res.generated_at ? `<p style="font-size:12px;color:var(--muted);margin-bottom:12px;">今日分析 ${res.generated_at} · <button class="btn btn-ghost btn-sm" onclick="runAnalysis()">重新分析</button></p>` : ''}`;
  }

  const recommendTitle = STOCK_STATUS === 'holding' ? '📌 持股操作建議' : '🎯 進場時機建議';
  area.innerHTML = riskHtml +
    `<div id="analysis-content">${res.html}</div>` +
    `<div class="recommend-section">
       <div class="recommend-header">
         <div class="recommend-title">${recommendTitle}</div>
       </div>
       <div id="recommend-content" class="loading">
         <div class="spinner"></div> 產生個人化建議中…
       </div>
     </div>`;

  loadRecommendation();
}

async function loadRecommendation() {
  const el = document.getElementById('recommend-content');
  if (!el) return;
  try {
    const res = await api(`/api/stocks/${STOCK_ID}/recommend`, { method: 'POST' });
    el.innerHTML = res.html;
    el.className = 'recommend-content';
  } catch (e) {
    el.innerHTML = `<p style="color:var(--muted);font-size:13px;">建議載入失敗：${e.message}
      <button class="btn btn-ghost btn-sm" style="margin-left:8px;" onclick="loadRecommendation()">重試</button></p>`;
    el.className = 'recommend-content';
  }
}

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

    showAnalysis(res);
  } catch (e) {
    area.innerHTML = `<div class="analysis-trigger">
      <p style="color:var(--red)">分析失敗：${e.message}</p>
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

/* ── 交易記錄管理 ──────────────────────────────────────── */
async function loadTrades() {
  if (STOCK_STATUS !== 'holding') return;
  const list = document.getElementById('trades-list');
  try {
    const data = await api(`/api/stocks/${STOCK_ID}/trades`);
    if (!data.trades.length) {
      list.innerHTML = '<p style="color:var(--muted);font-size:13px;">尚無交易記錄</p>';
      return;
    }
    list.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="color:var(--muted);font-size:12px;">
            <th style="text-align:left;padding:6px 8px;">買入價</th>
            <th style="text-align:right;padding:6px 8px;">張數</th>
            <th style="text-align:right;padding:6px 8px;">日期</th>
            <th style="padding:6px 8px;"></th>
          </tr>
        </thead>
        <tbody>
          ${data.trades.map(t => `
          <tr style="border-top:1px solid var(--border);">
            <td style="padding:8px;">${t.buy_price} 元</td>
            <td style="padding:8px;text-align:right;">${t.quantity_zhang} 張</td>
            <td style="padding:8px;text-align:right;color:var(--muted);">${t.buy_date || '—'}</td>
            <td style="padding:8px;text-align:right;">
              <button class="btn btn-ghost btn-sm" onclick="openTradeModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">編輯</button>
              <button class="btn btn-sm" style="background:rgba(248,81,73,.15);color:var(--red);border:1px solid var(--red);" onclick="confirmDeleteTrade(${t.id})">刪</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>`;
    const summary = document.getElementById('trades-summary');
    if (summary) summary.textContent = `合計 ${data.total_zhang} 張　均成本 ${data.avg_cost ?? '—'} 元`;
  } catch (e) {
    list.innerHTML = `<p style="color:var(--red);">${e.message}</p>`;
  }
}

function openTradeModal(trade) {
  document.getElementById('trade-modal-title').textContent = trade ? '編輯交易' : '新增交易';
  document.getElementById('t-trade-id').value   = trade ? trade.id : '';
  document.getElementById('t-buy-price').value  = trade ? trade.buy_price : '';
  document.getElementById('t-quantity').value   = trade ? trade.quantity_zhang : '';
  document.getElementById('t-buy-date').value   = trade ? (trade.buy_date || '') : '';
  document.getElementById('trade-modal').classList.add('open');
}
function closeTradeModal() {
  document.getElementById('trade-modal').classList.remove('open');
}
document.getElementById('trade-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeTradeModal();
});

async function submitTrade() {
  const tradeId = document.getElementById('t-trade-id').value;
  const price   = parseFloat(document.getElementById('t-buy-price').value);
  const qty     = parseFloat(document.getElementById('t-quantity').value);
  const dt      = document.getElementById('t-buy-date').value;
  if (!qty || qty <= 0) { toast('請填入張數', 'error'); return; }

  try {
    if (tradeId) {
      await api(`/api/trades/${tradeId}`, {
        method: 'PUT',
        body: JSON.stringify({ quantity_zhang: qty, buy_price: price || undefined, buy_date: dt || undefined }),
      });
      toast('交易記錄已更新');
    } else {
      await api('/api/stocks/trade', {
        method: 'POST',
        body: JSON.stringify({ stock_id: STOCK_ID, buy_price: price, quantity_zhang: qty, buy_date: dt || undefined }),
      });
      toast('交易記錄已新增');
    }
    closeTradeModal();
    loadTrades();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function confirmDeleteTrade(tradeId) {
  if (!confirm('確定刪除這筆交易記錄？')) return;
  try {
    await api(`/api/trades/${tradeId}`, { method: 'DELETE' });
    toast('已刪除');
    loadTrades();
  } catch (e) {
    toast(e.message, 'error');
  }
}

loadMarketData();
loadCachedAnalysis();
if (STOCK_STATUS === 'holding') loadTrades();
