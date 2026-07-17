"""
§四十四（2026-07-17）— 健檢 🔴 安全三項

S1：/debug-oauth 洩密端點刪除（source guard）
S2：OAuth email allowlist（_email_allowed 純函式；未設定=開放向後相容）
S3：股票名稱/symbol Stored XSS escape（後端 _render_one_block）
"""
import sys, os, datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as appmod
from modules.auth import _email_allowed


# ── S1：debug-oauth 已刪 ─────────────────────────────────────────
def test_debug_oauth_route_removed():
    import inspect
    src = inspect.getsource(appmod)
    assert "@app.route('/debug-oauth')" not in src, '/debug-oauth 洩密端點應已刪除'
    assert 'def debug_oauth' not in src


# ── S2：allowlist 純函式 ─────────────────────────────────────────
class TestEmailAllowed:
    def test_unset_env_open(self):
        """未設定 ALLOWED_EMAILS → 開放（向後相容，避免鎖死既有用戶）。"""
        assert _email_allowed('anyone@gmail.com', '') is True
        assert _email_allowed('anyone@gmail.com', '   ') is True

    def test_match_allowed(self):
        assert _email_allowed('frodo@gmail.com',
                              'frodo@gmail.com,family@gmail.com') is True

    def test_case_insensitive_and_whitespace(self):
        assert _email_allowed('Frodo@Gmail.com',
                              ' frodo@gmail.com , family@gmail.com ') is True

    def test_not_in_list_rejected(self):
        assert _email_allowed('attacker@evil.com',
                              'frodo@gmail.com,family@gmail.com') is False

    def test_empty_email_rejected_when_list_set(self):
        assert _email_allowed('', 'frodo@gmail.com') is False
        assert _email_allowed(None, 'frodo@gmail.com') is False


# ── S3：XSS escape ──────────────────────────────────────────────
def _stock(name, symbol='6533'):
    return SimpleNamespace(symbol=symbol, name=name, status='watching',
                           avg_cost=None, total_zhang=None, trades=False)


def _analysis():
    return SimpleNamespace(html_content='<p>x</p>', support_price=None,
                           resistance_price=None, target_price=None,
                           stop_loss=None, entry_low=None, entry_high=None,
                           wyckoff_phase=None, risk_pct=35, action_pill=None)


def test_stock_name_xss_escaped():
    """自訂股票名稱含 <script> → 輸出 HTML 須 escape，不得原樣注入。"""
    html = appmod._render_one_block(
        _stock('<script>alert(1)</script>'), _analysis(), None,
        idx=1, mode='watching')
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_symbol_xss_escaped():
    html = appmod._render_one_block(
        _stock('正常股', symbol='"><img src=x onerror=alert(1)>'),
        _analysis(), None, idx=1, mode='watching')
    assert '<img src=x' not in html


def test_normal_name_unchanged():
    """回歸：一般中文名稱原樣輸出。"""
    html = appmod._render_one_block(_stock('晶心科'), _analysis(), None,
                                    idx=1, mode='watching')
    assert '晶心科' in html
