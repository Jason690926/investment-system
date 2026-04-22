import os
from datetime import datetime
import config
import markdown as md

def _md(text):
    if not text:
        return ''
    return md.markdown(str(text), extensions=['nl2br'])

def _render_watchlist_html(watchlist_analysis, report_type='daily'):
    """產生持股追蹤 HTML，依產業分組"""
    from modules.stock_names import get_sector
    if not watchlist_analysis:
        return '<div style="color:#888;padding:16px;text-align:center">尚未設定追蹤標的，請至控制台新增</div>'

    border_color = '#c5cae9' if report_type == 'daily' else '#a5d6a7'
    title_color = '#1a237e' if report_type == 'daily' else '#1b5e20'
    card_bg = '#f8f9ff' if report_type == 'daily' else '#f1f8e9'
    advice_border = '#1a237e' if report_type == 'daily' else '#1b5e20'
    pattern_label = 'K線型態' if report_type == 'daily' else '本週K線型態'

    # 依產業分組
    groups = {}
    for item in watchlist_analysis:
        sector = item.get('sector') or get_sector(item.get('symbol', ''), item.get('name', ''))
        if sector not in groups:
            groups[sector] = []
        groups[sector].append(item)

    html = ''
    for sector, items in sorted(groups.items()):
        html += f'''
<div style="margin-bottom:20px">
  <div style="background:#e8eaf6;border-left:4px solid {title_color};padding:8px 14px;border-radius:0 6px 6px 0;margin-bottom:12px;font-weight:600;font-size:14px;color:{title_color}">
    📁 {sector} <span style="font-weight:400;font-size:12px;color:#888">（{len(items)} 檔）</span>
  </div>'''

        for item in items:
            name = item['name']
            tech = item['technical']
            patterns = item['patterns']
            ai_advice = item['ai_advice']
            curr = tech.get('price', 0)
            change = tech.get('change', 0)
            change_cls = 'up' if change >= 0 else 'down'
            sign = '+' if change >= 0 else ''

            pnl_html = ''
            if tech.get('cost') and curr:
                try:
                    cost = float(tech['cost'])
                    pnl_pct = round(((curr - cost) / cost) * 100, 2)
                    pnl_sign = '+' if pnl_pct >= 0 else ''
                    pnl_cls = 'up' if pnl_pct >= 0 else 'down'
                    pnl_html = f'成本:<span class="close-price">{cost}</span> 損益:<span class="{pnl_cls}">{pnl_sign}{pnl_pct}%</span>'
                except:
                    pass

            pattern_html = ''
            for p in patterns[:3]:
                p_cls = 'bullish-tag' if p['type'] == 'bullish' else ('bearish-tag' if p['type'] == 'bearish' else 'neutral-tag')
                pattern_html += f'<span class="pattern-tag {p_cls}">{p["name"]}</span>'
            if not pattern_html:
                pattern_html = '<span class="pattern-tag neutral-tag">無明顯型態</span>'

            symbol = item.get('symbol', '')
            html += f'''
<div class="stock-card" style="background:{card_bg};border-color:{border_color}">
  <div class="stock-header">
    <div class="stock-title" style="color:{title_color}">{name} <span style="font-size:12px;color:#888;font-weight:400">({symbol})</span></div>
    <div class="stock-price"><span class="close-price">NT${curr:,}</span> <span class="{change_cls}">{sign}{change}%</span></div>
  </div>
  <div class="stock-meta">趨勢：{tech.get("trend","--")} ｜ RSI：{tech.get("RSI","--")} ｜ MA5：{tech.get("MA5","--")} ｜ MA20：{tech.get("MA20","--")}{(" ｜ " + pnl_html) if pnl_html else ""}</div>
  <div class="stock-meta" style="color:#888">
    1日：<span class="{"up" if (tech.get("change") or 0)>=0 else "down"}">{("+" if (tech.get("change") or 0)>=0 else "")}{tech.get("change","--")}%</span>
    ｜ 5日：<span class="{"up" if (tech.get("change_5d") or 0)>=0 else "down"}">{("+" if (tech.get("change_5d") or 0)>=0 else "")}{tech.get("change_5d","N/A")}{"%" if tech.get("change_5d") is not None else ""}</span>
    ｜ 20日：<span class="{"up" if (tech.get("change_20d") or 0)>=0 else "down"}">{("+" if (tech.get("change_20d") or 0)>=0 else "")}{tech.get("change_20d","N/A")}{"%" if tech.get("change_20d") is not None else ""}</span>
  </div>
  <div class="pattern-row">{pattern_label}：{pattern_html}</div>
  <div class="price-summary">
    <span class="support-level">支撐：{tech.get("support","--")}</span>
    <span class="resistance-level">壓力：{tech.get("resistance","--")}</span>
    <span class="close-price">進場：{tech.get("entry_low","--")}~{tech.get("entry_high","--")}</span>
    <span class="target-price">目標一：{tech.get("target1","--")}</span>
    <span class="target-price">目標二：{tech.get("target2","--")}</span>
    <span class="stop-loss">停損：{tech.get("stop_loss_price","--")}</span>
  </div>
  <div class="ai-advice" style="border-left-color:{advice_border}">{_md(ai_advice)}</div>
</div>'''
        html += '</div>'
    return html


def _build_signals_html(livermore_signals, watchlist_analysis, include_entry=False):
    all_signals = dict(livermore_signals['all'])
    if watchlist_analysis:
        from modules.livermore import check_entry_signal
        for w_item in watchlist_analysis:
            w_name = w_item['name']
            if w_name not in all_signals:
                all_signals[w_name] = check_entry_signal(w_name, w_item['technical'])

    html = ''
    for name, sig in all_signals.items():
        cls = 'up' if sig['action'] == 'BUY' else ('down' if sig['action'] == 'SELL' else 'neutral')
        passed_text = ', '.join(sig['passed'][:2]) if sig['passed'] else '-'
        is_watchlist = any(w['name'] == name for w in (watchlist_analysis or []))
        row_style = ' style="background:#f1f8e9"' if is_watchlist else ''
        mark = ' ⭐' if is_watchlist else ''
        if include_entry:
            entry = sig.get('entry_range') or '--'
            target = f'<span class="target-price">{sig.get("target") or "--"}</span>'
            stop = f'<span class="stop-loss">{sig.get("stop_loss") or "--"}</span>'
            html += f'<tr{row_style}><td>{name}{mark}</td><td>{sig["recommendation"]}</td><td>{sig["score"]}</td><td class="{cls}">{sig["action"]}</td><td>{entry}</td><td>{target}</td><td>{stop}</td><td>{passed_text}</td></tr>'
        else:
            html += f'<tr{row_style}><td>{name}{mark}</td><td>{sig["recommendation"]}</td><td>{sig["score"]}</td><td class="{cls}">{sig["action"]}</td><td>{passed_text}</td></tr>'
    return html


DAILY_CSS = '''
body{font-family:"Noto Sans TC","Microsoft JhengHei",Arial,sans-serif;margin:0;padding:20px;color:#333;font-size:14px;background:#f5f5f5}
.header{background:#1a237e;color:white;padding:24px;border-radius:8px;margin-bottom:20px}
.header h1{margin:0 0 6px 0;font-size:22px}
.header p{margin:0;opacity:.85;font-size:13px}
.section{background:white;border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:16px}
.section h2{margin:0 0 14px 0;font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#e8eaf6;padding:8px;text-align:left;font-weight:600}
td{padding:7px 8px;border-bottom:1px solid #f0f0f0}
.up{color:#e74c3c;font-weight:500}.down{color:#27ae60;font-weight:500}.neutral{color:#f39c12;font-weight:500}
.close-price{color:#e74c3c;font-weight:700}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.analysis-text{line-height:1.9;font-size:13px;color:#444}
.analysis-text p{margin:6px 0}.analysis-text ul{margin:4px 0;padding-left:20px}.analysis-text li{margin:3px 0}
.analysis-text h1,.analysis-text h2,.analysis-text h3{margin:12px 0 6px 0;font-size:14px;color:#1a237e}
.short-term-title{display:block;color:#d84315;font-weight:700;font-size:14px;border-left:4px solid #d84315;padding:6px 0 6px 10px;margin:14px 0 6px 0;background:#fff3e0;border-radius:0 4px 4px 0}
.mid-term-title{display:block;color:#1565c0;font-weight:700;font-size:14px;border-left:4px solid #1565c0;padding:6px 0 6px 10px;margin:14px 0 6px 0;background:#e3f2fd;border-radius:0 4px 4px 0}
.target-price{color:#2e7d32;font-weight:700;background:#e8f5e9;padding:1px 6px;border-radius:4px}
.stop-loss{color:#b71c1c;font-weight:700;background:#ffebee;padding:1px 6px;border-radius:4px}
.support-level{color:#1565c0;font-weight:700;background:#e3f2fd;padding:1px 6px;border-radius:4px}
.resistance-level{color:#c62828;font-weight:700;background:#fff0f0;padding:1px 6px;border-radius:4px}
.stock-card{border-radius:8px;padding:14px;margin-bottom:12px;border:1px solid #c5cae9}
.stock-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.stock-title{font-size:15px;font-weight:bold}
.stock-price{font-size:15px;font-weight:bold}
.stock-meta{font-size:12px;color:#666;margin-bottom:8px;line-height:1.7}
.pattern-row{margin-bottom:8px}
.price-summary{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;padding:8px;background:#f5f5f5;border-radius:6px}
.price-summary span{font-size:12px;padding:3px 8px;border-radius:4px}
.pattern-tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:4px}
.bullish-tag{background:#e8f5e9;color:#2e7d32}.bearish-tag{background:#ffebee;color:#c62828}.neutral-tag{background:#f5f5f5;color:#666}
.ai-advice{font-size:13px;color:#444;line-height:1.8;background:white;border-radius:6px;padding:12px;border-left:3px solid #1a237e}
.ai-advice p{margin:5px 0}.ai-advice ul{padding-left:20px;margin:4px 0}.ai-advice li{margin:3px 0}
.ai-advice h1,.ai-advice h2,.ai-advice h3{font-size:13px;margin:8px 0 4px 0;color:#1a237e}
.disclaimer{background:#fff3e0;border:1px solid #ffe0b2;border-radius:6px;padding:12px;font-size:12px;color:#e65100;margin-top:16px}
'''

WEEKLY_CSS = DAILY_CSS.replace('#1a237e', '#1b5e20').replace('#e8eaf6', '#e8f5e9').replace('border:1px solid #c5cae9', 'border:1px solid #a5d6a7')


def generate_daily_report(global_markets, commodities, news,
                           global_analysis, taiwan_analysis,
                           technical_results, livermore_signals,
                           macro_data, macro_analysis,
                           watchlist_analysis, sector_recommendations):
    from datetime import timezone, timedelta
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    timestamp = now_tw.strftime('%Y-%m-%d %H:%M（台灣時間）')
    date_str = now_tw.strftime('%Y%m%d')

    def _fmt_chg(v):
        if v is None: return '<td style="color:#999;font-size:11px">--</td>'
        cls = 'up' if v > 0 else 'down'
        return f'<td class="{cls}" style="font-size:12px">{("+" if v>0 else "")}{v}%</td>'

    markets_html = ''.join(
        f'<tr><td>{n}</td><td class="close-price">{d["price"]:,}</td>'
        f'{_fmt_chg(d.get("change"))}'
        f'{_fmt_chg(d.get("change_7d"))}'
        f'{_fmt_chg(d.get("change_30d"))}'
        f'{_fmt_chg(d.get("change_60d"))}'
        f'</tr>'
        for n, d in global_markets.items()
    )
    def _fmt_chg(v):
        if v is None: return '<td style="color:#999">N/A</td>'
        cls = 'up' if v > 0 else 'down'
        return f'<td class="{cls}">{("+" if v>0 else "")}{v}%</td>'

    macro_html = ''.join(
        f'<tr><td>{n}</td><td class="close-price">{d["price"]}</td>'
        f'{_fmt_chg(d.get("change"))}'
        f'{_fmt_chg(d.get("change_7d"))}'
        f'{_fmt_chg(d.get("change_14d"))}'
        f'{_fmt_chg(d.get("change_30d"))}'
        f'{_fmt_chg(d.get("change_60d"))}'
        f'</tr>'
        for n, d in macro_data.items()
    )
    watchlist_html = _render_watchlist_html(watchlist_analysis, 'daily')
    signals_html = _build_signals_html(livermore_signals, watchlist_analysis, include_entry=True)

    html = f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet"><style>{DAILY_CSS}</style></head>
<body>
<div class="header">
  <h1>投資建議每日晨報</h1>
  <p>{timestamp} ｜ 資料來源：即時市場數據 + Claude AI 分析</p>
  <p style="font-size:11px;opacity:0.7;margin-top:4px">⚠️ 股價資料來自 yfinance，顯示最近一個交易日收盤價（台股收盤後約1小時更新）</p>
</div>
<div class="two-col">
  <div class="section"><h2>全球股市</h2>
    <table><tr><th>市場</th><th>收盤價</th><th>今日</th><th>7日</th><th>30日</th><th>60日</th></tr>{markets_html}</table>
  </div>
  <div class="section"><h2>美債／黃金／石油</h2>
    <table><tr><th>資產</th><th>價格</th><th>今日</th><th>7日</th><th>14日</th><th>30日</th><th>60日</th></tr>{macro_html}</table>
  </div>
</div>
<div class="section"><h2>美債／黃金／石油 白話解析</h2>
  <div class="analysis-text">{_md(macro_analysis)}</div>
</div>
<div class="section"><h2>全球市場 AI 分析</h2>
  <div class="analysis-text">{_md(global_analysis)}</div>
</div>
<div class="section"><h2>台股分析與投資建議</h2>
  <div class="analysis-text">{_md(taiwan_analysis)}</div>
</div>
<div class="section"><h2>持股追蹤（依產業分組）</h2>
  {watchlist_html}
</div>
<div class="section"><h2>產業投資方向建議</h2>
  <div class="analysis-text">{_md(sector_recommendations)}</div>
</div>
<div class="section"><h2>李佛摩法則訊號總覽</h2>
  <table><tr><th>股票</th><th>建議</th><th>分數</th><th>動作</th><th>進場區間</th><th>目標價</th><th>停損價</th><th>通過條件</th></tr>
  {signals_html}</table>
</div>
<div class="disclaimer">免責聲明：本報表為自動化系統產生，所有分析與建議僅供學習參考，不構成實際投資建議。投資有風險，請自行評估後謹慎決策。</div>
</body></html>'''

    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    filepath = os.path.join(config.REPORTS_DIR, f'daily_report_{date_str}.html')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'報表已產生：{filepath}')
    return filepath


def generate_weekly_report(global_markets, commodities, news,
                            global_weekly_analysis, taiwan_weekly_analysis,
                            technical_results, livermore_signals,
                            macro_data, macro_analysis,
                            watchlist_analysis, sector_recommendations,
                            week_range):
    from datetime import timezone, timedelta
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    timestamp = now_tw.strftime('%Y-%m-%d %H:%M（台灣時間）')
    date_str = now_tw.strftime('%Y%m%d')

    def _fmt_chg(v):
        if v is None: return '<td style="color:#999;font-size:11px">--</td>'
        cls = 'up' if v > 0 else 'down'
        return f'<td class="{cls}" style="font-size:12px">{("+" if v>0 else "")}{v}%</td>'

    markets_html = ''.join(
        f'<tr><td>{n}</td><td class="close-price">{d["price"]:,}</td>'
        f'{_fmt_chg(d.get("change"))}'
        f'{_fmt_chg(d.get("change_7d"))}'
        f'{_fmt_chg(d.get("change_30d"))}'
        f'{_fmt_chg(d.get("change_60d"))}'
        f'</tr>'
        for n, d in global_markets.items()
    )
    def _fmt_chg(v):
        if v is None: return '<td style="color:#999">N/A</td>'
        cls = 'up' if v > 0 else 'down'
        return f'<td class="{cls}">{("+" if v>0 else "")}{v}%</td>'

    macro_html = ''.join(
        f'<tr><td>{n}</td><td class="close-price">{d["price"]}</td>'
        f'{_fmt_chg(d.get("change"))}'
        f'{_fmt_chg(d.get("change_7d"))}'
        f'{_fmt_chg(d.get("change_14d"))}'
        f'{_fmt_chg(d.get("change_30d"))}'
        f'{_fmt_chg(d.get("change_60d"))}'
        f'</tr>'
        for n, d in macro_data.items()
    )
    watchlist_html = _render_watchlist_html(watchlist_analysis, 'weekly')
    signals_html = _build_signals_html(livermore_signals, watchlist_analysis, include_entry=True)

    html = f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet"><style>{WEEKLY_CSS}</style></head>
<body>
<div class="header">
  <h1>投資建議週報</h1>
  <p>{timestamp} ｜ 資料來源：即時市場數據 + Claude AI 分析</p>
  <div class="week-badge">{week_range}</div>
  <p style="font-size:11px;opacity:0.7;margin-top:4px">⚠️ 股價資料來自 yfinance，顯示最近一個交易日收盤價（台股收盤後約1小時更新）</p>
</div>
<div class="two-col">
  <div class="section"><h2>本週全球股市</h2>
    <table><tr><th>市場</th><th>收盤價</th><th>本週</th><th>7日</th><th>30日</th><th>60日</th></tr>{markets_html}</table>
  </div>
  <div class="section"><h2>美債／黃金／石油</h2>
    <table><tr><th>資產</th><th>價格</th><th>週漲跌</th></tr>{macro_html}</table>
  </div>
</div>
<div class="section"><h2>美債／黃金／石油 白話週解析</h2>
  <div class="analysis-text">{_md(macro_analysis)}</div>
</div>
<div class="section"><h2>全球市場本週回顧 + 下週展望</h2>
  <div class="analysis-text">{_md(global_weekly_analysis)}</div>
</div>
<div class="section"><h2>台股本週回顧 + 下週操作建議</h2>
  <div class="analysis-text">{_md(taiwan_weekly_analysis)}</div>
</div>
<div class="section"><h2>持股追蹤（依產業分組）— 下週操作建議</h2>
  {watchlist_html}
</div>
<div class="section"><h2>下週產業投資方向建議</h2>
  <div class="analysis-text">{_md(sector_recommendations)}</div>
</div>
<div class="section"><h2>李佛摩法則訊號總覽</h2>
  <table><tr><th>股票</th><th>建議</th><th>分數</th><th>動作</th><th>進場區間</th><th>目標價</th><th>停損價</th><th>通過條件</th></tr>
  {signals_html}</table>
</div>
<div class="disclaimer">免責聲明：本報表為自動化系統產生，所有分析與建議僅供學習參考，不構成實際投資建議。投資有風險，請自行評估後謹慎決策。</div>
</body></html>'''

    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    filepath = os.path.join(config.REPORTS_DIR, f'weekly_report_{date_str}.html')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'週報已產生：{filepath}')
    return filepath
