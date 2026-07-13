"""F1 §四十（2026-07-13）— 剔除 Yahoo 休市/停牌佔位假棒。

根因：Yahoo 對休市/停牌日偶回「O=H=L=C=前收、Volume=null/0」佔位棒
（2026-07-10 案例：12 檔全中）。假棒讓 PDF K 表印出 "None"、被標
「縮量·極低位」特徵餵 AI、拉低 5 日均量使放量判定與突破量門檻失真。

修法：`_drop_degenerate_bars` — (Volume isna 或 ==0) 且 O==H==L==C → 整列 drop。
真一字漲停 O=H=L=C 但量 > 0，不受影響。

plan §四十 / F1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd
from modules.data_enricher import _drop_degenerate_bars


def _df(rows):
    """rows = [(date_str, O, H, L, C, V), ...]；V 可為 None/np.nan"""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {'Open':   [r[1] for r in rows],
         'High':   [r[2] for r in rows],
         'Low':    [r[3] for r in rows],
         'Close':  [r[4] for r in rows],
         'Volume': [r[5] for r in rows]},
        index=idx,
    ).rename_axis('Date')


# ============================================================
# F1-T1：7/10 真實場景 — 全平 + Volume=NaN → drop
# ============================================================
def test_flat_bar_with_nan_volume_dropped():
    """晶心科 7/10 場景：O=H=L=C=191.5（=前日收）、Volume=NaN → 整列剔除"""
    df = _df([
        ('2026-07-09', 193.0, 195.0, 191.0, 191.5, 144100),
        ('2026-07-10', 191.5, 191.5, 191.5, 191.5, np.nan),
        ('2026-07-13', 210.5, 210.5, 210.5, 210.5, 615800),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 2
    assert '2026-07-10' not in out.index.strftime('%Y-%m-%d')


# ============================================================
# F1-T2：全平 + Volume=0 → drop（停牌日 Yahoo 有時回 0 非 null）
# ============================================================
def test_flat_bar_with_zero_volume_dropped():
    df = _df([
        ('2026-07-09', 100.0, 102.0, 99.0, 101.0, 5000),
        ('2026-07-10', 101.0, 101.0, 101.0, 101.0, 0),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 1
    assert out.index[0].strftime('%Y-%m-%d') == '2026-07-09'


# ============================================================
# F1-T3：真一字漲停 — 全平但量 > 0 → 保留
# ============================================================
def test_locked_limit_up_bar_kept():
    """晶心科 7/13 一字漲停：O=H=L=C=210.5 但量 615,800 → 真實交易，保留"""
    df = _df([
        ('2026-07-09', 193.0, 195.0, 191.0, 191.5, 144100),
        ('2026-07-13', 210.5, 210.5, 210.5, 210.5, 615800),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 2


# ============================================================
# F1-T4：非全平但量缺 → 保留（有真實高低波動，量欄位缺漏另處理）
# ============================================================
def test_non_flat_bar_with_nan_volume_kept():
    df = _df([
        ('2026-07-09', 100.0, 105.0, 98.0, 103.0, np.nan),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 1


# ============================================================
# F1-T5：正常資料零損傷
# ============================================================
def test_normal_bars_untouched():
    df = _df([
        ('2026-07-08', 192.5, 194.5, 189.5, 192.5, 207100),
        ('2026-07-09', 193.0, 195.0, 191.0, 191.5, 144100),
        ('2026-07-13', 210.5, 210.5, 210.5, 210.5, 615800),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 3
    pd.testing.assert_frame_equal(out, df)


# ============================================================
# F1-T6：空 DataFrame 不 crash
# ============================================================
def test_empty_df_safe():
    df = _df([])
    out = _drop_degenerate_bars(df)
    assert len(out) == 0


# ============================================================
# F1-T7：假棒剔除後 5 日均量不再被稀釋（下游效果驗證）
# ============================================================
def test_vol_avg_not_diluted_after_drop():
    """含假棒時 tail(5).mean 用 NaN skip 仍會少一天樣本；drop 後均量以真實交易日計"""
    df = _df([
        ('2026-07-07', 203.5, 203.5, 191.5, 192.0, 355100),
        ('2026-07-08', 192.5, 194.5, 189.5, 192.5, 207100),
        ('2026-07-09', 193.0, 195.0, 191.0, 191.5, 144100),
        ('2026-07-10', 191.5, 191.5, 191.5, 191.5, np.nan),
        ('2026-07-13', 210.5, 210.5, 210.5, 210.5, 615800),
    ])
    out = _drop_degenerate_bars(df)
    assert len(out) == 4
    # 剔除後 tail(5) 是 4 個真實交易日，均量 = 真實日均
    expected = (355100 + 207100 + 144100 + 615800) / 4
    assert abs(float(out['Volume'].tail(5).mean()) - expected) < 1e-6
