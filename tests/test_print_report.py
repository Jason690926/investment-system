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


# ── markdown 轉換測試（mistune 進 pipeline 後新增） ──────────

def test_render_block_converts_markdown_heading_to_h3():
    a = _make_analysis(html_content='### 一、威科夫骨幹分析\n\n內文')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<h3>一、威科夫骨幹分析</h3>' in html
    assert '###' not in html  # 原始 markdown 不應殘留


def test_render_block_converts_markdown_bullets_to_ul():
    a = _make_analysis(html_content='- 第一點\n- 第二點\n- 第三點')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<ul>' in html
    assert '<li>第一點</li>' in html
    assert '<li>第二點</li>' in html


def test_render_block_converts_markdown_bold_to_strong():
    a = _make_analysis(html_content='今日時機：**等待確認**')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<strong>等待確認</strong>' in html
    assert '**' not in html


def test_render_block_preserves_raw_html_table():
    raw_table = (
        '<table><thead><tr><th>日期</th><th>型態</th></tr></thead>'
        '<tbody><tr><td>2026-04-12</td><td>長紅K</td></tr></tbody></table>'
    )
    a = _make_analysis(html_content=raw_table)
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<table>' in html
    assert '<th>日期</th>' in html
    assert '長紅K' in html


def test_render_block_preserves_raw_html_key_point_span():
    a = _make_analysis(html_content='內文\n\n<span class="key-point">重點摘要</span>')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<span class="key-point">重點摘要</span>' in html


def test_render_block_converts_markdown_hr():
    a = _make_analysis(html_content='前段\n\n---\n\n後段')
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<hr' in html  # mistune 輸出 <hr /> 或 <hr>


def test_render_block_handles_real_world_mixed_content():
    """整合測試：完整一段真實 AI 輸出（markdown + HTML 混合）。"""
    raw = """### 一、威科夫骨幹分析

- 月K走勢：再積累
- <span class="support-level">支撐：211元</span>

<span class="key-point">縮量整理，等待量能</span>

---

### 二、本間宗久K線

<table><tbody><tr><td>2026-04-12</td><td>長紅K</td><td class="bull">看漲</td></tr></tbody></table>
"""
    a = _make_analysis(html_content=raw)
    html = _render_one_block(_make_stock(), a, None, idx=1, mode='holding')
    assert '<h3>一、威科夫骨幹分析</h3>' in html
    assert '<h3>二、本間宗久K線</h3>' in html
    assert '<ul>' in html
    assert '<span class="support-level">' in html
    assert '<span class="key-point">' in html
    assert '<table>' in html
    assert '<td class="bull">看漲</td>' in html
    assert '###' not in html
