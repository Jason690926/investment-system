# 報表 6 Bug 修法 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修 5/20 報表審視出的 6 個 bug（HTML 標籤外洩、第四節截斷、OHLC 欄序、空停缺漏、日K 根數、型態誤標）。

**Architecture:** 6 個 bug 分 6 個 Task。Bug 1+2 同根因（token 截斷）；Bug 3+6b 同根因（AI 手抄 K 表）→ 改由程式產表，分 helper（Task 5）與 wiring（Task 6）兩步。純加性 + prompt 改寫，無 DB/migration。

**Tech Stack:** Python 3.12、pytest、無新依賴。

**根因依據：** 兩組調查 agent 報告（見對話），逐 bug 根因與選定修法已與使用者確認。

---

## 檔案結構

| 檔案 | 變更 |
|------|------|
| `modules/data_enricher.py` | `_yahoo_ohlcv` 補 null Close（Bug5）|
| `modules/candlestick.py` | `label_bars` 多根型態跨度標註（Bug6a）|
| `modules/ai_analyzer_v2.py` | `_resolve_swing_anchors` 空停 fallback（Bug4）；`analyze_market_only` max_tokens + `_clean_html_output` 殘破標籤清理（Bug1+2）；新增 `_compute_bar_feats`/`_render_ktables_html`/`_inject_ktables` + 改 `analyze_market_only` prompt（Bug3+6b）|
| `tests/` | 新增 `test_report_bugfixes.py`；既有 `test_swing_anchors.py`/`test_fmt_bars_dedup.py` 作回歸護欄 |

---

## Task 1: Bug 5 — `_yahoo_ohlcv` 補 null 收盤價

**根因：** `_yahoo_ohlcv` 對 Yahoo 漏回 `Close` 的列整列 `dropna`，導致該日 K 棒消失（5/20 報表多支股日K 只 4 根）。

**Files:**
- Modify: `modules/data_enricher.py:30`
- Test: `tests/test_report_bugfixes.py`（新建）

- [ ] **Step 1: Write the failing test**

新建 `tests/test_report_bugfixes.py`：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_bugfixes.py -v`
Expected: FAIL — `ImportError: cannot import name '_patch_missing_close'`

- [ ] **Step 3: Write minimal implementation**

在 `modules/data_enricher.py` 的 `_yahoo_ohlcv` 函式**之前**新增：

```python
def _patch_missing_close(df):
    """Bug5：Yahoo 偶爾對某日漏回 Close，整列 dropna 會少一根 K 棒。
    若 Close 缺但 High/Low 在，用當日 (High+Low)/2 補；High/Low 也缺才 drop。"""
    mask = df['Close'].isna() & df['High'].notna() & df['Low'].notna()
    df.loc[mask, 'Close'] = (df.loc[mask, 'High'] + df.loc[mask, 'Low']) / 2
    return df.dropna(subset=['Close'])
```

把 `_yahoo_ohlcv` 的 `return df.dropna(subset=['Close'])`（line 30）改為：

```python
        return _patch_missing_close(df)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_bugfixes.py -v`
Expected: PASS（2 個）

- [ ] **Step 5: Commit**

```bash
git add modules/data_enricher.py tests/test_report_bugfixes.py
git commit -m "fix(report): Bug5 — _yahoo_ohlcv 補 null 收盤價，不再掉 K 棒

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Bug 4 — `_resolve_swing_anchors` 空停 fallback

**根因：** `calc_swing_levels()` 對某些 short 股算不出有效峰谷 → 回 None → `stop_loss_anchor` = None → pill 不顯示空停。修法：日K 資料充足（≥20 根）但 swing 失敗時，用近 20 日最高價 × 1.03 補空停。

**Files:**
- Modify: `modules/ai_analyzer_v2.py:225-260`（`_resolve_swing_anchors`）
- Test: `tests/test_report_bugfixes.py`（追加）；`tests/test_swing_anchors.py`（回歸護欄）

- [ ] **Step 1: Write the failing test**

在 `tests/test_report_bugfixes.py` 末尾追加：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_bugfixes.py -k stop_loss -v`
Expected: FAIL — `test_short_stop_loss_fallback_when_no_swing` 失敗（`stop_loss_anchor` is None）

- [ ] **Step 3: Write minimal implementation**

把 `_resolve_swing_anchors`（`modules/ai_analyzer_v2.py:238-260`）的 `from ... import` 之後**整段**改為：

```python
    from modules.candlestick import calc_swing_levels
    dk = enriched_data.get('daily_bars', [])
    sl = calc_swing_levels(dk, direction, price_f) if direction in ('long', 'short') else None
    out = {
        'support_anchor':    sl.get('range_low')  if sl else None,
        'resistance_anchor': sl.get('range_high') if sl else None,
        'target_anchor':     sl.get('target')     if sl else None,
        'stop_loss_anchor':  None,
    }
    if direction == 'short':
        rh = sl.get('range_high') if sl else None
        if rh:
            # 空停 = 前高 × 1.03（3% buffer above 失效點）
            out['stop_loss_anchor'] = round(float(rh) * 1.03, 1 if rh < 100 else 0)
        elif len(dk) >= 20:
            # Bug4 fallback：swing 算不出但日K 充足 → 用近 20 日最高 × 1.03 補空停
            highs = [float(b['high']) for b in dk[-20:] if b.get('high') is not None]
            if highs:
                rhf = max(highs)
                out['stop_loss_anchor'] = round(rhf * 1.03, 1 if rhf < 100 else 0)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report_bugfixes.py tests/test_swing_anchors.py -v`
Expected: PASS — 新測試 + 既有 `test_swing_anchors.py` 全綠（`test_insufficient_bars_all_none` 因 5 根 <20 仍全 None，不受影響）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_report_bugfixes.py
git commit -m "fix(report): Bug4 — short 股 swing 失敗時用近20日高×1.03 補空停

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Bug 6a — `label_bars` 多根型態跨度標註

**根因：** 三根組合型態（早晨之星等）的名稱被 `label_bars` 只貼到最後一根 `bars[i]`，看起來像「單根被標成三根型態」。修法：多根型態（`span>=3`）的顯示名稱加 `（N根組合）` 後綴，讀者一眼知道是跨根型態。

> 註：採「完成根 + 跨度後綴」而非「移到起始根」——組合型態於末根確認是 TA 慣例，且移列會產生 result key 覆寫的邊界情況。效果一致：杜絕「單根=組合型態」誤讀。

**Files:**
- Modify: `modules/candlestick.py:622-624`（`label_bars` 內）
- Test: `tests/test_report_bugfixes.py`（追加）

- [ ] **Step 1: Write the failing test**

在 `tests/test_report_bugfixes.py` 末尾追加：

```python
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
```

> ⚠️ 執行注意：若 Step 2 跑出來末根偵測到的不是「三白兵」（detect_patterns 選了別的 strong 型態），停下回報，不要硬改 fixture。Step 4 若 `test_candlestick.py` 既有測試因「多根型態名多了後綴」而失敗，也停下回報——那些既有測試可能需同步更新斷言。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_bugfixes.py -k candle -v`
Expected: FAIL — `test_multi_candle_pattern_has_span_suffix` 失敗（型態名無後綴）

- [ ] **Step 3: Write minimal implementation**

把 `modules/candlestick.py` 的 `label_bars` 內這段（line 622-624）：

```python
            if chosen_name:
                result[date] = chosen_name
                label_history.append(chosen_name)
```

改為：

```python
            if chosen_name:
                span = _MULTI_CANDLE.get(chosen_name, 1)
                if span >= 3:
                    # Bug6a：多根組合型態加跨度後綴，避免被誤讀為單根型態
                    result[date] = f"{chosen_name}（{span}根組合）"
                else:
                    result[date] = chosen_name
                label_history.append(chosen_name)  # 去重比對仍用原名
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report_bugfixes.py tests/test_candlestick.py -v`
Expected: PASS — 新測試 + 既有 `test_candlestick.py` 全綠

- [ ] **Step 5: Commit**

```bash
git add modules/candlestick.py tests/test_report_bugfixes.py
git commit -m "fix(report): Bug6a — label_bars 多根型態加（N根組合）跨度後綴

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Bug 1+2 — max_tokens 不足 + 殘破標籤清理

**根因：** `analyze_market_only` 用 `max_tokens=2000`，四節分析撐爆 → 輸出截斷在 `<span class="key-point`（HTML 外洩，Bug1）、第四節整段被切（Bug2）。`_clean_html_output` 只清殘破 style/script，沒清殘破的一般標籤。

**Files:**
- Modify: `modules/ai_analyzer_v2.py:1092`（max_tokens）、`:169-173`（`_clean_html_output` 結尾）
- Test: `tests/test_report_bugfixes.py`（追加）

- [ ] **Step 1: Write the failing test**

在 `tests/test_report_bugfixes.py` 末尾追加：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_bugfixes.py -k clean -v`
Expected: FAIL — `test_clean_strips_trailing_broken_tag` 失敗（殘破 `<span` 仍在）

- [ ] **Step 3: Write minimal implementation**

(a) `_clean_html_output`：把結尾（`modules/ai_analyzer_v2.py:171-173`）

```python
    # ── 步驟4：剝除所有 inline style 屬性 ────────────────────
    html = re.sub(r'\s+style\s*=\s*(?:"[^"]*"|\'[^\']*\')', '', html, flags=re.IGNORECASE)
    return html
```

改為：

```python
    # ── 步驟4：剝除所有 inline style 屬性 ────────────────────
    html = re.sub(r'\s+style\s*=\s*(?:"[^"]*"|\'[^\']*\')', '', html, flags=re.IGNORECASE)
    # ── 步驟5：砍字串尾端殘破未閉合標籤（Bug1：max_tokens 截斷在 <span ...）──
    html = re.sub(r'<[a-zA-Z][^>]*$', '', html).rstrip()
    return html
```

(b) max_tokens：把 `analyze_market_only` 的 `_generate(...)` 呼叫（`modules/ai_analyzer_v2.py:1092`）

```python
        max_tokens=2000,
```

改為：

```python
        max_tokens=3000,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_bugfixes.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_report_bugfixes.py
git commit -m "fix(report): Bug1+2 — analyze_market_only max_tokens 3000 + 清殘破標籤

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Bug 3+6b — K 表 helper（程式產表）

**根因：** `analyze_market_only` 的第二節 K 線表是 AI 把 `_fmt_bars` 文字手抄成 HTML `<table>`，AI 抄錯欄位（高<低，Bug3）、把特徵填進型態欄（Bug6b）。本 Task 先建程式產表的 helper，Task 6 再 wiring。

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（`_fmt_bars` 重構 + 新增 3 個 helper）
- Test: `tests/test_report_bugfixes.py`（追加）；`tests/test_fmt_bars_dedup.py`（回歸護欄）

- [ ] **Step 1: Write the failing test**

在 `tests/test_report_bugfixes.py` 末尾追加：

```python
# ---------- Bug 3+6b: 程式產 K 線表 ----------
from modules.ai_analyzer_v2 import (
    _compute_bar_feats, _render_ktables_html, _inject_ktables,
)


def _kbars(n, base_date='2026-03-01'):
    from datetime import date, timedelta
    d = date.fromisoformat(base_date)
    out = []
    for i in range(n):
        out.append({'date': (d + timedelta(days=i)).isoformat(),
                    'open': 100 + i, 'high': 105 + i, 'low': 95 + i,
                    'close': 102 + i, 'volume_zhang': 1000 + i})
    return out


def test_compute_bar_feats_returns_per_date():
    feats = _compute_bar_feats(_kbars(25))
    assert len(feats) == 25
    for v in feats.values():
        assert any(k in v for k in ('放量', '縮量', '均量'))


def test_render_ktables_has_three_tables_correct_order():
    enriched = {'monthly_bars': _kbars(12), 'weekly_bars': _kbars(26),
                'daily_bars': _kbars(60)}
    html = _render_ktables_html(enriched)
    assert html.count('<table') == 3
    # 表頭欄序固定 開→高→低→收
    assert '<th>開</th><th>高</th><th>低</th><th>收</th>' in html
    # 每列 OHLC：高 >= 低（程式產表不可能錯位）
    import re as _re
    for o, h, l, c in _re.findall(
            r'<td>[\d-]+</td><td>[^<]*</td><td>([\d.]+)</td><td>([\d.]+)</td>'
            r'<td>([\d.]+)</td><td>([\d.]+)</td>', html):
        assert float(h) >= float(l)


def test_inject_ktables_replaces_placeholder():
    enriched = {'monthly_bars': _kbars(12), 'weekly_bars': _kbars(26),
                'daily_bars': _kbars(60)}
    html = _inject_ktables('<p>前</p>[[K_TABLES]]<p>後</p>', enriched)
    assert '[[K_TABLES]]' not in html
    assert html.count('<table') == 3


def test_inject_ktables_fallback_when_no_placeholder():
    enriched = {'monthly_bars': _kbars(12), 'weekly_bars': _kbars(26),
                'daily_bars': _kbars(60)}
    html = _inject_ktables('### 二、本間宗久K線確認\n內文', enriched)
    assert html.count('<table') == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_bugfixes.py -k 'feats or ktables' -v`
Expected: FAIL — `ImportError: cannot import name '_compute_bar_feats'`

- [ ] **Step 3: Write minimal implementation**

(a) 在 `modules/ai_analyzer_v2.py` 的 `_fmt_bars` 函式**之前**新增 `_compute_bar_feats`：

```python
def _compute_bar_feats(bars: list) -> dict:
    """每根 K 棒的【特徵】字串 {date: '放量·高位·跳空高開'}。
    供 _fmt_bars 與 _render_ktables_html 共用，確保 K 表與 AI 文字一致。"""
    if not bars:
        return {}
    ref        = bars[-20:]
    vol_list   = [float(b.get('volume_zhang', 0) or 0) for b in ref]
    vol_avg    = sum(vol_list) / len(vol_list) if vol_list else 0
    range_high = max(float(b['high']) for b in ref) if ref else 0
    range_low  = min(float(b['low'])  for b in ref) if ref else 0
    feats = {}
    for i, b in enumerate(bars):
        vol = float(b.get('volume_zhang', 0) or 0)
        if vol_avg > 0:
            r = vol / vol_avg
            vol_feat = '放量' if r >= 1.5 else ('縮量' if r <= 0.7 else '均量')
        else:
            vol_feat = '均量'
        close = float(b['close'])
        if range_high > range_low:
            pos = (close - range_low) / (range_high - range_low)
            pos_feat = ('極高位' if pos >= 0.85 else '高位' if pos >= 0.65 else
                        '中段' if pos >= 0.35 else '低位' if pos >= 0.15 else '極低位')
        else:
            pos_feat = '中段'
        gap_feat = ''
        if i > 0:
            prev_close = float(bars[i - 1]['close'])
            open_ = float(b['open'])
            if open_ > prev_close * 1.01:
                gap_feat = '·跳空高開'
            elif open_ < prev_close * 0.99:
                gap_feat = '·跳空低開'
        feats[b['date']] = f"{vol_feat}·{pos_feat}{gap_feat}"
    return feats
```

(b) 重構 `_fmt_bars` 改用 `_compute_bar_feats`。把 `_fmt_bars`（`modules/ai_analyzer_v2.py:74-120`）從 `# 20-bar baselines...` 到 `return` **整段**改為：

```python
    feats = _compute_bar_feats(bars)
    rows = bars[-n:]
    lines = []
    for b in rows:
        feat = f"【特徵={feats.get(b['date'], '')}】"
        line = (f"{b['date']}  O={b['open']} H={b['high']} L={b['low']} C={b['close']}  "
                f"量={b['volume_zhang']}張  {feat}")
        if pattern_labels and b['date'] in pattern_labels:
            line += f"  ▶{pattern_labels[b['date']]}"
        lines.append(line)
    return f"【{label}（最近{len(rows)}根）】\n" + "\n".join(lines)
```

（即移除原本 inline 的 20-bar baseline 計算與 idx/abs_idx/vol/pos/gap 計算，改為呼叫 `_compute_bar_feats`。`bars = _dedup_bars_by_date(bars)` 那行保留。）

(c) 在 `_fmt_bars` 之後新增 `_render_ktables_html` 與 `_inject_ktables`：

```python
def _render_ktables_html(enriched_data: dict) -> str:
    """程式直接產生第二節 3 張 K 線表 HTML（修 Bug3/6b：不讓 AI 手抄數字）。"""
    from modules.candlestick import label_bars
    specs = [
        ('月K', enriched_data.get('monthly_bars', []), 6, 'monthly'),
        ('週K', enriched_data.get('weekly_bars',  []), 3, 'daily'),
        ('日K', enriched_data.get('daily_bars',   []), 5, 'daily'),
    ]
    out = []
    for label, bars, n, tf in specs:
        bars = _dedup_bars_by_date(bars)
        if not bars:
            out.append(f'<p class="kbar-label">{label}：資料不足</p>')
            continue
        feats = _compute_bar_feats(bars)
        labels = label_bars(bars, timeframe=tf)
        rows = bars[-n:]
        trs = []
        for b in rows:
            d = b['date']
            trs.append(
                f'<tr><td>{d}</td><td>{labels.get(d, "")}</td>'
                f'<td>{b["open"]}</td><td>{b["high"]}</td>'
                f'<td>{b["low"]}</td><td>{b["close"]}</td>'
                f'<td>{b.get("volume_zhang", "")}</td>'
                f'<td>{feats.get(d, "")}</td></tr>'
            )
        out.append(
            f'<p class="kbar-label">{label}（最近{len(rows)}根）</p>'
            f'<table class="kbar-table"><thead><tr>'
            f'<th>日期</th><th>型態</th><th>開</th><th>高</th><th>低</th>'
            f'<th>收</th><th>量(張)</th><th>特徵</th></tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table>'
        )
    return '\n'.join(out)


def _inject_ktables(html: str, enriched_data: dict) -> str:
    """把 AI 輸出的 [[K_TABLES]] 佔位替換成程式產的 K 線表。
    無佔位時 fallback：插在第二節標題後（再不行附在結尾）。"""
    tables = _render_ktables_html(enriched_data)
    if '[[K_TABLES]]' in html:
        return html.replace('[[K_TABLES]]', tables)
    m = re.search(r'(#{1,4}\s*二、[^\n]*\n|<h[1-4][^>]*>\s*二、.*?</h[1-4]>)', html)
    if m:
        return html[:m.end()] + '\n' + tables + '\n' + html[m.end():]
    return html + '\n' + tables
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report_bugfixes.py tests/test_fmt_bars_dedup.py -v`
Expected: PASS — 新測試 + 既有 `test_fmt_bars_dedup.py` 全綠（`_fmt_bars` 重構後行為不變）

- [ ] **Step 5: Commit**

```bash
git add modules/ai_analyzer_v2.py tests/test_report_bugfixes.py
git commit -m "fix(report): Bug3+6b — 新增程式產 K 表 helper + _fmt_bars 抽 _compute_bar_feats

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Bug 3+6b — 接上 `analyze_market_only`

**目標：** `analyze_market_only` 第二節改用程式產的 K 表：prompt 不再要 AI 輸出 table、改要求輸出 `[[K_TABLES]]` 佔位；分析後 `_inject_ktables` 替換。

**Files:**
- Modify: `modules/ai_analyzer_v2.py` — `analyze_market_only` 的 static_block（輸出格式鐵律 + K 表範例 + 第二節）與 result 組裝

- [ ] **Step 1: 改輸出格式鐵律第 6 條**

在 `analyze_market_only` 的 static_block，把（`modules/ai_analyzer_v2.py:982` 一帶）：

```
6. **第二節 K 線必須輸出 HTML table**（月K 6根 + 週K 3根 + 日K 5根各一張表），格式見下方範例
```

改為：

```
6. **第二節不要輸出任何 K 線 table**：在第二節 K 線表位置只輸出一行 `[[K_TABLES]]` 作佔位，系統會自動填入月K/週K/日K 三張表。嚴禁自行輸出 `<table>` 或 K 棒數字表格
```

- [ ] **Step 2: 移除 K 表範例區塊**

把這段（`modules/ai_analyzer_v2.py:985-987` 一帶）整段刪除：

```
## K 線 table 輸出範例（第二節專用）
<table><thead><tr><th>日期</th><th>型態</th><th>開</th><th>高</th><th>低</th><th>收</th><th>特徵</th></tr></thead>
<tbody><tr><td>YYYY-MM-DD</td><td>錘子</td><td>150</td><td>153</td><td>148</td><td>152</td><td>放量·高位</td></tr></tbody></table>
```

- [ ] **Step 3: 改第二節內文**

把第二節（`modules/ai_analyzer_v2.py:998-1011` 一帶）從 `### 二、本間宗久K線確認...` 到 `<span class="key-point">K線核心結論（≤15字）</span>` 之前**整段**改為：

```
### 二、本間宗久K線確認
⚠️ K 線表由系統自動產生，你只需在本節最前面輸出一行 `[[K_TABLES]]`，其後寫文字解讀（禁止自行畫表）。
K棒型態含意速查（解讀參考，須結合特徵欄量能·位置）：
錘子（下影≥實體2倍/低位看漲·高位需謹慎）、吊人（錘子型/高位看跌）、射擊之星（上影≥實體2倍/高位看跌）、
早晨之星（長黑+小K+長紅/底部反轉）、黃昏之星（長紅+小K+長黑/頂部反轉）、
多頭吞噬（陽線吞陰線）、空頭吞噬（陰線吞陽線）、十字星（高位→頂部·低位→底部·中段→觀望）
[[K_TABLES]]
- 週K型態解讀：引用上方週K表 ▶型態 + 特徵欄量能·位置，解讀含意
- 日K型態解讀：引用上方日K表 ▶型態 + 特徵欄量能·位置，解讀含意
- K線序列：依特徵欄量能·位置變化，說明多空動能增強或衰退（禁靠單根顏色判斷）
- 週K ↔ 日K 方向：一致多頭 / 一致空頭 / 訊號分歧（分歧時說明以哪個為準）
```

（保留其後的 `<span class="key-point">K線核心結論（≤15字）</span>` 不動。）

- [ ] **Step 4: result 組裝接上 `_inject_ktables`**

在 `analyze_market_only` 找到 result dict 中 `'html'` 欄用 `_clean_html_output(raw)` 的那行（約 `modules/ai_analyzer_v2.py:1095` 一帶），把它從：

```python
        'html':          _clean_html_output(raw),
```

改為：

```python
        'html':          _inject_ktables(_clean_html_output(raw), enriched_data),
```

（若該行格式或變數名不同，依實際情況把 `_clean_html_output(raw)` 的結果包一層 `_inject_ktables(..., enriched_data)`。）

- [ ] **Step 5: 驗證語法**

Run: `python -m py_compile modules/ai_analyzer_v2.py`
Expected: 無輸出（成功）

- [ ] **Step 6: 確認字串**

Run: `python -c "import modules.ai_analyzer_v2 as m; import inspect; src=inspect.getsource(m.analyze_market_only); print('OK' if '[[K_TABLES]]' in src and '_inject_ktables' in src else 'MISSING')"`
Expected: `OK`

- [ ] **Step 7: 全量測試**

Run: `python -m pytest -q`
Expected: PASS — 全綠（既有 + 本計畫新增測試）

- [ ] **Step 8: Commit**

```bash
git add modules/ai_analyzer_v2.py
git commit -m "fix(report): Bug3+6b — analyze_market_only 第二節改程式產 K 表

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 驗收標準（部署後人工驗）

1. ✅ `python -m pytest -q` 全綠。
2. ⚠️ 使用者 deploy 後燒 ~$0.6 重跑一鍵分析 + 出 PDF：
   - Bug1：無 `<span class="key-point` 殘字外洩。
   - Bug2：每支股第四節「三宗師融合結論」都有完整內文。
   - Bug3：第二節 K 表所有列「高 ≥ 低」，欄序一致。
   - Bug4：撼訊/合晶/大聯大等 short 股 pill 都有「空停」。
   - Bug5：日K 表根數一致（資料源缺漏日已補值，不再忽多忽少）。
   - Bug6a：多根組合型態顯示「早晨之星（3根組合）」等後綴。
   - Bug6b：K 表「型態」欄是型態名、「特徵」欄是量能註記，不再錯位。

## 回滾

純加性 + prompt 改寫，無 DB/migration。任一 bug 修法有問題，`git revert` 對應 Task 的 commit 即可。
