"""
§四十三 R2（2026-07-17）— 距峰值回落改用全月K盤中高點峰值

7/16 報告實證：峰值用「已收盤月的收盤 max」→ 強漲股現價高於峰值出現
合晶 -35% 負回落；顯示 `+25.1%` 正負號語意混亂（+ 讀起來像漲）。
修法：peak = 全部月K（含進行中）的 high max → 回落恆 ≥ 0；顯示去 + 號。
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.data_enricher import compute_monthly_structure


def _mbar(o, h, l, c):
    return {'open': o, 'high': h, 'low': l, 'close': c, 'volume_zhang': 1000}


def _bars_rally():
    """4 根已收盤（close 峰 100）+ 進行中月衝到高 160：合晶 7/16 場景。"""
    return [
        _mbar(80, 95, 75, 90),
        _mbar(90, 100, 85, 95),
        _mbar(95, 105, 90, 100),   # 已收盤 close 峰 = 100，盤中高 105
        _mbar(100, 110, 95, 102),
        _mbar(102, 160, 100, 150),  # 進行中：衝 160，現價 150
    ]


def test_drawdown_never_negative_on_rally():
    """強漲股現價 150 > 已收盤 close 峰 100 → 回落不得為負（舊法 -50%）。"""
    ms = compute_monthly_structure(_bars_rally(), [], 150.0, ma60=None)
    dd = ms['drawdown_from_peak']
    assert dd is not None
    assert dd >= 0, f'回落應恆 ≥ 0，實際 {dd}'


def test_drawdown_uses_intraday_high_peak():
    """peak 應含進行中月盤中高 160：現價 150 → 回落 = (160-150)/160 = 6.2%。"""
    ms = compute_monthly_structure(_bars_rally(), [], 150.0, ma60=None)
    assert ms['drawdown_from_peak'] == 6.2


def test_drawdown_normal_decline_unchanged_semantics():
    """一般下跌股：峰值 250（盤中高）、現價 190 → 24.0% 正值回落。"""
    bars = [
        _mbar(200, 250, 195, 240),  # 盤中高峰 250
        _mbar(240, 245, 220, 230),
        _mbar(230, 235, 210, 215),
        _mbar(215, 220, 200, 205),
        _mbar(205, 210, 185, 190),  # 進行中
    ]
    ms = compute_monthly_structure(bars, [], 190.0, ma60=None)
    assert ms['drawdown_from_peak'] == 24.0
