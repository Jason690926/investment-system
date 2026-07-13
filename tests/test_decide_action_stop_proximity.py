"""F2 §三十九（2026-07-13）— 空停零距離防護 + 一字漲停抑制佈空。

根因：short entry_zone=(mid, swing_high)、invalidation=swing_high →
價在區頂 = 停損零距離。晶心科 7/13 現價 210.5＝空停 210.5（且一字漲停鎖死）
仍標 🔴 分批佈空；采鈺距空停僅 1.31%。§三十四 Bug-3 只在區底加 0.5% buffer，
區頂無對稱防護。

修法：
- `_decide_action` short 在區內分支加雙 gate：
  (a) price ≥ 空停參考價（invalidation，缺則 zone 頂）× 0.98 → 🟡 等反轉佈空
  (b) limit_up_today=True（今日一字漲停鎖死）→ 🟡 等反轉佈空
- 新純函式 `_limit_up_locked_today`（漲幅≥9% + close≥high×0.99）

plan §三十九 / F2
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _decide_action, _limit_up_locked_today


def _swing_short(rl=100, rh=120, target=80):
    """構造 short swing_levels dict。entry_zone=(mid, rh)、invalidation=rh。"""
    mid = (rl + rh) / 2
    return {
        'direction': 'short',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (mid, rh),
        'invalidation': rh,
        'target': target,
    }


# ============================================================
# F2-T1：晶心科場景 — 現價 = 空停（零距離）→ 🟡 等反轉佈空
# ============================================================
def test_short_price_at_stop_downgraded():
    """現價 210.5 = zone 頂 = invalidation 210.5 → 不可標分批佈空"""
    sl = _swing_short(rl=189.5, rh=210.5)
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False,
        price=210.5,
    )
    assert action == '🟡 等反轉佈空'


# ============================================================
# F2-T2：采鈺場景 — 距空停 1.31%（< 2%）→ 🟡 等反轉佈空
# ============================================================
def test_short_price_within_2pct_of_stop_downgraded():
    """現價 535、空停 542 → 距離 1.31% < 2% → 等反轉佈空"""
    sl = _swing_short(rl=494, rh=542)
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False,
        price=535,
    )
    assert action == '🟡 等反轉佈空'


# ============================================================
# F2-T3：距空停 > 2% 且在區內 → 維持 🔴 分批佈空（不誤殺）
# ============================================================
def test_short_in_zone_far_from_stop_still_short_in():
    """rl=100, rh=120：區=(110,120)。價 112 距空停 120 有 6.7% → 分批佈空維持"""
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=112,
    )
    assert action == '🔴 分批佈空'


# ============================================================
# F2-T4：一字漲停日 — 即使在區內距空停遠，也不建議佈空
# ============================================================
def test_short_limit_up_today_downgraded():
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=112,
        limit_up_today=True,
    )
    assert action == '🟡 等反轉佈空'


# ============================================================
# F2-T5：站回空停之上 → 🔴 論點作廢 優先級不變
# ============================================================
def test_short_above_invalidation_still_invalid():
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=125,
        limit_up_today=True,
    )
    assert action == '🔴 論點作廢'


# ============================================================
# F2-T6：區下方等反彈佈空不受影響（limit_up 也不改語義）
# ============================================================
def test_short_below_zone_unchanged():
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=_swing_short(rl=100, rh=120), breakout=False,
        price=105,
        limit_up_today=True,
    )
    assert action == '🟡 等反彈佈空'


# ============================================================
# F2-T7：invalidation 缺失 → 用 zone 頂當空停參考價
# ============================================================
def test_short_stop_ref_falls_back_to_zone_top():
    sl = _swing_short(rl=100, rh=120)
    sl['invalidation'] = None
    action = _decide_action(
        status='watch', direction='short',
        structure_flag='結構已轉弱',
        swing_levels=sl, breakout=False,
        price=119,  # 距 zone 頂 120 僅 0.8%
    )
    assert action == '🟡 等反轉佈空'


# ============================================================
# F2-T8：long 路徑完全不受 limit_up_today 影響（參數向後相容）
# ============================================================
def test_long_path_ignores_limit_up_param():
    sl = {
        'direction': 'long',
        'range_low': 100, 'range_high': 120,
        'entry_zone': (100, 110),
        'invalidation': 100,
        'target': 130,
    }
    action = _decide_action(
        status='watch', direction='long',
        structure_flag='結構未轉弱',
        swing_levels=sl, breakout=False,
        price=105,
        limit_up_today=True,
    )
    assert action == '🟢 進場區可佈'


# ---------- _limit_up_locked_today 純函式 ----------

def _bar(c, h=None, o=None, l=None):
    h = h if h is not None else c
    o = o if o is not None else c
    l = l if l is not None else c
    return {'open': o, 'high': h, 'low': l, 'close': c, 'volume_zhang': 100}


# ============================================================
# F2-T9：一字漲停鎖死（晶心科 7/13：191.5 → 210.5 = +9.92%，O=H=L=C）
# ============================================================
def test_limit_up_locked_detected():
    bars = [_bar(191.5, h=195, o=193, l=191), _bar(210.5)]
    assert _limit_up_locked_today(bars) is True


# ============================================================
# F2-T10：漲停但尾盤打開（close < high×0.99）→ 不算鎖死
# ============================================================
def test_limit_up_opened_not_locked():
    """+9.2% 收但尾盤打開（close 109.2 < high 110.5 × 0.99）→ 不算鎖死"""
    bars = [_bar(100, h=101, o=100, l=99),
            _bar(109.2, h=110.5, o=105, l=104)]
    assert _limit_up_locked_today(bars) is False


# ============================================================
# F2-T11：普通上漲日 → False；資料不足 → False
# ============================================================
def test_normal_day_and_insufficient_data():
    bars = [_bar(100, h=101, o=100, l=99), _bar(103, h=104, o=101, l=100)]
    assert _limit_up_locked_today(bars) is False
    assert _limit_up_locked_today([_bar(100)]) is False
    assert _limit_up_locked_today([]) is False
    assert _limit_up_locked_today(None) is False
