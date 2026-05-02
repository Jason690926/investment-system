/* ── Dashboard ────────────────────────────────────────── */

let allStocks = [];
let currentFilter = 'all';

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
    grid.innerHTML = `<div class="empty-state"><div class="icon">📊</div><p>尚無${currentFilter === 'watching' ? '觀察' : currentFilter === 'holding' ? '持有' : ''}股票，點右上角新增</p></div>`;
    return;
  }
  grid.innerHTML = filtered.map(buildCard).join('');
}

function buildCard(s) {
  const riskPct     = s.risk_pct  ?? null;
  const wyckoff     = s.wyckoff_phase ?? '';
  const badgeCls    = s.status === 'holding' ? 'badge-holding' : 'badge-watching';
  const badgeText   = s.status === 'holding' ? '已持有' : '觀察中';
  const isAnalyzed  = riskPct != null;

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

  const wyckoffTag = wyckoff
    ? `<div class="wyckoff-tag">⬡ ${wyckoff}</div>`
    : '';

  return `
  <div class="stock-card${isAnalyzed ? ' analyzed' : ''}" data-stock-id="${s.id}" onclick="location.href='/stock/${s.id}'">
    <span class="badge ${badgeCls}">${badgeText}</span>
    <div class="card-row1">
      <div>
        <div class="card-name">${s.name}</div>
        <div class="card-symbol">${s.symbol}</div>
        ${wyckoffTag}
      </div>
      <div class="card-price-block">
        <div class="card-price">—</div>
        <div class="card-change flat">—</div>
      </div>
    </div>
    <hr class="card-divider">
    <div class="card-row2">
      ${riskBar}
      ${metaHtml}
    </div>
    ${isAnalyzed ? '<div class="analyzed-badge">✦ 已分析</div>' : ''}
  </div>`;
}

/* ── 一鍵分析所有股票 ─────────────────────────────────── */
async function analyzeAll() {
  const btn      = document.getElementById('btn-analyze-all');
  const progress = document.getElementById('analyze-progress');
  const stocks   = [...allStocks];
  if (!stocks.length) { toast('尚無股票', 'error'); return; }

  btn.disabled = true;
  progress.style.display = 'flex';
  let done = 0;

  for (const stock of stocks) {
    progress.innerHTML = `<div class="spinner" style="width:14px;height:14px;border-width:2px;flex-shrink:0"></div>分析中 ${done}/${stocks.length}：${stock.name}`;
    try {
      const res = await api(`/api/stocks/${stock.id}/analyze`, { method: 'POST' });
      done++;
      const idx = allStocks.findIndex(s => s.id === stock.id);
      if (idx >= 0) {
        allStocks[idx].risk_pct      = res.risk_pct;
        allStocks[idx].wyckoff_phase = res.wyckoff_phase;
      }
      markCardAnalyzed(stock.id, res.risk_pct, res.wyckoff_phase);
    } catch { done++; }
  }

  progress.innerHTML = `<span style="color:var(--green);font-weight:700;">✓ 分析完成（${stocks.length} 支）</span>`;
  btn.disabled = false;
  setTimeout(() => { progress.style.display = 'none'; }, 3500);
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
    const wy = card.querySelector('.wyckoff-tag');
    if (wy) wy.textContent = `⬡ ${wyckoffPhase}`;
    else {
      card.querySelector('.card-symbol')
          ?.insertAdjacentHTML('afterend', `<div class="wyckoff-tag">⬡ ${wyckoffPhase}</div>`);
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
