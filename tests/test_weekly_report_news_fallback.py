"""C6 / Bug I1（2026-05-24）— 週末 NEWS regen + DB fallback。

5/22 週五 20:35 週末視窗報表 INDUSTRY 顯示「⚠️ 本次無新聞資料」全推斷。
根因：dashboard.js 週末分支沒呼叫 /api/news/regenerate（日報路徑有）
+ run_weekly_report.py RSS 抓空無 DB fallback。

修法：
1. dashboard.js 週末視窗加 /api/news/regenerate 呼叫（與日報對稱）
2. run_weekly_report.py 抓出 _resolve_industry_news 純函式：RSS 空時讀 DB
   DailyMarketSummary 最近 7 天 fallback
3. get_industry_indicator_stocks 接受 news_fallback_note 參數，prompt 注入
   告知 AI 標明來源

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C6
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datetime import date, timedelta
from unittest.mock import MagicMock


# ============================================================
# C6-T1：_resolve_industry_news — RSS 有資料 → 直接用 RSS, fallback_note=None
# ============================================================
def test_resolve_uses_rss_when_available():
    from run_weekly_report import _resolve_industry_news
    rss = [{'title': '新聞 A'}, {'title': '新聞 B'}]
    db = MagicMock()
    news, note = _resolve_industry_news(rss, db, today=date(2026, 5, 24))
    assert news == rss
    assert note is None
    db.query.assert_not_called(), 'RSS 有就不該查 DB'


# ============================================================
# C6-T2：_resolve_industry_news — RSS 空 + DB 有近 7 天記錄 → fallback 標明來源
# ============================================================
def test_resolve_falls_back_to_db_when_rss_empty():
    from run_weekly_report import _resolve_industry_news
    rss = []
    db = MagicMock()
    fake_summary = MagicMock(summary_date=date(2026, 5, 22), html_content='<div>5/22 新聞摘要</div>')
    db.query().filter().order_by().first.return_value = fake_summary
    news, note = _resolve_industry_news(rss, db, today=date(2026, 5, 24))
    assert news == [], '已 fallback DB 時 news 仍是 []（fallback 走 html，非 RSS list）'
    assert note is not None
    assert '2026-05-22' in note, 'note 須含 DB 快取日期'
    assert 'DB' in note or 'DailyMarketSummary' in note or '快取' in note, \
        'note 須標明來源是 DB 快取'


# ============================================================
# C6-T3：_resolve_industry_news — RSS 空 + DB 也無 → note 標明全無
# ============================================================
def test_resolve_no_data_returns_explicit_note():
    from run_weekly_report import _resolve_industry_news
    rss = []
    db = MagicMock()
    db.query().filter().order_by().first.return_value = None
    news, note = _resolve_industry_news(rss, db, today=date(2026, 5, 24))
    assert news == []
    assert note is not None
    assert 'RSS' in note and ('DB' in note or '快取' in note), \
        'note 須明示 RSS 與 DB 皆無'


# ============================================================
# C6-T4：get_industry_indicator_stocks 接收 news_fallback_note，prompt 注入
# ============================================================
def test_industry_indicator_accepts_fallback_note(monkeypatch):
    import modules.ai_analyzer_v2 as mod
    captured = {}
    def fake(prompt, max_tokens=1024):
        captured['prompt'] = prompt
        return '<div>fake</div>'
    monkeypatch.setattr(mod, '_generate', fake)

    note = '（新聞來源：2026-05-22 DB 快取，無 RSS 即時資料）'
    mod.get_industry_indicator_stocks([], '全球市場背景', news_fallback_note=note)

    assert note in captured['prompt'], 'fallback_note 須注入 prompt 讓 AI 標明來源'


# ============================================================
# C6-T5：dashboard.js 週末分支字串含 /api/news/regenerate
# ============================================================
def test_dashboard_weekly_branch_triggers_news_regen():
    """確認 dashboard.js source 在週末分支有 /api/news/regenerate 呼叫。"""
    js_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'dashboard.js')
    with open(js_path, encoding='utf-8') as f:
        js = f.read()

    # 找 isWeeklyWindow() 後的 block — 須含 /api/news/regenerate
    weekly_idx = js.find('if (isWeeklyWindow())')
    assert weekly_idx > 0, '應有 isWeeklyWindow() 分支'
    end_idx = js.find('} else {', weekly_idx)
    if end_idx < 0:
        end_idx = weekly_idx + 1500
    weekly_block = js[weekly_idx:end_idx]
    assert '/api/news/regenerate' in weekly_block, \
        '週末視窗分支須觸發 /api/news/regenerate（與日報路徑對稱）'
