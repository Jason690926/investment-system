"""Bug-A 修法測試（plan §三十五, 2026-05-28）。

§三十四 Bug-1 修法 catch「加碼」字眼。但晶心科 5/28 cost=-38% 而 base pill = 「🟢 續抱」
（HOLD path entry_zone=None + structure_flag 未轉弱 → default 續抱），不含「加碼」
字眼故未被覆寫 → 家人讀者看「續抱」放心，第六節持倉停損被忽略。

Bug-A 修法：擴大 catch 範圍，深虧時把「續抱」也改「🟡 觀望持有」。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import adjust_pill_for_deep_loss


# ============ Bug-A 新增 case：深虧 + 續抱 ============

def test_deep_loss_overrides_xubao():
    """深虧 -38% + base pill 🟢 續抱 → 改 🟡 觀望持有。"""
    assert adjust_pill_for_deep_loss('🟢 續抱', pl_pct=-38.0) == '🟡 觀望持有'


def test_deep_loss_overrides_xubao_at_threshold():
    """深虧 -20% 邊界 + 續抱 → 改 🟡 觀望持有。"""
    assert adjust_pill_for_deep_loss('🟢 續抱', pl_pct=-20.0) == '🟡 觀望持有'


def test_xubao_not_overridden_when_shallow_loss():
    """淺虧 -15% + 續抱 → 不變（沿用既有邏輯）。"""
    assert adjust_pill_for_deep_loss('🟢 續抱', pl_pct=-15.0) == '🟢 續抱'


# ============ 既有「加碼」case 不退化 ============

def test_jiama_still_overridden():
    """深虧 + 加碼 → 仍改觀望持有（既有 Bug-1 行為）。"""
    assert adjust_pill_for_deep_loss('🟢 加碼', pl_pct=-34.0) == '🟡 觀望持有'


def test_jiama_qiang_still_overridden():
    """深虧 + 加碼 💪 → 仍改觀望持有。"""
    assert adjust_pill_for_deep_loss('🟢 加碼 💪', pl_pct=-30.0) == '🟡 觀望持有'


# ============ 其他 pill 不誤殺 ============

def test_chu_chang_not_changed():
    """深虧 + 🔴 出場 → 不變（已經是出場語義）。"""
    assert adjust_pill_for_deep_loss('🔴 出場', pl_pct=-40.0) == '🔴 出場'


def test_jianma_not_changed():
    """深虧 + 🟠 減碼 → 不變（已是減碼語義，比觀望持有更明確）。"""
    assert adjust_pill_for_deep_loss('🟠 減碼', pl_pct=-40.0) == '🟠 減碼'


def test_pl_none_no_change():
    """pl_pct=None → 不變動（觀察股 / 無 cost）。"""
    assert adjust_pill_for_deep_loss('🟢 續抱', pl_pct=None) == '🟢 續抱'


def test_profit_no_change():
    """賺錢場景（pl > 0）→ 不變動。"""
    assert adjust_pill_for_deep_loss('🟢 續抱', pl_pct=+15.0) == '🟢 續抱'
    assert adjust_pill_for_deep_loss('🟢 加碼', pl_pct=+30.0) == '🟢 加碼'
