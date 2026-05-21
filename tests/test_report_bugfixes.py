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


# ---------- Bug 4: 空停 fallback ----------
from modules.ai_analyzer_v2 import _resolve_swing_anchors


def _flat_bars(n=30, h=100, l=95):
    """全平盤 K 棒：無有效局部峰谷，calc_swing_levels 會回 None。"""
    return [{'date': f'2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}',
             'open': (h + l) / 2, 'high': h, 'low': l,
             'close': (h + l) / 2, 'volume_zhang': 1000} for i in range(n)]


def test_short_stop_loss_fallback_when_no_swing():
    """short：日K 充足(≥20)但算不出 swing → 空停 fallback 近20日高×1.03。"""
    r = _resolve_swing_anchors({'daily_bars': _flat_bars(30)}, 97.0, 'short')
    assert r['stop_loss_anchor'] is not None, 'short 充足資料應 fallback 出空停'
    assert r['stop_loss_anchor'] == 103.0  # max high 100 × 1.03


def test_short_no_fallback_when_data_insufficient():
    """short：日K < 20 根（真不足）→ 仍全 None，不亂補。"""
    r = _resolve_swing_anchors({'daily_bars': _flat_bars(5)}, 97.0, 'short')
    assert all(v is None for v in r.values())


# ---------- Bug 6a: 多根型態跨度標註 ----------
from modules.candlestick import label_bars


def test_multi_candle_pattern_has_span_suffix():
    """3 根組合型態（三白兵）標註應帶「（3根組合）」後綴。"""
    # 4 根 filler + 三白兵（連三陽、開盤收斂於前根實體內、無上影）
    bars = [
        {'date': '2026-05-01', 'open': 50,  'high': 51,  'low': 49,  'close': 50,  'volume_zhang': 100},
        {'date': '2026-05-02', 'open': 50,  'high': 51,  'low': 49,  'close': 50,  'volume_zhang': 100},
        {'date': '2026-05-03', 'open': 50,  'high': 51,  'low': 49,  'close': 50,  'volume_zhang': 100},
        {'date': '2026-05-04', 'open': 50,  'high': 51,  'low': 49,  'close': 50,  'volume_zhang': 100},
        {'date': '2026-05-05', 'open': 100, 'high': 105, 'low': 99,  'close': 105, 'volume_zhang': 200},
        {'date': '2026-05-06', 'open': 103, 'high': 108, 'low': 102, 'close': 108, 'volume_zhang': 200},
        {'date': '2026-05-07', 'open': 106, 'high': 111, 'low': 105, 'close': 111, 'volume_zhang': 200},
    ]
    labels = label_bars(bars)
    assert labels.get('2026-05-07', '') == '三白兵（3根組合）', \
        f"末根三白兵應帶跨度後綴，實際 labels={labels}"


def test_single_candle_pattern_no_suffix():
    """單根型態（如十字星）不加後綴。"""
    bars = [
        {'date': f'2026-05-{i:02d}', 'open': 50, 'high': 52, 'low': 48,
         'close': 50, 'volume_zhang': 100} for i in range(1, 8)
    ]
    labels = label_bars(bars)
    for name in labels.values():
        assert '根組合）' not in name


# ---------- Bug 1: 殘破未閉合標籤清理 ----------
from modules.ai_analyzer_v2 import _clean_html_output


def test_clean_strips_trailing_broken_tag():
    """輸出被截斷在殘破 <span ... → 清掉，不外洩到頁面。"""
    raw = '<p>分析內容正常</p>\n<span class="key-point'
    out = _clean_html_output(raw)
    assert '<span' not in out
    assert '分析內容正常' in out


def test_clean_keeps_complete_tags():
    """完整標籤不受影響。"""
    raw = '<p>正常</p><span class="key-point">結論</span>'
    out = _clean_html_output(raw)
    assert '<span class="key-point">結論</span>' in out
