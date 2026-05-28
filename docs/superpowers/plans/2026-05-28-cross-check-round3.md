# 5/28 cross-check Round 3：實作計畫

> 已執行完畢的實作 plan，作為 commit 順序 + 驗證 checklist 紀錄。

**Goal:** §三十五 deploy 後 cross-check 發現 Bug-I + Bug-J，追加修法。

**Spec:** `docs/superpowers/specs/2026-05-28-cross-check-round3-design.md`

---

## C1 — Bug-I：跌穿停損後 P&F 改顯論點已失效

### 修改檔案
- `modules/ai_analyzer_v2.py`：`_dual_pnf` 加 invalidation gate
- `tests/test_dual_pnf_invalidated.py` 新檔（5 case）

### Commit: `9611f02 feat(pnf): Bug-I 跌穿停損後 P&F 改顯論點已失效`

---

## C2 — Bug-J：WATCH long 跌穿 entry_low 加新 pill「🟡 跌穿觀察」

### 修改檔案
- `modules/ai_analyzer_v2.py`：`_decide_action` WATCH long path 加跌穿判斷
- `tests/test_decide_action_below_entry.py` 新檔（4 case）

### Commit: `8946529 feat(action): Bug-J WATCH long 跌穿 entry_low 加新 pill`

---

## C3 — 文件

### 修改檔案
- `plan.md` 加 §三十六
- `docs/superpowers/specs/2026-05-28-cross-check-round3-design.md` 新檔
- `docs/superpowers/plans/2026-05-28-cross-check-round3.md` 新檔（本檔）

### Commit: `docs: plan.md §三十六 + spec + impl plan`

---

## 驗收 checklist

執行完 C1-C3 後：

- [x] `git log --oneline -3` 顯示 2 commit + 1 docs
- [x] `python -m pytest tests/ -q` **349 全綠**
- [x] `python -m py_compile modules/ai_analyzer_v2.py` 通過

**Deploy 步驟：** push origin main → Render auto-deploy

**Deploy 後驗收 — 燒 ~$0.05 / 單檔重跑：**
- 晶心科重跑後第四節 P&F 句改為「論點已失效（跌穿支撐 224.5 元）」
- 瑞耘重跑後 pill 從「⚪ 觀望」改「🟡 跌穿觀察」

---

## 回滾策略

| Commit | revert 影響 |
|--------|------------|
| C1 (9611f02) | _dual_pnf 回 §三十五（跌穿停損仍顯示「需先突破」誤導）|
| C2 (8946529) | WATCH long 跌穿回 default ⚪ 觀望 |
| C3 (docs)    | 純文件 |

各 commit 獨立 revert 互不依賴。
