"""§四十六（2026-07-21）：7/21 報告 cross-check 四修法測試。

Fix A — PDF pill 誠實化：強跌反彈觀望（short）/ 強漲回測觀望（long）股
        `_render_one_block` pill 不再印殘留空進/箱頂區間，改「失效 + 待新箱」
        （鏡像 dashboard strip §三十八 #2 / §四十三 R1 既有誠實行為）。
Fix C — `_render_operation_framework` target「—」且無 relaxed note 時砍
        「— 元（P&F 下行目標）」殘句（東捷 7/21 案例；long 同構）。
Fix D — `_relaxed_sentence_from_info` reached 且遠古（偏離 >1.5×）→ 不引
        遠古數字（合晶 7/21 價 130 引 41.9 案例）。
Fix B — `_dual_swing_block` R6 追加「失效」字眼專屬鐵律（矽力 §1 壓力 554
        被稱「錨點失效線」但錨點失效=645 案例；prompt 行為需重跑實證，
        此處僅驗注入文字存在）。
"""
from decimal import Decimal
from datetime import date
from types import SimpleNamespace

import pytest

from app import _render_one_block
from modules.ai_analyzer_v2 import (
    _render_operation_framework,
    _relaxed_sentence_from_info,
    _dual_swing_block,
)


# ─────────────────────── helpers（沿用 test_print_report 模式） ───────────────────────

def _stock(**ov):
    d = dict(symbol='6415', name='矽力', status='watching',
             avg_cost=None, total_zhang=None, trades=[])
    d.update(ov)
    return SimpleNamespace(**d)


def _quote(close='461.5', prev='427.5'):
    return SimpleNamespace(symbol='6415', close=Decimal(close),
                           prev_close=Decimal(prev),
                           cache_date=date(2026, 7, 21))


def _analysis_short(**ov):
    """矽力 7/21 場景：short + 強跌反彈觀望。"""
    d = dict(symbol='6415', risk_pct=62, wyckoff_phase='下跌',
             support_price=Decimal('414.5'), resistance_price=Decimal('645'),
             target_price=None, stop_loss=Decimal('645'),
             entry_low=Decimal('600'), entry_high=Decimal('645'),
             action_pill='🟡 強跌反彈觀望',
             analysis_date=date(2026, 7, 21), html_content='<p>x</p>')
    d.update(ov)
    return SimpleNamespace(**d)


def _analysis_long(**ov):
    """合晶 7/21 場景：long + 強漲回測觀望。"""
    d = dict(symbol='6182', risk_pct=42, wyckoff_phase='上漲',
             support_price=Decimal('106.5'), resistance_price=Decimal('194.5'),
             target_price=None, stop_loss=Decimal('106.5'),
             entry_low=Decimal('106.5'), entry_high=Decimal('150.5'),
             action_pill='🟡 強漲回測觀望',
             analysis_date=date(2026, 7, 21), html_content='<p>x</p>')
    d.update(ov)
    return SimpleNamespace(**d)


# ─────────────────────── Fix A：PDF pill 誠實化 ───────────────────────

def test_short_pullback_watch_pill_drops_entry_zone():
    """強跌反彈觀望：pill 不再印空進區間/空標，改失效 + 待新箱。"""
    html = _render_one_block(_stock(), _analysis_short(), _quote(),
                             idx=2, mode='watching')
    assert '空進' not in html
    assert '空標' not in html
    assert '失效' in html
    assert '645' in html          # 失效價 = stop_loss
    assert '待新箱' in html


def test_short_normal_watch_pill_keeps_entry_zone():
    """回歸：等反彈佈空（非觀望 gate）pill 照常印空進區間。"""
    a = _analysis_short(action_pill='🟡 等反彈佈空',
                        entry_low=Decimal('62.7'), entry_high=Decimal('65'),
                        stop_loss=Decimal('65'), target_price=Decimal('56.7'))
    html = _render_one_block(_stock(symbol='6150', name='撼訊'), a,
                             _quote(close='58.4', prev='55.6'),
                             idx=5, mode='watching')
    assert '空進' in html
    assert '62.70~65.0' in html.replace(',', '') or '62.7' in html
    assert '空停' in html
    assert '空標' in html


def test_long_pullback_watch_pill_drops_box():
    """強漲回測觀望：pill 不再印箱底/箱頂/目標，改失效 + 待新箱。"""
    html = _render_one_block(_stock(symbol='6182', name='合晶'),
                             _analysis_long(),
                             _quote(close='130', prev='135'),
                             idx=7, mode='watching')
    assert '箱底' not in html
    assert '箱頂' not in html
    assert '目標' not in html
    assert '失效' in html
    assert '106.5' in html
    assert '待新箱' in html


def test_long_normal_watch_pill_keeps_box():
    """回歸：一般 long 股 pill 照常印箱底/箱頂/目標。"""
    a = _analysis_long(action_pill='🟡 等回測',
                       support_price=Decimal('136'),
                       resistance_price=Decimal('153'),
                       target_price=Decimal('157'),
                       entry_low=Decimal('136'), entry_high=Decimal('144.5'))
    html = _render_one_block(_stock(symbol='2377', name='微星'), a,
                             _quote(close='146', prev='141.5'),
                             idx=4, mode='watching')
    assert '箱底' in html
    assert '箱頂' in html
    assert '目標' in html


def test_long_pullback_stop_falls_back_to_support():
    """long 觀望股 stop_loss 缺（舊資料）→ 失效 fallback support_price。"""
    a = _analysis_long(stop_loss=None)
    html = _render_one_block(_stock(symbol='6182', name='合晶'), a,
                             _quote(close='130', prev='135'),
                             idx=7, mode='watching')
    assert '失效' in html
    assert '106.5' in html


def test_neutral_pill_unaffected_by_pullback_text():
    """neutral 股（相位反推 neutral）不觸發誠實 pill 分支。"""
    a = _analysis_long(wyckoff_phase='盤整', action_pill='⚪ 觀望',
                       target_price=None)
    html = _render_one_block(_stock(), a, _quote(), idx=1, mode='watching')
    assert '撐' in html
    assert '壓' in html


# ─────────────────────── Fix C：§5 空值殘句 ───────────────────────

def test_short_framework_no_target_no_note_clean_sentence():
    """東捷 7/21：target=None 且無 relaxed note → 不再「— 元（P&F 下行目標）」。"""
    sl = {'range_high': 147.0, 'entry_zone': (134.0, 147.0),
          'target': None, 'invalidation': 147.0}
    out = _render_operation_framework('🟡 等反彈佈空', 'short', sl,
                                       breakout=False, price=112.0,
                                       target_note=None)
    assert '— 元' not in out
    assert '空標：—（無有效箱體，等新箱形成）' in out


def test_short_framework_with_target_unchanged():
    """回歸：有空標時句式不變。"""
    sl = {'range_high': 65.0, 'entry_zone': (62.7, 65.0),
          'target': 56.7, 'invalidation': 65.0}
    out = _render_operation_framework('🟡 等反彈佈空', 'short', sl,
                                       breakout=False, price=58.4,
                                       target_note=None)
    assert '空標：56.70 元（P&amp;F 下行目標）' in out


def test_short_framework_with_note_unchanged():
    """回歸：R4 relaxed note 句式不變。"""
    sl = {'range_high': 247.0, 'entry_zone': (218.25, 247.0),
          'target': None, 'invalidation': 247.0}
    out = _render_operation_framework('🔴 分批佈空', 'short', sl,
                                       breakout=False, price=234.5,
                                       target_note='需先跌破 213 元後估 176 元')
    assert '需先跌破 213 元後估 176 元（P&amp;F 下行）' in out


def test_long_framework_no_target_no_note_clean_sentence():
    """long 同構：target=None 且無 note → 不再「目標：— 元」。"""
    sl = {'range_high': 150.5, 'entry_zone': (106.5, 150.5),
          'target': None, 'invalidation': 106.5}
    out = _render_operation_framework('🟢 進場區可佈', 'long', sl,
                                       breakout=False, price=130.0,
                                       vol_threshold_zhang=152122,
                                       target_note=None)
    assert '目標：— 元' not in out
    assert '目標：—（無有效箱體，等新箱形成）' in out


# ─────────────────────── Fix D：reached 遠古目標 guard ───────────────────────

def test_reached_stale_long_drops_ancient_number():
    """合晶 7/21：價 130 vs 遠古目標 41.9（3.1×）→ 不引數字。"""
    s = _relaxed_sentence_from_info('long', (41.9, 36.2, 'reached'), 130.0)
    assert '41.9' not in s
    assert '36.2' not in s
    assert '—' in s
    assert '早已達成' in s


def test_reached_recent_long_keeps_number():
    """回歸：近期已達成（偏離 <1.5×）保留數字句。"""
    s = _relaxed_sentence_from_info('long', (110, 100, 'reached'), 130.0)
    assert '110 元已達成' in s
    assert '突破點 100 元' in s


def test_reached_recent_short_keeps_number():
    """矽力 7/21：461.5 vs 515（0.90×）→ 保留。"""
    s = _relaxed_sentence_from_info('short', (515, 580, 'reached'), 461.5)
    assert '515 元已達成' in s
    assert '跌破點 580 元' in s


def test_reached_stale_short_drops_ancient_number():
    """short 鏡像：價 30 vs 目標 100（price < target/1.5）→ 不引數字。"""
    s = _relaxed_sentence_from_info('short', (100, 120, 'reached'), 30.0)
    assert '100' not in s
    assert '—' in s
    assert '早已達成' in s


# ─────────────────────── Fix B：R6「失效」字眼鐵律注入 ───────────────────────

def _bars(n=60, base=100.0):
    out = []
    for i in range(n):
        p = base + (i % 7) - 3
        out.append({'date': f'2026-05-{(i % 28) + 1:02d}',
                    'open': p, 'high': p + 2, 'low': p - 2,
                    'close': p + 1, 'volume': 1000})
    return out


def test_dual_swing_block_contains_invalidation_word_rule():
    block = _dual_swing_block({'daily_bars': _bars()}, 100.0)
    assert '「失效」' in block or '失效線' in block
    assert '禁' in block
