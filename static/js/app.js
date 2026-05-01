/* ── 共用工具 ─────────────────────────────────────────── */

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function formatChange(val) {
  if (val == null) return { text: '—', cls: 'flat' };
  const sign = val > 0 ? '+' : '';
  const cls  = val > 0 ? 'up' : val < 0 ? 'down' : 'flat';
  return { text: `${sign}${val.toFixed(2)}%`, cls };
}

function riskClass(pct) {
  if (pct <= 35) return 'risk-low';
  if (pct <= 65) return 'risk-mid';
  return 'risk-high';
}
