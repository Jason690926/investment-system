# 6/8 建議動作客觀化（與持有解耦）+ 2 渲染 bug：實作計畫

> 待執行 TDD 實作計畫（commit 順序 + 每步驗證）。

**Goal:** 建議動作 pill + 一~五節對「持股人/觀察者」一致（客觀局勢判讀），持倉操作只留第六節 + COST/QTY/P-L 列。順帶修 short 空標反向（P1-1）+ 方向 badge 矛盾（P2-1）。

**Spec:** `docs/superpowers/specs/2026-06-08-objective-action-decouple-holding-design.md`

**前置事實（已查證）：**
- `_decide_action` 兩 call site：`ai_analyzer_v2.py:1395`（analyze_market_only）、`:1827`（analyze_stock_three_masters），皆 `status=('hold' if ... else 'watch')`
- `adjust_pill_for_deep_loss` 唯一 read-time 疊加點：`app.py:191-193`（dashboard 讀 DB 既存 pill，不另疊）
- short `target_pnf = pnf_short`（`:1349`，calc_pnf_target 下行目標，恆在價下）→ `a.target_price`（`app.py:734` ← `result['target_pnf']`）
- `_render_operation_framework` 以 direction 驅動（`:991/1016`），pill 僅 echo 於「建議動作」行 → §5 客觀化自動
- `_decide_action` HOLD 分支（`:831-856`）保留不刪（死碼 + 既有測試綠 + 未來 §6 可複用）

---

## T1（test）— 客觀化行為紅燈測試

### 新檔 `tests/test_objective_action_decouple.py`
- **F1-a**：`_decide_action(status='watch', direction='long', 結構未轉弱, entry_zone 含 price)` → `🟢 進場區可佈`（驗 watch 字典；確保改 call site 後持股走這路徑）
- **F1-b**：`_decide_action(status='watch', direction='short', 結構已轉弱, price < 放空區下緣)` → `🟡 等反彈佈空`（晶心科風格）
- **F1-c（整合）**：mock 一檔 holding（深虧 -43%）跑 analyze_market_only → `result['action_pill']` 為 watch 字典（不含「加碼/出場/續抱」）
- **F1-d（回歸）**：`is_holding=True` → `result['html']` 仍含「六、持倉部位建議」節（_strip_section_six 不砍）
- **F2**：short、`support_price`(range_low)=224.5 > price=202.5、`target_price`=192 → 渲染 helper 之 空標取 192（< price）；`target_price` None 或 ≥ price → 空標 pill 不出現
- **F3**：phase=再積累、`entry_low`/`entry_high` 皆 None（采鈺風格）→ badge='觀望'；entry 有值 → badge='多' 不退化

> F2/F3 測 `app.py` pill 組裝邏輯——若該段不易單測，抽純函式 `_build_anchor_pills(a, _dir)` 再測（重構列入 T3/T4）。

### Commit: `test: §三十七 建議客觀化 + short 空標 + 方向 badge 紅燈測試`

---

## T2（feat F1）— status 恆 watch + 移除標頭 deep-loss 疊加

### 修改
- `modules/ai_analyzer_v2.py:1395`、`:1827`：`status=('hold' if ... else 'watch')` → `status='watch'`
- `app.py:190-193`：移除 `if action_pill and mode == 'holding': adjust_pill_for_deep_loss(...)` 疊加（A 法）；保留 `action_pill = getattr(a, 'action_pill', None)`
- **檢查並更新**任何斷言「持股標頭 = HOLD 字典」的既有整合測試（`test_print_report.py` / `test_report_bugfixes.py`）。`test_decide_action*.py` / `test_adjust_pill_extended.py` 直接測函式 → 不受影響保持綠

### 驗證
- 新檔 F1-a~d 轉綠
- `python -m pytest tests/ -q` 全綠（含更新後整合測試）

### Commit: `feat(action): §三十七 建議動作客觀化 — _decide_action 恆 watch + 移除標頭深虧疊加`

---

## T3（feat F2）— short 標頭空標改 P&F 下行目標

### 修改
- `app.py:169`：`空標` 由 `a.support_price` → `a.target_price`；加 guard：`a.target_price is not None and float(a.target_price) < float(price)` 才顯示
- （若 T1 已抽 `_build_anchor_pills`，於此實作）

### 驗證
- F2 測試轉綠（晶心科風格空標=192 < price；華星光風格 525 < 537）
- 全測試綠

### Commit: `fix(pill): §三十七 P1-1 short 標頭空標改 P&F 下行目標（修跑到現價上方）`

---

## T4（feat F3）— 方向 badge 與 pill 同源

### 修改
- `app.py:156-184`：`_dir` 反推為 long/short 但 `a.entry_low is None and a.entry_high is None` → 視為 neutral（badge='觀望'、走撐/壓中性版面），沿用 §三十五 Bug-B dashboard 判據

### 驗證
- F3 測試轉綠（采鈺 badge=觀望；正常 long 不退化）
- 全測試綠

### Commit: `fix(pill): §三十七 P2-1 方向 badge 與實際方向同源（entry 皆 None 視為 neutral）`

---

## T5（docs）

### 修改
- `plan.md` 加 §三十七（本節摘要）
- `docs/superpowers/specs/2026-06-08-objective-action-decouple-holding-design.md`（已建）
- `docs/superpowers/plans/2026-06-08-objective-action-decouple-holding.md`（本檔）
- `CLAUDE.md` 當前進度更新

### Commit: `docs: §三十七 plan + spec + impl plan + 進度`

---

## 驗收 checklist

- [ ] `python -m pytest tests/ -q` 全綠（既有 349 + 新增；扣除整合測試改寫）
- [ ] `python -m py_compile modules/ai_analyzer_v2.py app.py` 通過
- [ ] `node -c static/js/dashboard.js`（未改，sanity）

**Deploy：** push origin main → Render auto-deploy（零 migration）

**零 token 立即生效（dashboard hard refresh）：**
- 持股卡片建議 chip 不再出現「加碼/續抱/出場」，改客觀字（進場區可佈/等回測/等反彈佈空…）— ⚠️ 注意：dashboard 讀 **DB 既存** action_pill，須重跑後才更新（既有 cache 仍是 hold 字典）

**燒 ~$0.6 重跑 14 檔驗證：**
- 創惟/大聯大：標頭建議 = 客觀（進場區可佈/等回測），第六節仍給「不加碼/觀望持有」，**兩者不再矛盾**
- 晶心科：標頭建議 = 🟡 等反彈佈空（客觀 short），第六節給持倉出場/減碼判斷；空標 < 現價（≈192）
- 華星光：標頭空標 < 現價（≈525）
- 采鈺：方向 badge = 觀望（與 pill ⚪ 觀望、四/五節 neutral 一致）

---

## 範圍邊界（明確不做）

- **進場區 <3% 過近的 pill 細化**：原 P1-2 觀察的「進場區距停損過近仍標進場區可佈」— F1 已結構性解掉「持有→加碼」矛盾；proximity 屬「watch/hold 通用」的細化，且已由 `_entry_proximity_warning` 在 §3/§5 文字呈現，本輪不擴大
- **強勢回檔股寬停損**（矽力 -25% / 合晶 -35%）：calc_swing_levels 設計取捨，列觀察
- **deep-loss B 法**（§6 旁 read-time 個人小字）：A 法不足時再評估
- **新增 direction 欄位**：F3 採零-migration 判據，robust 版列日後選項

---

## 回滾策略

| Commit | revert 影響 |
|--------|------------|
| T2 (F1) | 標頭恢復 hold/watch 雙字典 + 深虧疊加（創惟/晶心科矛盾復現）|
| T3 (F2) | short 空標恢復 range_low（跳空時又顯示價上目標）|
| T4 (F3) | 方向 badge 恢復純相位反推（采鈺又顯「多」）|
| T1/T5 | 測試 / 文件純加性 |

各 commit 獨立 revert 互不依賴（T2 為行為主軸但純客觀化、不碰 §6/RISK）。
