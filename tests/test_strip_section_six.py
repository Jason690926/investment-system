"""C5 / Bug S3（2026-05-24）— 觀察股第六節雙層防護。

5/22 報表 12 檔觀察股有 3 檔（技嘉/南亞科/瑞軒）違規輸出第六節（25% 失效率）：
- 技嘉/南亞科：完整觀望持有 + 部位處理觸發價
- 瑞軒：「（本次 dynamic_block 未出現【持倉提示】，本節跳過）」洩漏內部欄位名

修法：雙層防護
1. prompt 改鐵律「禁止輸出『六、』標題」（強過「整節跳過」）
2. 新 helper _strip_section_six(html, is_holding) post-process：
   - is_holding=True → 原樣回傳
   - is_holding=False → regex 砍 ### 六、後整段（safety net）

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C5
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.ai_analyzer_v2 import _strip_section_six


# ============================================================
# C5-T1：is_holding=True 保留第六節整段
# ============================================================
def test_holding_preserves_section_six():
    html = '''### 五、操作框架
some content here.

### 六、持倉部位建議
<ul>
  <li>▶ 整體判斷：續抱</li>
  <li>▶ 部位處理觸發價：跌破 100 元減碼</li>
  <li>▶ 持倉停損：100 元 — 跌破請執行</li>
</ul>

⚠️ 以上為模擬分析。'''

    out = _strip_section_six(html, is_holding=True)
    assert '### 六、持倉部位建議' in out
    assert '▶ 整體判斷：續抱' in out
    assert '▶ 持倉停損：100 元' in out


# ============================================================
# C5-T2：is_holding=False 完整觀望持有洩漏 → 砍除（技嘉/南亞科 case）
# ============================================================
def test_watch_strips_full_holding_advice_leak():
    """5/22 技嘉/南亞科 case — AI 給完整觀望持有 + 部位處理"""
    html = '''### 五、操作框架
some content here.

### 六、持倉部位建議
<ul>
  <li>▶ 整體判斷：**觀望持有** — 結構未轉弱，無需主動出場</li>
  <li>▶ 部位處理觸發價：跌破 270.50 元減碼</li>
  <li>▶ 持倉停損：270.50 元 — 跌破請執行</li>
</ul>

⚠️ 以上為模擬分析。'''

    out = _strip_section_six(html, is_holding=False)
    assert '### 六、' not in out
    assert '持倉部位建議' not in out
    assert '觀望持有' not in out
    assert '部位處理觸發價' not in out
    assert '持倉停損' not in out
    # 前後文保留
    assert '### 五、操作框架' in out
    assert 'some content here' in out
    assert '以上為模擬分析' in out


# ============================================================
# C5-T3：is_holding=False 瑞軒 literal 洩漏 → 砍除
# ============================================================
def test_watch_strips_dynamic_block_leak():
    """瑞軒 case — AI 寫出內部欄位名"""
    html = '''### 五、操作框架
some content.

### 六、持倉部位建議
（本次 dynamic_block 未出現【持倉提示】，本節跳過）

重要提醒：以上為模擬分析，不構成實際投資建議。'''

    out = _strip_section_six(html, is_holding=False)
    assert 'dynamic_block' not in out
    assert '【持倉提示】' not in out
    assert '本節跳過' not in out
    assert '### 五、操作框架' in out
    assert '重要提醒：以上為模擬分析' in out  # disclaimer 保留


# ============================================================
# C5-T4：第六節是最後一節（無第七節）也要砍對 + AI 完全沒輸出第六節時 no-op
# ============================================================
def test_section_six_last_section_clean_strip():
    """無第七、八節時，第六節到結尾整段須砍乾淨"""
    html = '''### 五、操作框架
content five.

### 六、持倉部位建議
content six.
more content.'''

    out = _strip_section_six(html, is_holding=False)
    assert '### 六、' not in out
    assert 'content six' not in out
    assert '### 五、操作框架' in out
    assert 'content five' in out


def test_no_section_six_returns_unchanged():
    """is_holding=False 但 AI 本來就沒輸出第六節 → 原樣回傳"""
    html = '''### 五、操作框架
content here.

end.'''

    out = _strip_section_six(html, is_holding=False)
    assert out == html
