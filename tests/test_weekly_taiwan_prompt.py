"""C3 / Bug W2 + W3 + I2（2026-05-24）— 週報 prompt 量能/區間/max_tokens。

根因：
- W2 注入 vol/vol5 是日量/日均量，label 卻叫「本週末量」
- W3 prompt 沒分離「收盤區間」vs「高低區間」AI 自由命名
- I2 get_industry_indicator_stocks max_tokens=800 過小，句尾截斷

修法：
- analyze_weekly_taiwan_v2 從 weekly_bars 算「本週週量 + 近 5 週均量」，新欄位 relabel
- 加注入「近 3 週收盤區間」「近 3 週高低區間」+ 鐵律不可混用
- get_industry_indicator_stocks max_tokens 800 → 1500

spec: docs/superpowers/specs/2026-05-24-weekly-report-bugs-design.md
plan §二十九 / C3
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modules.ai_analyzer_v2 as mod


def _mock_enriched():
    """構造 twii_enriched mock：weekly_bars 5 根含真實數字方便驗證"""
    return {
        'price': 42268.0,
        'ma5': 40944,
        'ma20': 40758,
        'ma60': 36516,
        'macd': {'macd': 1211, 'signal': 1407, 'histogram': -196},
        # 日量欄位（修法後不該用在週報）
        'volume_zhang': 5124.4,
        'volume_5d_avg_zhang': 5124.4,
        # weekly_bars 5 根 — 第 [-1] 為本週進行中
        'weekly_bars': [
            {'date': '2026-04-20', 'open': 38000, 'high': 38900, 'low': 37500, 'close': 38500, 'volume_zhang': 30000},
            {'date': '2026-04-27', 'open': 38500, 'high': 40000, 'low': 38200, 'close': 39900, 'volume_zhang': 35000},
            {'date': '2026-05-04', 'open': 40000, 'high': 41700, 'low': 39900, 'close': 41603, 'volume_zhang': 36000},
            {'date': '2026-05-11', 'open': 41603, 'high': 42408, 'low': 41100, 'close': 41172, 'volume_zhang': 39350},
            {'date': '2026-05-18', 'open': 41095, 'high': 41606, 'low': 39967, 'close': 41368, 'volume_zhang': 25622},
        ],
        'monthly_bars': [
            {'date': '2026-04-01', 'open': 31892, 'high': 39000, 'low': 31800, 'close': 38926, 'volume_zhang': 500000},
            {'date': '2026-05-01', 'open': 38926, 'high': 42408, 'low': 38900, 'close': 41368, 'volume_zhang': 300000},
        ],
    }


def _capture_prompt(monkeypatch):
    """patch _generate 攔截 prompt 字串並回傳 (captured_prompts list, max_tokens list)。"""
    captured = {'prompts': [], 'max_tokens': []}
    def fake(prompt, max_tokens=1024):
        captured['prompts'].append(prompt)
        captured['max_tokens'].append(max_tokens)
        return '<div>fake</div>'
    monkeypatch.setattr(mod, '_generate', fake)
    return captured


# ============================================================
# C3-T1：週報 prompt 含「本週週量」「近 5 週均量」（取代「本週末量」）
# ============================================================
def test_weekly_prompt_uses_week_level_volume_labels(monkeypatch):
    cap = _capture_prompt(monkeypatch)
    mod.analyze_weekly_taiwan_v2(_mock_enriched(), '全球摘要', '2026/05/18~05/22')
    p = cap['prompts'][0]

    assert '本週週量' in p, 'label 須改為「本週週量」'
    assert '近 5 週均量' in p, 'label 須含「近 5 週均量」'
    assert '本週末量' not in p, '舊「本週末量」需移除'


# ============================================================
# C3-T2：注入值正確 — 本週週量 = weekly_bars[-1].volume_zhang
# ============================================================
def test_weekly_prompt_injects_correct_week_volume(monkeypatch):
    cap = _capture_prompt(monkeypatch)
    mod.analyze_weekly_taiwan_v2(_mock_enriched(), '全球摘要', '2026/05/18~05/22')
    p = cap['prompts'][0]

    # 本週量 = weekly_bars[-1].volume_zhang = 25622
    assert '25622' in p, '本週週量 25622 須注入 prompt'
    # 近 5 週均量 = (30000+35000+36000+39350+25622)/5 = 33194.4
    # 接受 33194 或 33194.4（round 視實作）
    assert ('33194' in p or '33,194' in p), '近 5 週均量 約 33194 須注入'


# ============================================================
# C3-T3：prompt 含「近 3 週收盤區間」「近 3 週高低區間」雙欄分明
# ============================================================
def test_weekly_prompt_has_close_range_and_hl_range(monkeypatch):
    cap = _capture_prompt(monkeypatch)
    mod.analyze_weekly_taiwan_v2(_mock_enriched(), '全球摘要', '2026/05/18~05/22')
    p = cap['prompts'][0]

    assert '近 3 週收盤區間' in p, 'prompt 須含「近 3 週收盤區間」label'
    assert '近 3 週高低區間' in p, 'prompt 須含「近 3 週高低區間」label'
    # 收盤區間 = min/max of close in last 3 weeks = 41172~41603
    # 高低區間 = min low / max high in last 3 weeks = 39900~42408
    assert '41172' in p and '41603' in p, '收盤區間實值須注入'
    assert '39900' in p and '42408' in p, '高低區間實值須注入'


# ============================================================
# C3-T4：get_industry_indicator_stocks max_tokens 提升到 1500
# ============================================================
def test_industry_indicator_stocks_max_tokens_raised(monkeypatch):
    cap = _capture_prompt(monkeypatch)
    mod.get_industry_indicator_stocks([{'title': '新聞 A'}], '全球摘要')
    assert cap['max_tokens'][0] >= 1500, \
        f'max_tokens 應 ≥ 1500（修法目標），實際 {cap["max_tokens"][0]}'
