# 5/28 cross-check Round 2：實作計畫

> 已執行完畢的實作 plan，作為 commit 順序 + 驗證 checklist 紀錄。

**Goal:** §三十四 deploy 後 cross-check 發現 5 bug（Bug-H/A/D/G/B），追加修法。

**Architecture:** 分層職責（DB cache 防污染）+ 純加性 helper / signature 擴展 + prompt 強化

**Spec:** `docs/superpowers/specs/2026-05-28-cross-check-round2-design.md`

---

## C1 — Bug-H：API error 永久污染 cache（P0）

### 修改檔案
- `modules/ai_analyzer_v2.py`：新 `AIGenerationError` + `_detect_error_kind` + `generate_personal_recommendation` raise
- `app.py`：`api_recommend_stock` try/except + 偵測既有壞 cache 刪除
- DB cleanup（一次性）：刪除既有 5/28 兩筆 `AI分析失敗%` cache（6533/6104）
- `tests/test_ai_generation_error.py` 新檔（11 case）

### Commit: `da4e3ac feat(error): Bug-H API error 永久污染 cache + leak 修法`

---

## C2 — Bug-A：深虧「續抱」誤導（P0）

### 修改檔案
- `modules/ai_analyzer_v2.py`：`adjust_pill_for_deep_loss` 擴大 catch '加碼' + '續抱'
- `tests/test_adjust_pill_extended.py` 新檔（9 case）

### Commit: `db29965 feat(action): Bug-A 深虧 gate 擴大 catch「續抱」`

---

## C3 — Bug-D：Opt-1 「需先突破 Y」目標已達成場景誤導（P0）

### 修改檔案
- `modules/candlestick.py`：`calc_pnf_target_relaxed` signature → (target, gate, status) 三元組
- `modules/ai_analyzer_v2.py`：`_dual_pnf` 依 status 切換 sentence
- `tests/test_pnf_relaxed_status.py` 新檔（4 case）
- `tests/test_pnf_target_relaxed.py` 4 case 改解構三元組
- `tests/test_dual_pnf_quantize.py` 既有 case 改 monkeypatch 回三元組 + 新增 reached case

### Commit: `8f0e973 feat(pnf): Bug-D Opt-1 relaxed 加 status 區分 pending/reached`

---

## C4 — Bug-G + Bug-B：prompt 隔離 + frontend neutral fallback（P1）

### 修改檔案
- `modules/ai_analyzer_v2.py`：`analyze_market_only` 兩處 prompt 強化
  1. 【持倉提示】改寫為明確隔離 RISK/方向/量價
  2. 風險評分原則加「客觀性鐵律」（兩個 prompt 共用此原則）
- `static/js/dashboard.js`：`renderAnchorStrip` 增「entry 為 None 走 neutral path」分支
- 純 prompt + frontend 不新增 test

### Commit: `747fbb3 feat(prompt+ui): Bug-G is_holding prompt 隔離 + Bug-B 錨點 strip neutral fallback`

---

## C5 — 文件

### 修改檔案
- `plan.md` 加 §三十五
- `docs/superpowers/specs/2026-05-28-cross-check-round2-design.md` 新檔
- `docs/superpowers/plans/2026-05-28-cross-check-round2.md` 新檔（本檔）
- `CLAUDE.md` 進度更新（如需）

### Commit: `docs: plan.md §三十五 + spec + impl plan + CLAUDE.md update`

---

## 驗收 checklist

執行完 C1-C5 後：

- [x] `git log --oneline -6` 顯示 5 commit + 1 docs
- [x] `python -m pytest tests/ -q` **340 全綠**
- [x] `python -m py_compile modules/{ai_analyzer_v2,candlestick}.py app.py` 全綠
- [x] `node -c static/js/dashboard.js` 通過

**Deploy 步驟（用戶執行）：**
1. push origin main → Render auto-deploy
2. Hard refresh dashboard 觀察

**Deploy 後驗收 — 零 token（讀取端 post-process 立即生效）：**
- 晶心科 dashboard pill 從「🟢 續抱」→「🟡 觀望持有」（Bug-A）
- 晶心科 dashboard 錨點 strip 從「— | — | —」→「區間 213-249.5 | 雙向」（Bug-B）
- 個股詳情頁不再 leak raw API error；credit 不足顯示「AI 服務額度不足」（Bug-H）

**Deploy 後驗收 — 燒 ~$0.6 重跑（驗 AI prompt 行為）：**
- 強勢突破股 P&F 句改為「先前等幅量度 X 已達成」（Bug-D）
- 14 檔重跑 RISK 評分對 holding/watching 切換更穩定（Bug-G — 需 A/B test）

---

## 回滾策略

| Commit | revert 影響 |
|--------|------------|
| C1 (da4e3ac) | AIGenerationError 不存在 + endpoint 回舊行為 |
| C2 (db29965) | 「續抱」回到不被 deep_loss catch |
| C3 (8f0e973) | relaxed 回兩元組（須一併 revert 既有 test 改動）|
| C4 (747fbb3) | prompt 回舊版 + frontend 回 long-only path |
| C5 (docs)    | 純文件，無功能影響 |

各 commit 獨立 revert，除 C3 因 signature 改動需配對 test。
