"""5/20 報表 6 bug 修法測試（2026-05-21）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd
import numpy as np
from modules.data_enricher import _patch_missing_close


def test_patch_fills_close_from_high_low():
    """Close=NaN 但 High/Low 在 → 用 (High+Low)/2 補。"""
    df = pd.DataFrame({
        'Open':  [10.0, 11.0, 12.0],
        'High':  [12.0, 13.0, 14.0],
        'Low':   [9.0,  10.0, 11.0],
        'Close': [11.0, np.nan, 13.0],
        'Volume':[100,  200,   300],
    })
    out = _patch_missing_close(df)
    assert len(out) == 3, '不該掉列'
    assert out['Close'].iloc[1] == 11.5  # (13+10)/2


def test_patch_still_drops_fully_empty_row():
    """High/Low 也缺 → 該列仍 drop（無法補）。"""
    df = pd.DataFrame({
        'Open':  [10.0, np.nan],
        'High':  [12.0, np.nan],
        'Low':   [9.0,  np.nan],
        'Close': [11.0, np.nan],
        'Volume':[100,  np.nan],
    })
    out = _patch_missing_close(df)
    assert len(out) == 1
