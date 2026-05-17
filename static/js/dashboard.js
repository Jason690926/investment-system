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
  initSortable(grid);
}

/* ── 拖拉排序（SortableJS）────────────────────────────────
 * 僅在「全部」chip 啟用：過濾子集做排序語意不清，故只允許整體重排。
 * 桌面：滑鼠按下移動即拖拉；手機：long-press 250ms 再拖（避免吃掉 tap/scroll）。
 */
let sortableInstance = null;
function initSortable(grid) {
  if (sortableInstance) { sortableInstance.destroy(); sortableInstance = null; }
  if (currentFilter !== 'all' || typeof Sortable === 'undefined') return;
  sortableInstance = new Sortable(grid, {
    animation: 150,
    delay: 250,
    delayOnTouchOnly: true,
    ghostClass: 'card-drag-ghost',
    onEnd: async () => {
      const ids = [...grid.querySelectorAll('[data-stock-id]')]
        .map(el => parseInt(el.dataset.stockId, 10))
        .filter(Number.isFinite);
      if (!ids.length) return;
      // 樂觀更新本地 allStocks 順序，避免下次過濾切換時錯亂
      const map = new Map(allStocks.map(s => [s.id, s]));
      allStocks = ids.map(id => map.get(id)).filter(Boolean);
      try {
        await api('/api/stocks/reorder', {
          method: 'PATCH',
          body: JSON.stringify({ order: ids }),
        });
      } catch (e) {
        toast('排序儲存失敗：' + e.message, 'error');
      }
    },
  });
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

// 威科夫相位 → 結構方向標籤（與後端 phase_to_direction 同步；復用 wyckoff 色系）
function phaseDirection(phase) {
  if (!phase) return null;
  const bull = ['上漲', '積累', '再積累'];
  const bear = ['派發', '下跌', '再派發'];
  if (bear.some(p => phase.includes(p))) return { t: '空', c: 'wyckoff-bear' };
  if (bull.some(p => phase.includes(p))) return { t: '多', c: 'wyckoff-bull' };
  return { t: '觀望', c: 'wyckoff-neutral' };
}

function buildCard(s) {
  const riskPct    = s.risk_pct  ?? null;
  const wyckoff    = s.wyckoff_phase ?? '';
  const badgeCls   = s.status === 'holding' ? 'badge-holding' : 'badge-watching';
  const badgeText  = s.status === 'holding' ? '已持有' : '觀察中';
  const isAnalyzed = riskPct != null;

  // Status row: 方向標籤 + wyckoff badge + risk inline chip（並排）
  const _dir = wyckoff ? phaseDirection(wyckoff) : null;
  const dirChip = _dir
    ? `<span class="wyckoff-badge ${_dir.c}" title="結構方向">${_dir.t}</span>`
    : '';
  const wyckoffChip = wyckoff
    ? `<span class="wyckoff-badge ${wyckoffBadgeCls(wyckoff)}">${wyckoff}</span>`
    : '';
  const riskChip = riskPct != null
    ? `<span class="risk-inline ${riskClass(riskPct)}">RISK ${riskPct}%</span>`
    : (wyckoff ? '' : '<span class="risk-inline-empty">尚未分析</span>');
  const statusRowHtml = (dirChip || wyckoffChip || riskChip)
    ? `<div class="card-status-row">${dirChip}${wyckoffChip}${riskChip}</div>`
    : '';

  // Meta row：holding 顯示張數+成本；watching 顯示「觀察中」
  let metaHtml = '';
  if (s.status === 'holding') {
    metaHtml = `<div class="card-meta">
      <div>${s.total_zhang ?? '--'} 張</div>
      ${s.avg_cost ? `<div>成本 <strong>${s.avg_cost}</strong></div>` : ''}
    </div>`;
  } else {
    metaHtml = `<div class="card-meta" style="color:var(--muted);">觀察中 · 尚未建倉</div>`;
  }

  return `
  <div class="stock-card${isAnalyzed ? ' analyzed' : ''}" data-stock-id="${s.id}" onclick="openStockPage(${s.id})">
    <div class="card-row1">
      <div class="card-ident">
        <span class="badge ${badgeCls}">${badgeText}</span>
        <div class="card-name">${s.name}</div>
        <div class="card-symbol">${s.symbol}</div>
      </div>
      <div class="card-price-block">
        <div class="card-price card-price-val">—</div>
        <div class="card-change flat">—</div>
      </div>
    </div>
    ${statusRowHtml}
    <div class="card-spark-wrap">
      <span class="card-spark-title">近 20 日 K</span>
      <span class="card-spark-label flat">—</span>
    </div>
    <div class="card-ohlc">
      <span class="ohlc-item">開 <strong class="ohlc-o">—</strong></span>
      <span class="ohlc-item">高 <strong class="ohlc-h">—</strong></span>
      <span class="ohlc-item">低 <strong class="ohlc-l">—</strong></span>
      <span class="ohlc-item">收 <strong class="ohlc-c">—</strong></span>
    </div>
    <hr class="card-divider">
    <div class="card-row2">
      ${metaHtml}
    </div>
  </div>`;
}

/* ── 20 日迷你日 K 線 SVG 渲染（台股漲紅跌綠）──────────── */
function renderSparkline(bars) {
  if (!bars || bars.length < 2) return '';
  const W = 200, H = 56, padY = 4;
  let maxH = -Infinity, minL = Infinity;
  for (const b of bars) {
    if (b.h > maxH) maxH = b.h;
    if (b.l < minL) minL = b.l;
  }
  const range = (maxH - minL) || 1;
  const usable = H - padY * 2;
  const n = bars.length;
  const slot = W / n;
  const bodyW = Math.max(slot * 0.6, 2);
  const halfBody = bodyW / 2;
  const yOf = (p) => padY + (1 - (p - minL) / range) * usable;

  const parts = [];
  for (let i = 0; i < n; i++) {
    const b = bars[i];
    const xc = slot * (i + 0.5);
    const isUp = b.c >= b.o;
    const color = isUp ? '#EF4444' : '#22C55E';   // 台股：漲紅跌綠
    const yH = yOf(b.h), yL = yOf(b.l);
    const yO = yOf(b.o), yC = yOf(b.c);
    const top = Math.min(yO, yC);
    const h = Math.max(Math.abs(yO - yC), 1);
    parts.push(
      `<line x1="${xc.toFixed(1)}" y1="${yH.toFixed(1)}" x2="${xc.toFixed(1)}" y2="${yL.toFixed(1)}" stroke="${color}"/>`,
      `<rect x="${(xc - halfBody).toFixed(1)}" y="${top.toFixed(1)}" width="${bodyW.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}"/>`
    );
  }
  return `<svg class="card-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${parts.join('')}</svg>`;
}

function sparkPctLabel(bars) {
  if (!bars || bars.length < 2) return ['flat', '—'];
  const first = bars[0].c, last = bars[bars.length - 1].c;
  if (!first) return ['flat', '—'];
  const pct = (last - first) / first * 100;
  if (Math.abs(pct) < 0.05) return ['flat', '0.0%'];
  const cls = pct >= 0 ? 'up' : 'down';
  const arrow = pct >= 0 ? '▲' : '▼';
  return [cls, `${arrow} ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`];
}

/* ── 非同步抓各卡片行情（輕量 /quote 端點）────────────────
 * 失敗自動 retry 一次（延遲 1.5 秒），避免初次 Yahoo 探測 .TWO 失敗或網路 blip
 * 導致該卡永遠顯示「—」。多支同時湧 Yahoo 時這種偶發 timing 問題會自動修正。
 */
async function loadCardPrices(stocks) {
  await Promise.all(stocks.map(s => fetchQuoteWithRetry(s)));
}

async function fetchQuoteWithRetry(stock) {
  const url = `/api/market/${encodeURIComponent(stock.symbol)}/quote`;
  try {
    const d = await api(url);
    updateCardPrice(stock.id, d);
  } catch {
    await new Promise(r => setTimeout(r, 1500));
    try {
      const d = await api(url);
      updateCardPrice(stock.id, d);
    } catch { /* 兩次都失敗就放棄，卡片留「—」*/ }
  }
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

  // 20 日迷你 K 線 sparkline
  if (q.spark_bars && q.spark_bars.length >= 2) {
    const wrap = card.querySelector('.card-spark-wrap');
    if (wrap) {
      const oldSvg = wrap.querySelector('svg.card-spark');
      if (oldSvg) oldSvg.remove();
      wrap.insertAdjacentHTML('beforeend', renderSparkline(q.spark_bars));
      const labelEl = wrap.querySelector('.card-spark-label');
      if (labelEl) {
        const [cls, text] = sparkPctLabel(q.spark_bars);
        labelEl.className = 'card-spark-label ' + cls;
        labelEl.textContent = text;
      }
    }
  }
}

/* ── 週末視窗判斷（週五 14:30 ~ 週一 09:00 台灣時間）──── */
function isWeeklyWindow() {
  const tw = new Date(Date.now() + 8 * 60 * 60 * 1000); // UTC+8
  const wd = tw.getUTCDay();   // 0=Sun 1=Mon ... 5=Fri 6=Sat
  const h  = tw.getUTCHours();
  const m  = tw.getUTCMinutes();
  return (wd === 5 && (h > 14 || (h === 14 && m >= 30))) || wd === 6 || wd === 0 || (wd === 1 && h < 9);
}

function updateAnalyzeBtn() {
  const btn = document.getElementById('btn-analyze-all');
  if (btn) btn.textContent = isWeeklyWindow() ? '⚡ 一鍵分析（含週報）' : '⚡ 一鍵分析';
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

  // 週末視窗：先射出週報背景產生，與個股並行
  if (isWeeklyWindow()) {
    try {
      await api('/api/weekly-report/generate', { method: 'POST' });
      toast('週末視窗：週報背景產生中（約 1-2 分鐘）');
    } catch (e) {
      toast('週報觸發失敗，繼續個股分析', 'error');
    }
  }

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

  // 找或建 card-status-row（插在 card-row1 後）
  let statusRow = card.querySelector('.card-status-row');
  if (!statusRow) {
    statusRow = document.createElement('div');
    statusRow.className = 'card-status-row';
    const row1 = card.querySelector('.card-row1');
    if (row1) row1.after(statusRow);
  }
  // 移除「尚未分析」placeholder
  const empty = statusRow.querySelector('.risk-inline-empty');
  if (empty) empty.remove();

  // 更新或建立 wyckoff badge（插在 row 最前）
  if (wyckoffPhase) {
    let wb = statusRow.querySelector('.wyckoff-badge');
    if (wb) {
      wb.textContent = wyckoffPhase;
      wb.className = `wyckoff-badge ${wyckoffBadgeCls(wyckoffPhase)}`;
    } else {
      statusRow.insertAdjacentHTML('afterbegin',
        `<span class="wyckoff-badge ${wyckoffBadgeCls(wyckoffPhase)}">${wyckoffPhase}</span>`);
    }
  }

  // 更新或建立 risk chip（插在 row 最後）
  if (riskPct != null) {
    let rc = statusRow.querySelector('.risk-inline');
    const cls = riskClass(riskPct);
    if (rc) {
      rc.textContent = `RISK ${riskPct}%`;
      rc.className = `risk-inline ${cls}`;
    } else {
      statusRow.insertAdjacentHTML('beforeend',
        `<span class="risk-inline ${cls}">RISK ${riskPct}%</span>`);
    }
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

/* ── Name 反查代號（部分子字串匹配，下拉建議）─────────── */
let nameTimer = null;
const nameInput = document.getElementById('f-name');
const suggestBox = document.getElementById('name-suggest');

nameInput.addEventListener('input', function () {
  clearTimeout(nameTimer);
  const q = this.value.trim();
  if (!q) { suggestBox.style.display = 'none'; suggestBox.innerHTML = ''; return; }
  nameTimer = setTimeout(async () => {
    try {
      const list = await api(`/api/market/search?q=${encodeURIComponent(q)}`);
      if (!list.length) { suggestBox.style.display = 'none'; return; }
      suggestBox.innerHTML = list.map(item =>
        `<div class="suggest-item" data-symbol="${item.symbol}" data-name="${item.name}">
           <span class="suggest-name">${item.name}</span>
           <span class="suggest-symbol">${item.symbol.replace('.TW','')}</span>
         </div>`).join('');
      suggestBox.style.display = 'block';
    } catch {
      suggestBox.style.display = 'none';
    }
  }, 250);
});

suggestBox.addEventListener('click', function (e) {
  const item = e.target.closest('.suggest-item');
  if (!item) return;
  document.getElementById('f-symbol').value = item.dataset.symbol;
  document.getElementById('f-name').value = item.dataset.name;
  suggestBox.style.display = 'none';
  suggestBox.innerHTML = '';
});

// 點擊 modal 其他位置關掉建議下拉
document.addEventListener('click', function (e) {
  if (e.target !== nameInput && !suggestBox.contains(e.target)) {
    suggestBox.style.display = 'none';
  }
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

/* ── 分享 PDF Modal ─────────────────────────────────────── */
let shareRecipients = new Set();

async function openShareModal() {
  shareRecipients = new Set();
  document.getElementById('f-share-email').value = '';
  document.getElementById('share-status').style.display = 'none';
  renderRecipients();
  document.getElementById('share-modal').classList.add('open');
  // 載入聯絡人
  const chipBox = document.getElementById('contact-chips');
  try {
    const contacts = await api('/api/contacts');
    if (!contacts.length) {
      chipBox.innerHTML = '<span class="muted-text" style="font-size:13px;">尚無記憶；首次寄送後自動記住</span>';
    } else {
      chipBox.innerHTML = contacts.map(c =>
        `<span class="contact-chip" data-email="${c.email}">${c.email}</span>`
      ).join('');
    }
  } catch (e) {
    chipBox.innerHTML = `<span class="muted-text" style="font-size:13px;">載入失敗：${e.message}</span>`;
  }
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('open');
}

function renderRecipients() {
  const box = document.getElementById('selected-recipients');
  if (!shareRecipients.size) {
    box.innerHTML = '<span class="muted-text" style="font-size:13px;">尚未加入收件人</span>';
    return;
  }
  box.innerHTML = [...shareRecipients].map(em =>
    `<span class="recipient-chip">${em} <span class="rm" data-email="${em}">×</span></span>`
  ).join('');
}

document.getElementById('contact-chips').addEventListener('click', e => {
  const chip = e.target.closest('.contact-chip');
  if (!chip) return;
  shareRecipients.add(chip.dataset.email);
  renderRecipients();
});

document.getElementById('selected-recipients').addEventListener('click', e => {
  const rm = e.target.closest('.rm');
  if (!rm) return;
  shareRecipients.delete(rm.dataset.email);
  renderRecipients();
});

// Enter / 逗號將輸入框內容拆分加入
document.getElementById('f-share-email').addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    flushEmailInput();
  }
});

function flushEmailInput() {
  const inp = document.getElementById('f-share-email');
  const parts = inp.value.split(/[,\s]+/).map(s => s.trim()).filter(Boolean);
  for (const p of parts) {
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(p)) {
      shareRecipients.add(p);
    }
  }
  inp.value = '';
  renderRecipients();
}

document.getElementById('share-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeShareModal();
});

async function submitShare() {
  flushEmailInput();
  if (!shareRecipients.size) { toast('請加入至少 1 個收件人', 'error'); return; }
  const btn = document.getElementById('btn-share-send');
  const status = document.getElementById('share-status');
  btn.disabled = true;
  status.style.display = 'block';
  try {
    // 1. 抓 print-report HTML 渲染成 PDF
    status.textContent = '⏳ 取得報表內容…';
    const html = await fetch('/print-report', { credentials: 'same-origin' }).then(r => r.text());
    // 用隱藏 iframe 載入 print-report 完整 DOM，然後截整頁渲染 PDF
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;left:-9999px;top:0;width:1024px;height:1400px;border:0;';
    document.body.appendChild(iframe);
    iframe.srcdoc = html;
    await new Promise(res => iframe.addEventListener('load', res, { once: true }));
    // 等 print-report 自己的 fetch /api/* 完成（給 2 秒緩衝）
    await new Promise(r => setTimeout(r, 2000));

    status.textContent = '⏳ 產生 PDF（約 5-10 秒）…';
    const target = iframe.contentDocument.body;
    const pdfBlob = await html2pdf().set({
      margin: 8,
      filename: '投資建議書.pdf',
      image: { type: 'jpeg', quality: 0.92 },
      html2canvas: { scale: 1.5, useCORS: true, backgroundColor: '#0f1115' },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
    }).from(target).output('blob');
    document.body.removeChild(iframe);

    // 2. 上傳 + 寄出
    status.textContent = '⏳ 寄送中…';
    const fd = new FormData();
    fd.append('pdf', pdfBlob, '投資建議書.pdf');
    fd.append('emails', JSON.stringify([...shareRecipients]));
    const res = await fetch('/api/share/dashboard-pdf', {
      method: 'POST', body: fd, credentials: 'same-origin',
    }).then(async r => {
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
      return j;
    });
    status.textContent = `✓ 已寄出給 ${res.sent_to.length} 位`;
    toast(`已寄出給 ${res.sent_to.length} 位`);
    setTimeout(closeShareModal, 1500);
  } catch (e) {
    status.textContent = `❌ ${e.message}`;
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

/* ── 測試用：清除今日快取（含 NEWS，並立刻重生成新聞摘要）────── */
async function clearTodayCache() {
  if (!confirm('確定清除今日所有分析快取？（含新聞摘要，僅測試用）')) return;
  const btn = document.getElementById('btn-clear-cache');
  btn.disabled = true;
  btn.textContent = '清除中…';
  try {
    const res = await api('/api/admin/clear-today-cache', { method: 'POST' });
    toast(`已清除 ${res.deleted} 筆快取，正在重新產生新聞摘要…`);
    btn.textContent = '重生新聞…';
    await api('/api/news/regenerate', { method: 'POST' });
    toast('新聞摘要已更新');
    loadStocks();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🗑 清快取';
  }
}

loadStocks();
updateAnalyzeBtn();
