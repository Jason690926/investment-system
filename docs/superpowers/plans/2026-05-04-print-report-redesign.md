# 持股 PDF 報表改版實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/print-report` PDF 從 Material Indigo 範本改成「終端機印刷」風格（IBM Plex + 象牙紙 + 琥珀強調），順帶修排序 bug、補當日收盤、拆持股/觀察兩節。

**Architecture:** 後端在 `app.py` 加兩個 pure helpers（`_strip_inline_styles`、`_render_one_block`）+ 一個包裝（`_render_stock_blocks`），route 改用 `get_user_stocks` 與 batch `QuoteCache` 查詢；前端 `templates/print_report.html` 全面重寫 `<style>` 與 `<body>` 結構，加 Google Fonts、`:root` token、`@page` 頁碼。

**Tech Stack:** Python 3 + Flask 3 + SQLAlchemy 2 + Jinja2 + pytest 9（已在 requirements）+ Chrome 列印預覽。

**Spec：** `docs/superpowers/specs/2026-05-04-print-report-redesign-design.md`

**設計鐵則（依 CLAUDE.md「修改 AI 功能的紀律」）：** 整份計畫**不動 AI prompt 也不動 cleanup 既有邏輯**，純前端 CSS + 後端 query 改動。`_clean_html_output:113` 已在寫入時剝 inline style，本計畫只在 render time 加第二道防禦給「DB 既有殘留資料」用。

---

## 檔案結構

| 檔案 | 動作 | 責任 |
|------|------|------|
| `app.py` | Modify `:595-685` + 新增 helpers | `/print-report` route 重構、helper 集中放在 route 上方 |
| `templates/print_report.html` | Rewrite `<style>` + `<body>` | 終端機印刷視覺、章節結構、@page 列印規則 |
| `tests/__init__.py` | Create | pytest package marker（空檔） |
| `tests/conftest.py` | Create | pytest sys.path 設定，讓 import 找到 modules |
| `tests/test_print_report.py` | Create | 三個 helper 的單元測試 |

無新 migration（`QuoteCache` 與 `display_order` 都已存在）。

---

## Task 1：建 pytest 測試骨架

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: 跑 `pytest --collect-only` 應該找到 0 個 test 但 import 不出錯

- [ ] **Step 1：建立空的 `tests/__init__.py`**

`tests/__init__.py`：

```python
```

（空檔即可，給 pytest 當 package 用。）

- [ ] **Step 2：寫 `tests/conftest.py` 設定 sys.path**

`tests/conftest.py`：

```python
"""pytest 設定：把專案根目錄加入 sys.path，讓 tests 能 import app / modules。"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

- [ ] **Step 3：驗證 pytest 能跑**

Run（在專案根目錄）：

```bash
python -m pytest --collect-only -q
```

Expected：`no tests collected` 但 exit code 5（pytest 對「沒測試」回 5），且**沒有 import error**。

- [ ] **Step 4：Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: 建立 pytest 測試骨架（conftest 設 sys.path）"
```

---

## Task 2：`_strip_inline_styles` 防禦性 helper

**Files:**
- Modify: `app.py`（在第 7 行 import 區下方加 helpers 區）
- Test: `tests/test_print_report.py`

**動機：** `_clean_html_output:113` 已在 AI 寫入時剝 inline style，但 DB 既有殘留可能還帶。render time 加第二道防禦，正則同款。

- [ ] **Step 1：寫失敗測試**

`tests/test_print_report.py`：

```python
"""print-report 重構的單元測試。"""
from app import _strip_inline_styles


def test_strip_double_quoted_style():
    html = '<p style="color:red;">hi</p>'
    assert _strip_inline_styles(html) == '<p>hi</p>'


def test_strip_single_quoted_style():
    html = "<div style='background:#000'>x</div>"
    assert _strip_inline_styles(html) == '<div>x</div>'


def test_strip_multiple_attributes_keeps_others():
    html = '<a class="link" style="color:red" href="/x">go</a>'
    assert _strip_inline_styles(html) == '<a class="link" href="/x">go</a>'


def test_strip_handles_empty_and_none():
    assert _strip_inline_styles('') == ''
    assert _strip_inline_styles(None) == ''


def test_strip_handles_no_style():
    html = '<p>plain</p>'
    assert _strip_inline_styles(html) == '<p>plain</p>'
```

- [ ] **Step 2：跑測試確認失敗**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：5 個 test 都 FAIL with `ImportError: cannot import name '_strip_inline_styles' from 'app'`。

- [ ] **Step 3：在 `app.py` 加 helper**

在 `app.py:23`（既有 `init_auth(app)` 之後、`/debug-oauth` 之前）插入：

```python
# ── /print-report 用的 helpers ──────────────────────────────
import re

_INLINE_STYLE_RE = re.compile(
    r'\s+style\s*=\s*(?:"[^"]*"|\'[^\']*\')',
    re.IGNORECASE,
)


def _strip_inline_styles(html):
    """剝除 HTML 內所有 inline style 屬性。
    對既有 DB 殘留 inline style 做 render-time 第二道防禦
    （第一道在 _clean_html_output:113 已做於寫入時）。"""
    if not html:
        return ''
    return _INLINE_STYLE_RE.sub('', html)
```

- [ ] **Step 4：跑測試確認過**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：5 個 test 全部 PASS。

- [ ] **Step 5：Commit**

```bash
git add app.py tests/test_print_report.py
git commit -m "feat: 加 _strip_inline_styles helper（render-time 防 DB 殘留 inline style）"
```

---

## Task 3：`_render_one_block` helper（單一 stock 區塊 HTML）

**Files:**
- Modify: `app.py`（接續 Task 2 helpers 區塊）
- Test: `tests/test_print_report.py`（追加）

**輸入：**
- `s`：Stock SQLAlchemy 物件（測試用 `SimpleNamespace` 替身）
- `a`：StockAnalysis 物件 or None
- `q`：QuoteCache 物件 or None
- `idx`：1-based 序號（章節內）
- `mode`：`'holding'` or `'watching'`

**輸出：** 一個 `.stock-block` 的 HTML 字串。

- [ ] **Step 1：寫失敗測試**

把這段加到 `tests/test_print_report.py` 末尾：

```python
from decimal import Decimal
from types import SimpleNamespace
from datetime import date
from app import _render_one_block


def _make_stock(**overrides):
    defaults = dict(
        symbol='2330', name='台積電', status='holding',
        avg_cost=Decimal('1012.50'), total_zhang=Decimal('3.0'),
        trades=[1],  # 非空 list 代表有交易
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_analysis(**overrides):
    defaults = dict(
        symbol='2330', risk_pct=24,
        wyckoff_phase='Markup',
        support_price=Decimal('1050'),
        resistance_price=Decimal('1120'),
        target_price=Decimal('1180'),
        analysis_date=date(2026, 5, 3),
        html_content='<p>分析內容</p>',
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_quote(**overrides):
    defaults = dict(
        symbol='2330',
        close=Decimal('1085'),
        prev_close=Decimal('1070'),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_render_block_contains_stock_name_and_symbol():
    html = _render_one_block(_make_stock(), _make_analysis(), _make_quote(), idx=1, mode='holding')
    assert '台積電' in html
    assert '2330' in html


def test_render_block_holding_shows_index_and_status_label():
    html = _render_one_block(_make_stock(), None, None, idx=5, mode='holding')
    assert '[05 · HOLD]' in html


def test_render_block_watching_shows_watch_label():
    s = _make_stock(status='watching', trades=[])
    html = _render_one_block(s, None, None, idx=2, mode='watching')
    assert '[02 · WATCH]' in html


def test_render_block_with_quote_shows_price_and_change():
    html = _render_one_block(_make_stock(), None, _make_quote(), idx=1, mode='holding')
    assert '1,085' in html
    assert '+1.4' in html  # change pct


def test_render_block_uses_bull_class_when_price_up():
    html = _render_one_block(_make_stock(), None, _make_quote(), idx=1, mode='holding')
    assert 'class="change bull"' in html or 'change bull' in html
    assert '▲' in html


def test_render_block_uses_bear_class_when_price_down():
    q = _make_quote(close=Decimal('1050'), prev_close=Decimal('1070'))
    html = _render_one_block(_make_stock(), None, q, idx=1, mode='holding')
    assert 'change bear' in html
    assert '▼' in html


def test_render_block_no_quote_shows_dash():
    html = _render_one_block(_make_stock(), None, None, idx=1, mode='holding')
    assert '—' in html


def test_render_block_holding_shows_data_row_with_cost_qty_pl():
    html = _render_one_block(_make_stock(), _make_analysis(), _make_quote(), idx=1, mode='holding')
    assert '1,012.50' in html
    assert '3.0' in html  # qty
    assert 'COST' in html
    assert 'P/L' in html
    assert 'RISK' in html


def test_render_block_watching_skips_data_row_includes_risk_pill():
    s = _make_stock(status='watching', trades=[])
    html = _render_one_block(s, _make_analysis(), _make_quote(), idx=1, mode='watching')
    assert 'COST' not in html  # watch mode 沒有 data row
    assert '風險' in html       # 風險改進 pills


def test_render_block_pills_show_support_resistance_target_wyckoff():
    html = _render_one_block(_make_stock(), _make_analysis(), _make_quote(), idx=1, mode='holding')
    assert '撐' in html and '1,050' in html
    assert '壓' in html and '1,120' in html
    assert '目標' in html and '1,180' in html
    assert '威科夫' in html and 'Markup' in html


def test_render_block_strips_inline_styles_from_analysis():
    a = _make_analysis(html_content='<p style="color:red;">x</p><h3>y</h3>')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert 'style="color:red' not in html
    assert '<p>x</p>' in html
    assert '<h3>y</h3>' in html


def test_render_block_no_analysis_shows_placeholder():
    html = _render_one_block(_make_stock(), None, None, idx=1, mode='holding')
    assert 'no-analysis' in html or '尚無分析資料' in html
```

- [ ] **Step 2：跑測試確認失敗**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：12 個新 test FAIL with ImportError。

- [ ] **Step 3：實作 `_render_one_block`**

在 `app.py` 接著 `_strip_inline_styles` 後面加：

```python
def _format_price(value):
    """價格格式：>=100 用整數千分位，<100 顯示 2 位小數。"""
    if value is None:
        return '—'
    v = float(value)
    return f'{v:,.0f}' if v >= 100 else f'{v:,.2f}'


def _render_one_block(s, a, q, idx, mode):
    """產出單一持股/觀察區塊 HTML。

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

    # Pills 列
    pills = []
    if a:
        if a.support_price is not None:
            pills.append(f'<span class="pill pill-support"><span class="lbl">撐 </span>{_format_price(a.support_price)}</span>')
        if a.resistance_price is not None:
            pills.append(f'<span class="pill pill-bull"><span class="lbl">壓 </span>{_format_price(a.resistance_price)}</span>')
        if a.target_price is not None:
            pills.append(f'<span class="pill pill-amber"><span class="lbl">目標 </span>{_format_price(a.target_price)}</span>')
        if a.wyckoff_phase:
            pills.append(f'<span class="pill pill-ink"><span class="lbl">威科夫 </span>{a.wyckoff_phase}</span>')
    # 觀察版把風險合進 pills
    if mode == 'watching' and a and a.risk_pct is not None:
        pills.append(f'<span class="pill pill-amber-outline"><span class="lbl">風險 </span>{a.risk_pct}%</span>')
    pills_html = f'<div class="pills">{"".join(pills)}</div>' if pills else ''

    # 分析內容（剝 inline style）
    if a and a.html_content:
        body_html = f'<div class="analysis-wrap">{_strip_inline_styles(a.html_content)}</div>'
    else:
        body_html = '<div class="no-analysis">尚無分析資料</div>'

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
</div>"""
```

- [ ] **Step 4：跑測試確認過**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：所有 test PASS（5 + 12 = 17 個）。

- [ ] **Step 5：Commit**

```bash
git add app.py tests/test_print_report.py
git commit -m "feat: 加 _render_one_block helper（持股/觀察區塊 HTML 產生）"
```

---

## Task 4：`_render_stock_blocks` 包裝（list → HTML）

**Files:**
- Modify: `app.py`（接續 helpers 區塊）
- Test: `tests/test_print_report.py`（追加）

- [ ] **Step 1：寫失敗測試**

加到 `tests/test_print_report.py` 末尾：

```python
from app import _render_stock_blocks


def test_render_stock_blocks_empty_list_returns_empty_string():
    assert _render_stock_blocks([], {}, {}, mode='holding') == ''


def test_render_stock_blocks_iterates_with_correct_index():
    stocks = [_make_stock(symbol='2330', name='台積電'),
              _make_stock(symbol='2317', name='鴻海')]
    html = _render_stock_blocks(stocks, {}, {}, mode='holding')
    assert '[01 · HOLD]' in html
    assert '[02 · HOLD]' in html


def test_render_stock_blocks_passes_analysis_and_quote_by_symbol():
    stocks = [_make_stock(symbol='2330', name='台積電')]
    analyses = {'2330': _make_analysis()}
    quotes = {'2330': _make_quote()}
    html = _render_stock_blocks(stocks, analyses, quotes, mode='holding')
    assert '台積電' in html
    assert '1,085' in html
    assert 'Markup' in html


def test_render_stock_blocks_handles_missing_quote_or_analysis():
    stocks = [_make_stock(symbol='2330', name='台積電')]
    html = _render_stock_blocks(stocks, {}, {}, mode='holding')
    assert '台積電' in html
    assert '尚無分析資料' in html
```

- [ ] **Step 2：跑測試確認失敗**

Run：

```bash
python -m pytest tests/test_print_report.py -v -k stock_blocks
```

Expected：4 test FAIL with ImportError。

- [ ] **Step 3：實作 `_render_stock_blocks`**

在 `app.py` 接著 `_render_one_block` 後面加：

```python
def _render_stock_blocks(stocks, analyses, quotes, mode):
    """把一個 stocks list 全部串接成 HTML。

    stocks: list[Stock]
    analyses: dict[symbol -> StockAnalysis]
    quotes: dict[symbol -> QuoteCache]
    mode: 'holding' or 'watching'
    """
    parts = []
    for idx, s in enumerate(stocks, start=1):
        a = analyses.get(s.symbol)
        q = quotes.get(s.symbol)
        parts.append(_render_one_block(s, a, q, idx=idx, mode=mode))
    return ''.join(parts)
```

- [ ] **Step 4：跑測試確認過**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：21 個 test 全 PASS。

- [ ] **Step 5：Commit**

```bash
git add app.py tests/test_print_report.py
git commit -m "feat: 加 _render_stock_blocks 包裝 helper"
```

---

## Task 5：`/print-report` route 重構（套用 helpers + 拆 holdings/watching + 補 quote）

**Files:**
- Modify: `app.py:595-685`

- [ ] **Step 1：替換整段 route**

把 `app.py` 第 595-685 行（既有的 `@app.route('/print-report')` ... `def print_report():` ... `db.close()`）整段替換成下方：

```python
@app.route('/print-report')
@login_required
def print_report():
    from modules.models import StockAnalysis, WeeklyReport, QuoteCache
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta, date
    TW = timezone(timedelta(hours=8))

    db = SessionLocal()
    try:
        # 用既有 helper：display_order 已正確（NULL 排最後）
        stocks = get_user_stocks(db, current_user.id)
        if not stocks:
            return '尚無持股資料', 404

        # 最新一份週報（跨用戶共用）
        weekly = db.query(WeeklyReport).order_by(WeeklyReport.week_start.desc()).first()
        weekly_range = (f"{weekly.week_start.strftime('%Y/%m/%d')} ~ "
                        f"{weekly.week_end.strftime('%Y/%m/%d')}") if weekly else ''

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

        # 當日 quote 批次撈（沒命中就 fallback 顯示 —，不打 Yahoo）
        today_tw = datetime.now(TW).date()
        quote_rows = (
            db.query(QuoteCache)
            .filter(QuoteCache.symbol.in_(symbols),
                    QuoteCache.cache_date == today_tw)
            .all()
        )
        quotes = {q.symbol: q for q in quote_rows}

        # 拆 holdings / watching
        holdings = [s for s in stocks if s.status == 'holding']
        watching = [s for s in stocks if s.status == 'watching']
        holdings_html = _render_stock_blocks(holdings, analyses, quotes, mode='holding')
        watching_html = _render_stock_blocks(watching, analyses, quotes, mode='watching')

        now_tw = datetime.now(TW)
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
        )
    finally:
        db.close()
```

注意：
- 不再 import `Stock`（用了 `get_user_stocks`）
- 移除舊變數 `stocks_html`，改用 `holdings_html` / `watching_html`
- Quote 用 today（TW 時區）— dashboard 當日有看過的股會在 cache 裡

- [ ] **Step 2：smoke 驗證 import 沒壞**

Run：

```bash
python -c "from app import app; print('app loaded OK')"
```

Expected：印出 `app loaded OK`，沒有 traceback。

- [ ] **Step 3：本機 dev server 跑起來**

Run：

```bash
python app.py
```

或（若用 main.py 啟動）：

```bash
python main.py
```

Expected：Flask dev server 起來，listen 5000 port（或專案預設）。**保留這個 server 在 Task 7 用**。

- [ ] **Step 4：route 不掛掉的最低驗證**

另開瀏覽器登入後訪問 `http://localhost:5000/print-report`。

Expected：
- 頁面載入（雖然此時還是舊樣式）
- 沒有 Internal Server Error
- 排序已修：拖拉 dashboard 順序後重整 PDF，順序跟 dashboard 一致
- HTML source 內含 `holdings_html` 與 `watching_html` 對應內容（暫時樣式還是舊的，下個 Task 改）

如果有錯，**不要繼續 Task 6**，先回頭修 route。

- [ ] **Step 5：Commit**

```bash
git add app.py
git commit -m "refactor: /print-report 用 helpers、修排序 bug、加 quote 批次撈、拆 holding/watching"
```

---

## Task 6：`templates/print_report.html` 重寫（套用終端機印刷視覺）

**Files:**
- Modify: `templates/print_report.html`（整支 176 行重寫）

**注意：** 這個 task 是**整支檔案 rewrite**。建議用 Write 工具直接覆蓋。

- [ ] **Step 1：覆寫 `templates/print_report.html`**

把整支檔案內容換成：

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>持股分析報告 — {{ date_str }}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;700&family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">

  <style>
    :root {
      --font-sans: "IBM Plex Sans", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
      --font-mono: "IBM Plex Mono", "Consolas", monospace;

      --paper:        #fbf8f1;
      --ink:          #1a1a1a;
      --amber:        #b8860b;
      --bull:         #c0392b;
      --bear:         #2e7d32;
      --support:      #1565c0;
      --amber-soft:   #fff8dc;
      --bull-soft:    #fef0f0;
      --support-soft: #e8f4ff;
      --rule-soft:    #e5e0d0;

      --space-xs: 4px;
      --space-sm: 8px;
      --space-md: 12px;
      --space-lg: 20px;
      --space-xl: 32px;

      --fs-display:    24px;
      --fs-section:    14px;
      --fs-stock-name: 16px;
      --fs-body:       11px;
      --fs-label:      9px;
      --fs-mini:       8px;
    }

    * { box-sizing: border-box; }
    body {
      font-family: var(--font-sans);
      font-size: var(--fs-body);
      color: var(--ink);
      background: var(--paper);
      margin: 0; padding: 24px 28px;
      line-height: 1.7;
    }

    /* 列印工具列（螢幕用，列印時隱藏） */
    .print-toolbar {
      position: fixed; top: 0; left: 0; right: 0;
      background: var(--ink); color: var(--paper);
      padding: 10px 24px; display: flex; align-items: center; gap: 12px;
      z-index: 100; font-size: 13px;
      font-family: var(--font-mono);
    }
    .print-toolbar strong { flex: 1; font-weight: 700; }
    .print-toolbar button {
      background: var(--paper); color: var(--ink); border: none;
      padding: 6px 18px; border-radius: 0; font-size: 12px;
      cursor: pointer; font-weight: 700;
      font-family: var(--font-mono);
    }
    .print-toolbar button:hover { background: var(--amber); color: var(--paper); }

    .report-body { padding-top: 52px; }

    /* 封面 */
    .report-header {
      border-bottom: 2px solid var(--ink);
      padding: 0 0 var(--space-md);
      margin-bottom: var(--space-xl);
      display: flex; justify-content: space-between; align-items: flex-end;
    }
    .report-header h1 {
      margin: 0;
      font-size: var(--fs-display);
      font-weight: 700;
      letter-spacing: -.5px;
      font-family: var(--font-sans);
    }
    .report-header .meta {
      text-align: right;
      font-family: var(--font-mono);
      font-size: var(--fs-mini);
      letter-spacing: 1px;
      opacity: .65;
      line-height: 1.7;
    }
    .report-header .label {
      display: block;
      font-family: var(--font-mono);
      font-size: var(--fs-mini);
      letter-spacing: 3px;
      opacity: .55;
      text-transform: uppercase;
      margin-bottom: 4px;
    }

    /* 章節分隔（§ HOLDINGS / § WATCHLIST） */
    .section-divider {
      font-family: var(--font-sans);
      font-size: var(--fs-section);
      font-weight: 700;
      letter-spacing: 1px;
      border-bottom: 1px solid var(--ink);
      padding-bottom: var(--space-sm);
      margin: var(--space-xl) 0 var(--space-lg);
    }

    /* 週報區塊 */
    .weekly-section {
      border: 1px solid var(--ink);
      margin-bottom: var(--space-lg);
      page-break-inside: avoid;
    }
    .weekly-section-header {
      background: var(--ink); color: var(--paper);
      padding: var(--space-sm) var(--space-md);
      font-weight: 700; font-size: 13px;
      display: flex; justify-content: space-between; align-items: center;
      font-family: var(--font-mono);
      letter-spacing: 1px;
    }
    .weekly-section-header .range { font-weight: 400; font-size: var(--fs-mini); opacity: .7; }
    .weekly-section-body {
      padding: var(--space-md);
      font-size: var(--fs-body);
      line-height: 1.75;
      background: #fff;
    }
    .weekly-section-body h3,
    .weekly-section-body h4 {
      color: var(--ink); font-size: 13px; font-weight: 700;
      margin: var(--space-md) 0 var(--space-xs);
      border-left: 3px solid var(--amber);
      padding: var(--space-xs) var(--space-sm);
      background: var(--amber-soft);
    }
    .weekly-section-body ul { padding-left: 18px; margin: var(--space-xs) 0; }
    .weekly-section-body li { margin: 3px 0; }
    .weekly-section-body p  { margin: 5px 0; }

    /* 持股 / 觀察 區塊 */
    .stock-block {
      background: #fff;
      border: 1px solid var(--ink);
      margin-bottom: var(--space-lg);
      page-break-inside: avoid;
    }
    .stock-block-header {
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: var(--space-md);
      border-bottom: 1px solid var(--ink);
    }
    .stock-name-row {
      display: flex; align-items: baseline; gap: var(--space-sm);
    }
    .stock-name {
      font-family: var(--font-sans);
      font-size: var(--fs-stock-name);
      font-weight: 700;
      line-height: 1.1;
    }
    .stock-symbol {
      font-family: var(--font-mono);
      font-size: 10px;
      opacity: .55;
    }
    .stock-price-row {
      display: flex; align-items: baseline; gap: 10px;
      margin-top: 5px;
    }
    .price-num {
      font-family: var(--font-mono);
      font-size: var(--fs-display);
      font-weight: 700;
      color: var(--ink);
      letter-spacing: -1px;
      line-height: 1;
    }
    .change {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
    }
    .change.bull { color: var(--bull); }
    .change.bear { color: var(--bear); }

    .stock-meta-right {
      text-align: right;
      font-family: var(--font-mono);
      font-size: var(--fs-mini);
      opacity: .55;
      line-height: 1.7;
    }
    .idx-tag { letter-spacing: 2px; }

    .data-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      padding: var(--space-sm) var(--space-md);
      background: var(--paper);
      border-bottom: 1px dashed var(--ink);
      font-family: var(--font-mono);
      font-size: var(--fs-label);
    }
    .data-row .label {
      opacity: .5;
      letter-spacing: 1px;
    }
    .data-row strong {
      font-size: 11px;
      font-weight: 700;
    }
    .data-row .bull { color: var(--bull); }
    .data-row .bear { color: var(--bear); }
    .data-row .amber { color: var(--amber); }
    .data-row .muted { opacity: .5; }

    .pills {
      display: flex; flex-wrap: wrap; gap: 5px;
      padding: var(--space-sm) var(--space-md);
      background: var(--paper);
      border-bottom: 1px solid var(--rule-soft);
      font-family: var(--font-mono);
      font-size: var(--fs-label);
    }
    .pill {
      padding: 2px 7px;
      letter-spacing: 0;
    }
    .pill .lbl { opacity: .6; letter-spacing: 1px; }
    .pill-support { background: var(--support-soft); border-left: 3px solid var(--support); }
    .pill-bull    { background: var(--bull-soft);    border-left: 3px solid var(--bull); }
    .pill-amber   { background: var(--amber-soft);   border-left: 3px solid var(--amber); }
    .pill-ink     { background: var(--ink); color: var(--paper); }
    .pill-ink .lbl { opacity: .7; }
    .pill-amber-outline { background: var(--paper); border: 1px solid var(--amber); }

    /* AI 分析區塊（吃 token 統一控制） */
    .analysis-wrap {
      padding: var(--space-md);
      font-family: var(--font-sans);
      font-size: var(--fs-body);
      line-height: 1.75;
    }
    .analysis-wrap h3,
    .analysis-wrap h4 {
      font-size: 13px; font-weight: 700;
      border-left: 3px solid var(--amber);
      padding: var(--space-xs) var(--space-sm);
      background: var(--amber-soft);
      margin: var(--space-md) 0 var(--space-xs);
      color: var(--ink);
    }
    .analysis-wrap ul { padding-left: 18px; margin: var(--space-xs) 0; }
    .analysis-wrap li { margin: 3px 0; }
    .analysis-wrap p  { margin: 5px 0; }
    .analysis-wrap table {
      width: 100%; border-collapse: collapse; font-size: 10px; margin: var(--space-sm) 0;
    }
    .analysis-wrap th {
      background: var(--paper); padding: 5px 7px; text-align: left;
      font-weight: 700; border-bottom: 1px solid var(--ink);
    }
    .analysis-wrap td { padding: 4px 7px; border-bottom: 1px solid var(--rule-soft); }

    /* AI 既有 class 對應 */
    .analysis-wrap .key-point {
      display: inline-block; color: var(--amber); font-weight: 700;
      background: var(--amber-soft); border-left: 3px solid var(--amber);
      padding: 2px 8px; margin: 2px 0;
    }
    .analysis-wrap .support-level    { color: var(--support); font-weight: 700; background: var(--support-soft); padding: 1px 6px; }
    .analysis-wrap .resistance-level { color: var(--bull); font-weight: 700; background: var(--bull-soft); padding: 1px 6px; }
    .analysis-wrap .target-price     { color: var(--amber); font-weight: 700; background: var(--amber-soft); padding: 1px 6px; }
    .analysis-wrap .stop-loss        { color: var(--bull); font-weight: 700; background: var(--bull-soft); padding: 1px 6px; }
    .analysis-wrap .short-term-title { color: var(--amber); font-weight: 700; }
    .analysis-wrap .mid-term-title   { color: var(--support); font-weight: 700; }
    .analysis-wrap .bull             { color: var(--bull); font-weight: 700; }
    .analysis-wrap .bear             { color: var(--bear); font-weight: 700; }

    .no-analysis {
      padding: var(--space-lg) var(--space-md);
      color: var(--ink);
      opacity: .4;
      font-style: italic;
      text-align: center;
      font-family: var(--font-mono);
      font-size: 10px;
    }

    .disclaimer {
      background: var(--amber-soft);
      border-left: 3px solid var(--amber);
      padding: var(--space-md);
      font-size: 10px;
      color: var(--ink);
      margin-top: var(--space-xl);
      font-family: var(--font-sans);
    }

    /* 列印規則 */
    @page {
      size: A4;
      margin: 18mm 14mm;
      @bottom-right {
        content: counter(page) " / " counter(pages);
        font-family: "IBM Plex Mono", monospace;
        font-size: 9px;
        color: #888;
      }
    }
    @media print {
      .print-toolbar { display: none !important; }
      .report-body   { padding-top: 0; }
      body           { background: var(--paper); }
    }
  </style>
</head>
<body>

<div class="print-toolbar">
  <strong>📊 持股分析報告 — {{ date_str }}</strong>
  <button onclick="window.print()">🖨 列印 / 存成 PDF</button>
  <button onclick="window.close()">✕ 關閉</button>
</div>

<div class="report-body">
  <div class="report-header">
    <div>
      <span class="label">PORTFOLIO_BRIEF</span>
      <h1>持股分析報告</h1>
    </div>
    <div class="meta">
      {{ user_name }}<br>
      {{ date_str }} (TW)<br>
      hold {{ holding_count }} · watch {{ watching_count }}
    </div>
  </div>

  {% if weekly and weekly.html_market %}
  <div class="weekly-section">
    <div class="weekly-section-header">
      <span>§ MARKET · 大盤週報</span>
      <span class="range">{{ weekly_range }}</span>
    </div>
    <div class="weekly-section-body">
      {{ weekly.html_market | safe }}
    </div>
  </div>
  {% endif %}

  {% if weekly and weekly.html_industry %}
  <div class="weekly-section">
    <div class="weekly-section-header">
      <span>§ INDUSTRY · 產業指標股</span>
      <span class="range">{{ weekly_range }}</span>
    </div>
    <div class="weekly-section-body">
      {{ weekly.html_industry | safe }}
    </div>
  </div>
  {% endif %}

  {% if holdings_html %}
  <div class="section-divider">§ HOLDINGS · 持股</div>
  {{ holdings_html | safe }}
  {% endif %}

  {% if watching_html %}
  <div class="section-divider">§ WATCHLIST · 觀察</div>
  {{ watching_html | safe }}
  {% endif %}

  <div class="disclaimer">
    ⚠️ 免責聲明：本報表由 AI 自動分析產生，所有分析與建議僅供學習參考，不構成實際投資建議。投資有風險，請自行評估後謹慎決策。
  </div>
</div>

</body>
</html>
```

- [ ] **Step 2：重整 dev server 訪問 `/print-report`**

不用重啟 Flask（template 改動會自動 reload）。瀏覽器重整 `http://localhost:5000/print-report`。

Expected 螢幕看到：
- 象牙紙底色（不是純白）
- IBM Plex Mono 在數字 / 標籤；IBM Plex Sans + Noto Sans TC 在 prose
- 封面區：左 PORTFOLIO_BRIEF 標籤 + 持股分析報告大標；右 mono 小字 meta
- 大盤週報 / 產業指標股（若有）：黑底章節標、白底內文
- `§ HOLDINGS · 持股` / `§ WATCHLIST · 觀察` 兩個章節分隔
- 每張 stock-block：左側股名 + 大數字股價 + 漲跌；右側 [01 · HOLD] + close 日期
- 持股版有 COST/QTY/P/L/RISK 四欄；觀察版沒有，但 pills 多一顆「風險」
- 紅漲綠跌
- AI 分析區塊小標靠 amber 邊條 + 淺米填底

如果哪裡爛掉、回頭調 CSS。

- [ ] **Step 3：Chrome 列印預覽驗證**

按工具列「🖨 列印 / 存成 PDF」（或 Ctrl+P），目的地選「另存為 PDF」。

Expected 在預覽中看到：
- 工具列消失
- 字體正確嵌入（IBM Plex 系列）
- 右下頁碼 `1 / N`
- 每張 stock-block 不會被切成兩頁
- A4 紙張、邊距合理

如果頁碼沒出，是 Chrome 版本問題，可接受降級（不影響內容）。

- [ ] **Step 4：Commit**

```bash
git add templates/print_report.html
git commit -m "feat: print-report 視覺改版（IBM Plex + 象牙紙 + 終端機印刷風）"
```

---

## Task 7：對既有 DB 真實資料驗證 + 收尾

**Files:** 無

**動機（依 CLAUDE.md「修改 AI 功能的紀律」）：** 不重跑 AI、用 DB 既有 raw 輸出在新 cleanup + CSS 上推演，確認舊資料也能正確渲染。

- [ ] **Step 1：抓 5 支既有 daily 分析最新一筆**

在專案根目錄跑：

```bash
python -c "
from modules.database import SessionLocal
from modules.models import StockAnalysis
db = SessionLocal()
rows = db.query(StockAnalysis).filter_by(analysis_type='daily').order_by(StockAnalysis.analysis_date.desc()).limit(5).all()
for r in rows:
    has_inline = 'style=' in (r.html_content or '')
    print(f'{r.symbol} {r.analysis_date} inline_style={has_inline} len={len(r.html_content or \"\")}')
db.close()
"
```

Expected：印出 5 筆 symbol / 日期 / 是否含 inline style / 內容長度。記下哪幾支有 `inline_style=True`。

- [ ] **Step 2：在瀏覽器把那幾支放進 watchlist 或 holding（如果還沒）**

確保使用者帳號的 stocks 表至少包含上述 5 支。如果已經有，跳過。

- [ ] **Step 3：訪問 `/print-report` 視覺檢查**

重整 PDF 頁面，特別檢查含 inline style 的那幾支：

- 顏色是否被舊 inline style 蓋過（不該）
- 標題層級、列表、表格是否乖乖吃新 CSS
- 短線 / 中線 / 重點等 class 是否上對應色

如果發現某支樣式還是被蓋，回頭看 `_strip_inline_styles` 是否有漏（例如 inline `<style>` 標籤殘留 — 若有，spec 風險表第一條兌現，加 `<style>` 整段砍）。

- [ ] **Step 4：拖拉排序驗證**

dashboard 拖拉幾張卡片改變順序 → 重新整理 `/print-report` → 確認 PDF 內持股順位跟 dashboard 一致。

- [ ] **Step 5：Chrome 列印預覽存 PDF 看一次**

存一份 PDF 到桌面，打開檢查最終視覺。

- [ ] **Step 6：跑全測試**

Run：

```bash
python -m pytest tests/test_print_report.py -v
```

Expected：21 個 test 全 PASS。

- [ ] **Step 7：更新 CLAUDE.md「當前進度」**

把這次的成果加進 CLAUDE.md 的「當前進度」區塊，例如：

```markdown
- ✅ 持股 PDF 報表改版（終端機印刷風格）
  - IBM Plex + 象牙紙 + 琥珀強調
  - 修排序 bug（用 get_user_stocks）、補當日收盤、拆持股/觀察兩節
  - 加 _strip_inline_styles 二道防禦（DB 既有 inline style 殘留）
  - 加 unit tests (`tests/test_print_report.py`, 21 cases)
  - spec: docs/superpowers/specs/2026-05-04-print-report-redesign-design.md
  - plan: docs/superpowers/plans/2026-05-04-print-report-redesign.md
```

- [ ] **Step 8：最終 commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md 紀錄持股 PDF 報表改版完成"
```

---

## 驗收

- [ ] 21 個 pytest 全綠
- [ ] 螢幕版 `/print-report` 視覺如 spec 第 4 節 mockup
- [ ] Chrome 列印 PDF 字體正確、頁碼出現、page-break 合理
- [ ] 拖拉 dashboard 順序 → PDF 順序跟著改
- [ ] 含 inline style 的舊 DB 分析資料樣式被新 CSS 控住
- [ ] 沒重跑任何 AI（AI 帳單無變動）

---

## 風險摘要（Spec 第 8 節照映）

| 風險 | 計畫處理 |
|---|---|
| AI 既有 inline style | Task 2 加 `_strip_inline_styles`，Task 7 step 3 真實資料驗證 |
| QuoteCache 沒當日資料 | Task 5 step 4 接受降級（顯示 `—`）；不打 Yahoo |
| Google Fonts 載入失敗 | font-stack 有 system fallback（Noto Sans TC / Microsoft JhengHei / Consolas） |
| Chrome 列印頁碼語法 | Task 6 step 3 接受降級（不影響內容） |
