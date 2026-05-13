"""TWII freshness 驗證：注入 AI prompt 前必須確認 last_date == today TW。

Regression 來源：2026-05-13 用戶回報「今日財經新聞的大盤數字是昨日的」。
前次 fde93e5 只擋 AI 從訓練資料引用歷史數字（"1778點"/"破3萬點"），
但若資料源本身就回傳昨日 bar（Yahoo 1d chart 在盤前/Render IP 限流情境），
AI 仍會忠實複述「今日大盤 X 點」實際是昨日的 X。

修法在資料層加 freshness check，比照 _resolve_quote 個股 stale 偵測 pattern。
"""
import pytest
from datetime import date


# ── _fetch_ticker source 必含 last_date 欄位（讓上游可驗 freshness）──
def test_fetch_ticker_source_returns_last_date_field():
    """_fetch_ticker 成功與失敗 fallback 兩條 path 都必須有 last_date 欄位。
    讀 source 避免 import yfinance / curl_cffi 等重 dep。"""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / 'modules' / 'data_fetcher.py').read_text(encoding='utf-8')
    start = src.index('def _fetch_ticker(')
    end = src.index('\ndef ', start + 1)
    func_src = src[start:end]
    # 成功 path 與 fallback path 都要有 last_date
    assert func_src.count("'last_date'") >= 2, (
        "_fetch_ticker 需在 success path 與 fallback path 都有 last_date 欄位"
    )


# ── freshness check 邏輯（純函式測試，不打網路）────────────────────
def _check_twii_fresh(twii_data, today_str):
    """模擬 app.py:/api/news/regenerate 與 run_daily_report.py 的 freshness 邏輯。
    回傳 (twii_price, twii_change_pct)。stale 時都回 None。"""
    if not twii_data:
        return None, None
    if twii_data.get('last_date') == today_str:
        return twii_data.get('price'), twii_data.get('change')
    return None, None


def test_fresh_twii_passes_through():
    today = '2026-05-13'
    fresh = {'last_date': '2026-05-13', 'price': 22500.0, 'change': 1.5}
    p, c = _check_twii_fresh(fresh, today)
    assert p == 22500.0
    assert c == 1.5


def test_yesterday_twii_blocked():
    """若 TWII bar 是昨日（盤前 Yahoo 未更新）→ 不注入 → AI prompt 不會錯誤複述昨日數字。"""
    today = '2026-05-13'
    stale = {'last_date': '2026-05-12', 'price': 22300.0, 'change': -0.5}
    p, c = _check_twii_fresh(stale, today)
    assert p is None
    assert c is None


def test_missing_last_date_blocked():
    """fallback path 回 last_date=None，視同 stale。"""
    today = '2026-05-13'
    broken = {'last_date': None, 'price': 0, 'change': 0}
    p, c = _check_twii_fresh(broken, today)
    assert p is None
    assert c is None


def test_empty_data_blocked():
    """整個 dict 為空時不會 KeyError。"""
    p, c = _check_twii_fresh({}, '2026-05-13')
    assert p is None
    assert c is None


def test_none_data_blocked():
    p, c = _check_twii_fresh(None, '2026-05-13')
    assert p is None
    assert c is None


# ── analyze_daily_news 當 twii_price=None 時不注入大盤 block ─────
def test_analyze_daily_news_no_twii_block_when_price_none():
    """確認 analyze_daily_news 在 twii_price=None 時 prompt 不含「今日大盤資訊」block。
    這保證 stale 情境下 AI 不會被餵任何大盤數字。
    讀 source 而非 import 模組（避免 anthropic SDK 依賴）。"""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / 'modules' / 'ai_analyzer_v2.py').read_text(encoding='utf-8')
    # 取 analyze_daily_news 函式區段
    start = src.index('def analyze_daily_news(')
    end = src.index('\ndef ', start + 1)
    func_src = src[start:end]
    # 條件分支：有 twii 才注入 twii_block
    assert 'twii_price and twii_change_pct is not None' in func_src
    # else 分支：空字串
    assert "twii_block = ''" in func_src
    # prompt 模板：注入點存在
    assert '{twii_block}' in func_src
