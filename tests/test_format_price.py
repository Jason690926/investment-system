"""_format_price 依 TWSE 申報價格升降單位（tick）回傳格式化字串。

Regression 來源：2026-05-13 用戶回報創惟（6104）收盤 100.5 顯示 100、
矽力-KY（6415）收盤 467.5 顯示 468，根因為 :.0f 對 ≥100 banker's rounding。
"""
from app import _format_price


# ── 用戶實際回報的 bug case ────────────────────────────────
def test_user_case_6104_chuangwei_100_5():
    """創惟（6104）收盤 100.5 必須顯示 100.5（不能被 banker's rounding 吞成 100）"""
    assert _format_price(100.5) == '100.5'


def test_user_case_6415_silergy_467_5():
    """矽力-KY（6415）收盤 467.5 必須顯示 467.5（不能被 banker's rounding 變成 468）"""
    assert _format_price(467.5) == '467.5'


# ── tick 區間覆蓋 ────────────────────────────────────────
# < 10 元，tick 0.01，必須 2 dp
def test_below_10_two_decimals():
    assert _format_price(9.99) == '9.99'
    assert _format_price(5.05) == '5.05'


# 10–50 元，tick 0.05，必須 2 dp
def test_10_to_50_two_decimals():
    assert _format_price(10.05) == '10.05'
    assert _format_price(49.95) == '49.95'


# 50–100 元，tick 0.10，1 dp 即可
def test_50_to_100_one_decimal():
    assert _format_price(50.0) == '50.0'
    assert _format_price(99.9) == '99.9'


# 100–500 元，tick 0.50（CORE BUG ZONE）
def test_100_to_500_one_decimal():
    assert _format_price(100.0) == '100.0'
    assert _format_price(100.5) == '100.5'
    assert _format_price(250.5) == '250.5'
    assert _format_price(499.5) == '499.5'


# 500–1000 元，tick 1.00，整數
def test_500_to_1000_integer():
    assert _format_price(500) == '500'
    assert _format_price(999) == '999'


# ≥1000 元，tick 5.00，整數 + 千分位
def test_above_1000_integer_with_comma():
    assert _format_price(1000) == '1,000'
    assert _format_price(1235) == '1,235'
    assert _format_price(2500) == '2,500'


# ── 邊界值 ────────────────────────────────────────────────
def test_boundary_49_99_uses_2dp():
    """49.99 剛好低於 50，走 2 dp 區段。"""
    assert _format_price(49.99) == '49.99'


def test_boundary_50_uses_1dp():
    """50 剛好進入 1 dp 區段。"""
    assert _format_price(50) == '50.0'


def test_boundary_499_99_uses_1dp():
    """499.99 剛好低於 500（其實 .5 tick 不會產生 .99，但邊界仍要正確）。"""
    assert _format_price(499.99) == '500.0'  # 1 dp 進位


def test_boundary_500_uses_0dp():
    """500 剛好進入 0 dp 區段。"""
    assert _format_price(500) == '500'


# ── 特殊值 ────────────────────────────────────────────────
def test_none_returns_em_dash():
    assert _format_price(None) == '—'


def test_decimal_input_accepted():
    """SQLAlchemy 從 Numeric 欄位讀出來常為 Decimal，必須能轉 float。"""
    from decimal import Decimal
    assert _format_price(Decimal('100.5')) == '100.5'
    assert _format_price(Decimal('467.5')) == '467.5'


def test_int_input_accepted():
    assert _format_price(100) == '100.0'
    assert _format_price(500) == '500'


# ── 反例：確認舊 bug 已修 ─────────────────────────────────
def test_regression_no_banker_rounding_on_half():
    """關鍵 regression：以前 :.0f 對 100.5/467.5 各往不同方向湊偶數。
    修法後 100–500 區間一律 1 dp，根本不再 round 整數。"""
    # 100.5 修法前 → '100'（100 偶數）；修法後應為 '100.5'
    assert '.' in _format_price(100.5)
    # 467.5 修法前 → '468'（468 偶數）；修法後應為 '467.5'
    assert '.' in _format_price(467.5)
