"""C4 / Bug S5（2026-05-24）— 結構閘 gate_hint「結構已轉弱」加禁標多方相位。

根因：撼訊報表「結構旗標：結構已轉弱」但 phase 標「再積累」，UX 矛盾。
規則表只禁「結構未轉弱」標派發/再派發/下跌，反向沒禁。

修法：gate_hint「結構已轉弱」加「相位限定 派發/再派發/下跌/不明，
禁標 積累/上漲/再積累」（與「結構未轉弱」對稱）。

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C4
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modules.ai_analyzer_v2 as mod


def _make_enriched(*, flag: str):
    """構造 enriched_data 讓 compute_monthly_structure 回指定 flag。

    走 monkeypatch — 直接 patch compute_monthly_structure 回傳 dict。
    """
    return {
        'monthly_bars': [{'date': '2026-04-01'}] * 3,  # 任意，會被 patch
        'weekly_bars': [],
        'ma60': 60.0,
    }


def _patch_ms(monkeypatch, flag):
    monkeypatch.setattr(mod, 'compute_monthly_structure', lambda *a, **k: {
        'structure_flag': flag,
        'monthly_structure': '橫',
        'consecutive_bear_months': 1,
        'drawdown_from_peak': -10.0,
        'price_vs_ma60': '在MA60上',
        'weekly_momentum': '中性',
        'weekly_hold_support': True,
    })


# ============================================================
# C4-T1：結構已轉弱 → 禁標多方相位（新增鐵律）
# F8 §三十二 Bug-3：加 DIRECTION 鐵律 + 多頭字眼禁令
# ============================================================
def test_structure_weakened_blocks_long_phases(monkeypatch):
    _patch_ms(monkeypatch, '結構已轉弱')
    out = mod._structure_block(_make_enriched(flag='結構已轉弱'), 70.0)

    assert '結構已轉弱' in out
    assert '禁標 積累/上漲/再積累' in out, '結構已轉弱須禁標多方相位（與未轉弱規則對稱）'
    # F8 §三十二 Bug-3：撼訊 5/25 報表案例（pill 🔴 / AI 文「方向一致順勢做多」）
    assert '派發/再派發/下跌/不明' in out, '結構已轉弱須限定 WYCKOFF_PHASE 為空方/不明'
    assert 'DIRECTION 禁標 long' in out, 'F8 Bug-3 安全網 prompt 鐵律：禁標 DIRECTION=long'
    assert '方向一致' in out and '順勢做多' in out, \
        'F8 Bug-3：須列出禁多頭字眼清單避免 AI 違規'
    assert 'post-process' in out, 'F8 Bug-3：須告知違反鐵律會被 post-process 覆寫'


# ============================================================
# C4-T2：結構未轉弱 規則不變（既有規則保留）
# ============================================================
def test_structure_not_weakened_keeps_existing_rule(monkeypatch):
    _patch_ms(monkeypatch, '結構未轉弱')
    out = mod._structure_block(_make_enriched(flag='結構未轉弱'), 70.0)

    assert '結構未轉弱' in out
    assert '禁止標派發/再派發/下跌' in out, '結構未轉弱既有規則不可變動'
    # 但不該誤套到「禁標 積累/上漲/再積累」
    assert '禁標 積累/上漲/再積累' not in out, \
        '結構未轉弱 hint 不可含禁標多方相位（屬結構已轉弱的反向規則）'
