# 報表「建議動作」明確化：實作計畫

> **For agentic workers:** 逐 Task 執行，每 Task 走 TDD（紅→綠→commit）。

**Goal:** 在報表上加「建議動作」pill 一眼可見、強勢突破狀態 emoji 標記、第五節「操作框架」改程式渲染確保格式統一與 pill 同源。

**Architecture:** 兩個純函式（`_decide_action()` + `_render_operation_framework()`）+ DB 欄位 + UI 渲染。spec：`docs/superpowers/specs/2026-05-25-action-pill-and-framework-design.md`

**Tech Stack:** Python / pytest / SQLAlchemy / Vanilla JS

---

## E1 — `_decide_action` 純函式

### Task 1：寫測試 + 實作 `_decide_action`

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（新增函式，置於 `_strong_breakout_state` 之後）
- Test: `tests/test_decide_action.py`（新建）

- [ ] **Step 1: 寫失敗測試**（~12 case 涵蓋決定樹）

關鍵 fixture：
```python
def _swing_long(rl=100, rh=120, target=130):
    """構造 long swing_levels dict。entry_zone=(rl, mid)。"""
    mid = (rl + rh) / 2
    return {
        'direction': 'long',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (rl, mid),
        'invalidation': rl,
        'target': target,
    }

def _swing_short(rl=100, rh=120, target=80):
    mid = (rl + rh) / 2
    return {
        'direction': 'short',
        'range_low': rl, 'range_high': rh,
        'entry_zone': (mid, rh),
        'invalidation': rh,
        'target': target,
    }
```

12 個 test case 見 spec §五。

- [ ] **Step 2: 跑測試確認失敗** — `pytest tests/test_decide_action.py -q`，預期全 fail（函式不存在）。

- [ ] **Step 3: 實作 `_decide_action`** — code 見 spec §四 決策 1。

- [ ] **Step 4: 跑測試確認通過**。

- [ ] **Step 5: commit E1**
  ```
  test(action): _decide_action 12 TDD (plan §三十一)
  feat(action): _decide_action 純函式 (plan §三十一)
  ```
  分 test + feat 兩 commit。

---

## E2 — `_render_operation_framework` 純函式

### Task 2：寫測試 + 實作 `_render_operation_framework`

**Files:**
- Modify: `modules/ai_analyzer_v2.py`（新增函式，置於 `_decide_action` 之後）
- Test: `tests/test_operation_framework.py`（新建）

- [ ] **Step 1: 寫失敗測試**（~6 case 涵蓋 4 種模板）

- [ ] **Step 2: 實作** — code 見 spec §四 決策 2。

- [ ] **Step 3: commit E2**
  ```
  test(framework): _render_operation_framework 6 TDD (plan §三十一)
  feat(framework): _render_operation_framework 純函式 (plan §三十一)
  ```

---

## E3 — 整合：prompt placeholder + post-process

### Task 3：3 個分析函式整合

**Files:**
- Modify: `modules/ai_analyzer_v2.py` (`analyze_market_only` + `analyze_stock_three_masters` + `generate_personal_recommendation`)

- [ ] **Step 1: 找到 3 個函式的「五、操作框架」段**（grep 「五、操作框架」）

- [ ] **Step 2: 把 prompt 中的長段框架字串改為 `[[OPERATION_FRAMEWORK]]` placeholder**

- [ ] **Step 3: AI 呼叫後加 post-process**：
  ```python
  # 在 ai_html 已抽出，但寫入 DB 前
  action_pill = _decide_action(
      status=status,                            # 'hold' / 'watch'
      direction=result.get('direction'),
      structure_flag=monthly_structure.get('structure_flag'),
      swing_levels=swing_levels,                # 已算出
      breakout=_strong_breakout_state(enriched_data, price_f),
      price=price_f,
      cost_stop_loss=cost_stop_loss,            # HOLD 才有
  )
  op_framework = _render_operation_framework(
      action_pill=action_pill,
      direction=result.get('direction'),
      swing_levels=swing_levels,
      breakout=breakout,
      vol_threshold_zhang=int(vol_5avg * 1.5) if vol_5avg else None,
  )
  ai_html = ai_html.replace('[[OPERATION_FRAMEWORK]]', op_framework)
  # 防 AI 忘記 placeholder（雙層防護）
  if '[[OPERATION_FRAMEWORK]]' not in ai_html and '五、操作框架' not in ai_html:
      ai_html += '\n' + op_framework

  result['action_pill'] = action_pill
  result['html'] = ai_html
  ```

- [ ] **Step 4: 確認 3 個函式都做了** + pytest 跑既有測試零退化

- [ ] **Step 5: commit E3**
  ```
  feat(action): analyze_market_only / three_masters / personal 整合 action_pill + framework placeholder (plan §三十一)
  ```

---

## E4 — DB 欄位 + Migration

### Task 4：StockAnalysis 加 action_pill + migration

**Files:**
- Modify: `modules/models.py`（StockAnalysis 加欄位）
- Create: `migrate_add_action_pill.py`
- Modify: 寫入 StockAnalysis 的呼叫端（找 `StockAnalysis(...)` 構造處）

- [ ] **Step 1: models.py 加欄位**
  ```python
  class StockAnalysis(Base):
      # ... 既有欄位
      action_pill = Column(String(32))  # e.g., '🟢 追進 💪'（plan §三十一）
  ```

- [ ] **Step 2: 寫 migration**
  ```python
  # migrate_add_action_pill.py
  import sys
  sys.stdout.reconfigure(encoding='utf-8')
  from sqlalchemy import text
  from modules.database import engine

  with engine.begin() as conn:
      conn.execute(text(
          "ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS action_pill VARCHAR(32)"
      ))
  print("[OK] stock_analyses.action_pill 欄位已加入（IF NOT EXISTS）")
  ```

- [ ] **Step 3: 寫入 StockAnalysis 的呼叫端帶入 action_pill**
  - grep `StockAnalysis(symbol=` 或類似 pattern 找寫入處
  - `result['action_pill']` 傳入 constructor

- [ ] **Step 4: 確認 dashboard API serialize 回 action_pill**
  - grep API endpoint（可能在 `app.py` `/api/stock-list` 之類）
  - 確認 dict serialize 含 `action_pill` 欄位

- [ ] **Step 5: 跑 migration（本機 / Render 部署時自動）**
  ```bash
  python migrate_add_action_pill.py
  ```

- [ ] **Step 6: commit E4**
  ```
  feat(db): StockAnalysis 加 action_pill 欄位 + migration (plan §三十一)
  ```

---

## E5 — Dashboard UI + PDF + CSS

### Task 5：UI 渲染

**Files:**
- Modify: `static/js/dashboard.js` (`buildCard()`)
- Modify: `templates/print_report.html`
- Modify: `static/css/app.css`

- [ ] **Step 1: dashboard.js `buildCard()` 加 actionChip**
  ```javascript
  function actionClass(pill) {
    if (!pill) return 'action-neutral';
    if (pill.startsWith('🟢')) return 'action-bull';
    if (pill.startsWith('🟡')) return 'action-amber';
    if (pill.startsWith('🟠')) return 'action-warn';
    if (pill.startsWith('🔴')) return 'action-bear';
    return 'action-neutral';
  }

  const actionChip = s.action_pill
    ? `<span class="action-pill ${actionClass(s.action_pill)}" title="建議動作">${s.action_pill}</span>`
    : '';
  const statusRowHtml = (dirChip || wyckoffChip || riskChip || actionChip)
    ? `<div class="card-status-row">${dirChip}${wyckoffChip}${riskChip}${actionChip}</div>`
    : '';
  ```

- [ ] **Step 2: print_report.html 加 PDF pill**
  - 找 stock-block-header 區段
  - 加 action pill 顯示

- [ ] **Step 3: app.css 加 5 色樣式**
  ```css
  .action-pill {
    display: inline-flex; align-items: center;
    padding: 2px 8px; border-radius: 12px;
    font-size: 11px; font-weight: 600;
    border: 1px solid;
  }
  .action-bull   { color: #22C55E; border-color: #22C55E33; background: #22C55E11; }
  .action-amber  { color: #F59E0B; border-color: #F59E0B33; background: #F59E0B11; }
  .action-warn   { color: #FB923C; border-color: #FB923C33; background: #FB923C11; }
  .action-bear   { color: #EF4444; border-color: #EF444433; background: #EF444411; }
  .action-neutral{ color: #94A3B8; border-color: #94A3B833; background: #94A3B811; }
  ```

- [ ] **Step 4: `node -c dashboard.js` 確認語法**

- [ ] **Step 5: commit E5**
  ```
  feat(ui): dashboard + PDF action pill + CSS 樣式 (plan §三十一)
  ```

---

## 最後驗證

- [ ] **Step F1: 跑全 pytest** — `pytest tests/ -q`，預期 249 + 18 = 267+ passed
- [ ] **Step F2: py_compile**
  - `python -m py_compile modules/ai_analyzer_v2.py modules/models.py`
- [ ] **Step F3: node -c dashboard.js**
- [ ] **Step F4: 跑 migration（本機）**
- [ ] **Step F5: 更新 CLAUDE.md 進度快照 → §三十一 完成**
- [ ] **Step F6: push origin/main** → Render auto-deploy
- [ ] **Step F7: Deploy 後跑 migration（Render 環境）**
- [ ] **Step F8: 燒 ~$0.6 重跑 5/22 報表** + 對照 5/25 收盤實機驗：見 spec §七

## 回滾策略

E1 / E2 / E3 / E4 / E5 各自純加性：
- E1/E2 新增純函式，不動既有
- E3 prompt placeholder 失敗會 fallback append（雙層防護）
- E4 DB IF NOT EXISTS，revert 後欄位仍在但無寫入
- E5 UI 新增 chip，原 chip 不動

任一有問題 `git revert <commit>` 即可獨立回滾。
