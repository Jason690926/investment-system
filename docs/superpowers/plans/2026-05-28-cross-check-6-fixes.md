# 5/28 cross-check 6 修法：實作計畫

> 已執行完畢的實作 plan，作為 commit 順序 + 驗證 checklist 紀錄。

**Goal:** 5/26 報表 vs 5/27-5/28 走勢 cross-check 14 檔，修 5 bug + 1 優化 + 1 文件不一致。

**Architecture:**
- 分層職責：DB base pill + 讀取端 post-process（避免 cross-user 污染）
- 純加性 helper / 既有函式 default None 參數（向後相容）
- TDD：先紅 → 實作 → 綠

**Spec:** `docs/superpowers/specs/2026-05-28-cross-check-6-fixes-design.md`

---

## C1 — Bug-1（HOLD 深虧 gate）+ Bug-3（short boundary buffer）

### 修改檔案
- `modules/ai_analyzer_v2.py`：
  - `_decide_action` 加 `pl_pct=None` 參數，HOLD 路徑「加碼」前檢查 `pl_pct ≤ -20`
  - `_decide_action` short path 加 `zlo_buf = zlo × 1.005` boundary buffer
  - 新 helper `adjust_pill_for_deep_loss(pill, pl_pct, threshold=-20)` 供讀取端覆寫
- `app.py` `_render_one_block`：mode=holding 算出 pnl_pct 後呼叫 helper
- `static/js/dashboard.js`：
  - JS helper `adjustPillForDeepLoss(pill, status, avgCost, price)`
  - `buildCard` 套用 + `updateCardPrice` 載入後重評 pill DOM
- `tests/test_decide_action_pl_gate.py` 新檔（8 case）

### Commit: `cec5bff feat(action): Bug-1 HOLD 深虧 gate + Bug-3 short boundary buffer`

---

## C2 — Bug-2（突破首日警示）+ Bug-4（雙重停損 hierarchy）

### 修改檔案
- `modules/ai_analyzer_v2.py` `_render_operation_framework`：
  - breakout=True 分支加 watermark：「⚠️ 突破首日反轉風險：假突破常於突破後 1-2 日翻盤」
  - 主停損（🔴）vs 次停損（🟠）label hierarchy，取代單一「停損：」
- `tests/test_operation_framework_hierarchy.py` 新檔（6 case）

### Commit: `3e1cc23 feat(framework): Bug-2 突破首日警示 + Bug-4 雙重停損 hierarchy`

---

## C3 — Opt-1（P&F 揭露假設條件）

### 修改檔案
- `modules/candlestick.py`：新函式 `calc_pnf_target_relaxed(bars, lookback, current_price, direction) -> (target, gate) | None`
- `modules/ai_analyzer_v2.py` `_dual_pnf`：strict None 時嘗試 relaxed → 注入「P&F理論目標：X 元 — 需先突破/跌破 Y 元觸發」整句
- `tests/test_pnf_target_relaxed.py` 新檔（4 case）
- `tests/test_dual_pnf_quantize.py` 1 case 改寫（reflect 新行為）+ 1 case 新增 relaxed 場景

### Commit: `51145a9 feat(pnf): Opt-1 strict 失敗時揭露理論目標 + 觸發 gate`

---

## C4 — Bug-5（CLAUDE.md 微星驗收更正）+ docs

### 修改檔案
- `CLAUDE.md` §三十二 驗收表：Bug-1+2 結果改「4/5 ✅」並註明「微星未生效（_strong_breakout_state 不觸發）」
- `plan.md` §三十四（本修法摘要）
- `docs/superpowers/specs/2026-05-28-cross-check-6-fixes-design.md`
- `docs/superpowers/plans/2026-05-28-cross-check-6-fixes.md`（本檔）

### Commit: `docs: Bug-5 + plan.md §三十四 (5/28 cross-check)`

---

## 驗收 checklist

執行完 C1-C4 後：

- [x] `git log --oneline -5` 顯示 4 commit + 1 docs（本批次合計 4-5 commit）
- [x] `python -m pytest tests/ -q` **315 全綠**（291 既有 + 24 新 - 部分改寫扣除）
- [x] `python -m py_compile modules/{ai_analyzer_v2,candlestick}.py app.py` 全綠
- [x] `node -c static/js/dashboard.js` 通過

**Deploy 步驟（用戶執行，沿用 §三十三 已驗證路徑）：**
1. push origin main → Render auto-deploy
2. Hard refresh dashboard

**Deploy 後驗收 — 零 token（讀取端 post-process 立即生效）：**
- 晶心科 print PDF：pill 應由「🟢 加碼」覆寫為「🟡 觀望持有」（既有 cache 透過 read-time 覆寫）
- dashboard 載入 price 後晶心科卡片 pill 同樣覆寫

**Deploy 後驗收 — 燒 ~$0.6 重跑（驗 AI prompt 渲染）：**
- 強勢突破股第五節含 watermark + 主/次停損 hierarchy
- P&F「— 元」減少，改顯示「P&F理論目標：X 元 — 需先突破 Y 元觸發」
- 撼訊 short 重跑後 pill 走 boundary buffer 邏輯

---

## 回滾策略

| Commit | revert 影響 |
|--------|------------|
| C1 (cec5bff) | _decide_action 回 §三十一 簽名 + dashboard/PDF 無深虧調整 |
| C2 (3e1cc23) | 強勢突破第五節回單一「停損」+ 無 watermark |
| C3 (51145a9) | calc_pnf_target_relaxed 不存在 + _dual_pnf 沿用「—」 |
| C4 (docs)    | 純文件，無功能影響 |

各 commit 獨立 revert 互不依賴。
