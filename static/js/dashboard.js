/* ── Dashboard ────────────────────────────────────────── */

let allStocks = [];
let currentFilter = 'all';
let isAnalyzing  = false;

async function loadStocks() {
  const grid = document.getElementById('stock-grid');
  grid.innerHTML = '<div class="loading"><div class="spinner"></div> 載入中…</div>';
  try {
    allStocks = await api('/api/stocks');
    renderGrid();
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>${e.message}</p></div>`;
  }
}

function renderGrid() {
  const grid = document.getElementById('stock-grid');
  const holding  = allStocks.filter(s => s.status === 'holding');
  const watching  = allStocks.filter(s => s.status === 'watching');

  document.getElementById('cnt-all').textContent     = allStocks.length;
  document.getElementById('cnt-holding').textContent  = holding.length;
  document.getElementById('cnt-watching').textContent = watching.length;

  const filtered = currentFilter === 'all'     ? allStocks
                 : currentFilter === 'holding'  ? holding
                 : watching;

  if (filtered.length === 0) {
    grid.style.gridTemplateColumns = '';
    grid.style.removeProperty('--card-min-h');
    grid.innerHTML = `<div class="empty-state"><div class="icon">📊</div><p>尚無${currentFilter === 'watching' ? '觀察' : currentFilter === 'holding' ? '持有' : ''}股票，點右上角新增</p></div>`;
    return;
  }
  adjustGridLayout(grid, filtered.length);
  grid.innerHTML = filtered.map(buildCard).join('');
  loadCardPrices(filtered);
}

function adjustGridLayout(grid, count) {
  /* 依顯示中的股票數，動態決定欄寬與卡片最低高度 */
  let minCol, minH;
  if      (count <= 2) { minCol = '520px'; minH = '300px'; }
  else if (count <= 4) { minCol = '420px'; minH = '260px'; }
  else if (count <= 6) { minCol = '360px'; minH = '220px'; }
  else if (count <= 9) { minCol = '300px'; minH = '195px'; }
  else                 { minCol = '260px'; minH = '175px'; }
  grid.style.gridTemplateColumns = `repeat(auto-fill, minmax(${minCol}, 1fr))`;
  grid.style.setProperty('--card-min-h', minH);
}

function wyckoffBadgeCls(phase) {
  if (!phase) return 'wyckoff-none';
  const bull = ['上漲', '積累', '再積累'];
  const bear = ['派發', '下跌', '再派發'];
  if (bull.some(p => phase.includes(p))) return 'wyckoff-bull';
  if (bear.some(p => phase.includes(p))) return 'wyckoff-bear';
  return 'wyckoff-neutral';
}

function buildCard(s) {
  const riskPct    = s.risk_pct  ?? null;
  const wyckoff    = s.wyckoff_phase ?? '';
  const badgeCls   = s.status === 'holding' ? 'badge-holding' : 'badge-watching';
  const badgeText  = s.status === 'holding' ? '已持有' : '觀察中';
  const isAnalyzed = riskPct != null;

  const riskBar = riskPct != null ? `
    <div class="risk-block">
      <div class="risk-label">
        風險係數 <span class="${riskClass(riskPct)}">${riskPct}%</span>
      </div>
      <div class="risk-bar">
        <div class="risk-fill ${riskClass(riskPct)}" style="width:${riskPct}%"></div>
      </div>
    </div>` : `<div class="risk-block" style="color:var(--muted);font-size:12px;">尚未分析</div>`;

  let metaHtml = '';
  if (s.status === 'holding') {
    metaHtml = `<div class="card-meta">
      <div>${s.total_zhang ?? '--'} 張</div>
      ${s.avg_cost ? `<div>成本 <strong>${s.avg_cost}</strong></div>` : ''}
    </div>`;
  }

  const wyckoffBadge = wyckoff
    ? `<div class="wyckoff-badge ${wyckoffBadgeCls(wyckoff)}">${wyckoff}</div>`
    : `<div class="wyckoff-badge wyckoff-none"></div>`;

  return `
  <div class="stock-card${isAnalyzed ? ' analyzed' : ''}" data-stock-id="${s.id}" onclick="openStockPage(${s.id})">
    <span class="badge ${badgeCls}">${badgeText}</span>
    <div class="card-row1">
      <div>
        <div class="card-name">${s.name}</div>
        <div class="card-symbol">${s.symbol}</div>
        ${wyckoffBadge}
      </div>
      <div class="card-price-block">
        <div class="card-price card-price-val">—</div>
        <div class="card-change flat">—</div>
      </div>
    </div>
    <div class="card-ohlc">
      <span class="ohlc-item">開 <strong class="ohlc-o">—</strong></span>
      <span class="ohlc-item">高 <strong class="ohlc-h">—</strong></span>
      <span class="ohlc-item">低 <strong class="ohlc-l">—</strong></span>
      <span class="ohlc-item">收 <strong class="ohlc-c">—</strong></span>
    </div>
    <hr class="card-divider">
    <div class="card-row2">
      ${riskBar}
      ${metaHtml}
    </div>
    ${isAnalyzed ? '<div class="analyzed-badge">✦ 已分析</div>' : ''}
  </div>`;
}

/* ── 非同步抓各卡片行情（輕量 /quote 端點）──────────────── */
async function loadCardPrices(stocks) {
  await Promise.all(stocks.map(s =>
    api(`/api/market/${encodeURIComponent(s.symbol)}/quote`)
      .then(d => updateCardPrice(s.id, d))
      .catch(() => {})
  ));
}

function updateCardPrice(stockId, q) {
  const card = document.querySelector(`[data-stock-id="${stockId}"]`);
  if (!card) return;

  // 收盤價
  const priceEl = card.querySelector('.card-price-val');
  if (priceEl) priceEl.textContent = q.close != null ? `${q.close}` : '—';

  // 漲跌幅
  const changeEl = card.querySelector('.card-change');
  if (changeEl && q.prev_close && q.close != null) {
    const chg = (q.close - q.prev_close) / q.prev_close * 100;
    const { text, cls } = formatChange(chg);
    changeEl.textContent = text;
    changeEl.className = 'card-change ' + cls;
  }

  // OHLC 四格
  const set = (sel, val, cls) => {
    const el = card.querySelector(sel);
    if (!el) return;
    el.textContent = val ?? '—';
    if (cls) el.className = cls;
  };
  set('.ohlc-o', q.open);
  set('.ohlc-h', q.high,  'up');
  set('.ohlc-l', q.low,   'down');
  set('.ohlc-c', q.close);
}

/* ── 一鍵分析所有股票（3 並行 worker pool）──────────────── */
async function analyzeAll() {
  const CONCURRENCY = 3;
  const btn      = document.getElementById('btn-analyze-all');
  const progress = document.getElementById('analyze-progress');
  const stocks   = [...allStocks];
  if (!stocks.length) { toast('尚無股票', 'error'); return; }

  btn.disabled = true;
  isAnalyzing  = true;
  progress.style.display = 'flex';

  const queue   = [...stocks];
  const inFlight = new Set();
  let done = 0;
  let cached = 0;

  function renderProgress() {
    const names = [...inFlight].join(' · ');
    const cachedNote = cached > 0 ? ` <span style="color:var(--muted);font-size:11px;">（${cached} 支快取）</span>` : '';
    progress.innerHTML =
      `<div class="spinner" style="width:14px;height:14px;border-width:2px;flex-shrink:0"></div>` +
      `分析中 ${done}/${stocks.length}${cachedNote}` +
      (names ? ` ▸ <span style="color:var(--blue)">${names}</span>` : '');
  }

  async function worker() {
    while (true) {
      const stock = queue.shift();
      if (!stock) break;
      inFlight.add(stock.name);
      renderProgress();
      try {
        const res = await api(`/api/stocks/${stock.id}/analyze`, { method: 'POST' });
        if (res.from_cache) cached++;
        done++;
        const idx = allStocks.findIndex(s => s.id === stock.id);
        if (idx >= 0) {
          allStocks[idx].risk_pct      = res.risk_pct;
          allStocks[idx].wyckoff_phase = res.wyckoff_phase;
        }
        markCardAnalyzed(stock.id, res.risk_pct, res.wyckoff_phase);
      } catch { done++; }
      inFlight.delete(stock.name);
      renderProgress();
    }
  }

  // 同時啟動 CONCURRENCY 個 worker，共用同一個 queue
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  isAnalyzing = false;
  const cacheMsg = cached > 0 ? `，其中 ${cached} 支來自快取` : '';
  progress.innerHTML = `<span style="color:var(--green);font-weight:700;">✓ 分析完成（${stocks.length} 支${cacheMsg}）</span>`;
  btn.disabled = false;
  setTimeout(() => { progress.style.display = 'none'; }, 3500);
}

/* ── 股票卡片導航（分析中改開新分頁，避免中斷）─────────── */
function openStockPage(stockId) {
  if (isAnalyzing) {
    window.open(`/stock/${stockId}`, '_blank');
  } else {
    location.href = `/stock/${stockId}`;
  }
}

function markCardAnalyzed(stockId, riskPct, wyckoffPhase) {
  const card = document.querySelector(`[data-stock-id="${stockId}"]`);
  if (!card) return;
  card.classList.add('analyzed');

  if (riskPct != null) {
    const rc = riskClass(riskPct);
    const rb = card.querySelector('.risk-block');
    if (rb) rb.innerHTML = `
      <div class="risk-label">風險係數 <span class="${rc}">${riskPct}%</span></div>
      <div class="risk-bar"><div class="risk-fill ${rc}" style="width:${riskPct}%"></div></div>`;
  }
  if (wyckoffPhase) {
    const wb = card.querySelector('.wyckoff-badge');
    if (wb) {
      wb.textContent = wyckoffPhase;
      wb.className = `wyckoff-badge ${wyckoffBadgeCls(wyckoffPhase)}`;
    } else {
      card.querySelector('.card-symbol')
          ?.insertAdjacentHTML('afterend',
            `<div class="wyckoff-badge ${wyckoffBadgeCls(wyckoffPhase)}">${wyckoffPhase}</div>`);
    }
  }
  if (!card.querySelector('.analyzed-badge')) {
    const b = document.createElement('div');
    b.className = 'analyzed-badge';
    b.textContent = '✦ 已分析';
    card.appendChild(b);
  }
}

/* ── Filter ───────────────────────────────────────────── */
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    currentFilter = chip.dataset.filter;
    renderGrid();
  });
});

/* ── Symbol 自動帶入名稱 ──────────────────────────────── */
let symbolTimer = null;
document.getElementById('f-symbol').addEventListener('input', function () {
  clearTimeout(symbolTimer);
  const raw = this.value.trim().toUpperCase();
  if (!raw) return;
  symbolTimer = setTimeout(async () => {
    // 純數字自動補 .TW
    const symbol = /^\d+$/.test(raw) ? raw + '.TW' : raw;
    if (symbol !== raw) this.value = symbol;

    const nameEl = document.getElementById('f-name');
    nameEl.placeholder = '查詢中…';
    try {
      const info = await api(`/api/market/${encodeURIComponent(symbol)}/info`);
      if (info.name) nameEl.value = info.name;
      nameEl.placeholder = info.name || '找不到名稱';
    } catch {
      nameEl.placeholder = '找不到此代號';
    }
  }, 600);
});

/* ── Add Modal ────────────────────────────────────────── */
function openAddModal() {
  document.getElementById('add-modal').classList.add('open');
}
function closeAddModal() {
  document.getElementById('add-modal').classList.remove('open');
  ['f-symbol','f-name','f-buy-price','f-quantity','f-buy-date'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  setStatus('watching');
}

function setStatus(val) {
  document.querySelectorAll('input[name="status"]').forEach(r => r.checked = r.value === val);
  document.getElementById('rl-watching').classList.toggle('selected', val === 'watching');
  document.getElementById('rl-holding').classList.toggle('selected', val === 'holding');
  document.getElementById('holding-fields').style.display = val === 'holding' ? '' : 'none';
}

document.querySelectorAll('input[name="status"]').forEach(r => {
  r.addEventListener('change', () => setStatus(r.value));
});
document.querySelectorAll('.radio-label').forEach(label => {
  label.addEventListener('click', () => {
    const val = label.querySelector('input').value;
    setStatus(val);
  });
});

async function submitAddStock() {
  const raw    = document.getElementById('f-symbol').value.trim().toUpperCase();
  const symbol = /^\d+$/.test(raw) ? raw + '.TW' : raw;
  document.getElementById('f-symbol').value = symbol;
  const name   = document.getElementById('f-name').value.trim();
  const status = document.querySelector('input[name="status"]:checked').value;
  if (!symbol || !name) { toast('請填入代號和名稱', 'error'); return; }

  const body = { symbol, name, status };
  if (status === 'holding') {
    const bp = parseFloat(document.getElementById('f-buy-price').value);
    const qt = parseFloat(document.getElementById('f-quantity').value);
    const dt = document.getElementById('f-buy-date').value;
    if (bp) body.buy_price = bp;
    if (qt) body.quantity_zhang = qt;
    if (dt) body.buy_date = dt;
  }
  try {
    await api('/api/stocks/add', { method: 'POST', body: JSON.stringify(body) });
    toast(`${name} 新增成功`);
    closeAddModal();
    loadStocks();
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* 點擊 overlay 外部關閉 */
document.getElementById('add-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeAddModal();
});

loadStocks();
