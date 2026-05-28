# 5/28 cross-check 6 修法：設計

- 日期：2026-05-28
- 觸發：用戶 5/26 21:46 報表 + 5/27/5/28 OHLC（手動撈 yfinance + TPEx）cross-check 14 檔
- 對應 plan：§三十四

---

## 一、問題陳述

### Bug-1（P0）：HOLD -34% 虧損仍標「🟢 加碼」

晶心科 6533（HOLD，cost=355 / 5/26 收 234.5 / 虧 -33.9%）：
- 5/26 PDF：威科夫「再積累」+ 結構未轉弱 + 現價在進場區 224.5-242.25 → pill「🟢 加碼」
- 5/27 跌至 228 / 5/28 收 219.5（跌穿停損 224.5）→ -6.4% 兩日跌幅
- 家人讀者看「🟢 加碼」可能再買 → 再虧

**根因**：`_decide_action` HOLD path 只看結構（breakout / entry_zone / structure_flag），**完全沒考慮個人虧損深度**。深虧已 -34% 仍標加碼 = 攤平擴大敞口。

### Bug-2（P0）：強勢突破首日翻盤、pill「追進 💪」誤導

東捷 8064 / 瑞軒 2489 5/26「🟢 追進 💪」、5/27 即跌穿追進停損：
- 東捷 5/26 收 149 / 追進停損 143.5 → 5/27 跌至 140 / 5/28 收 133（-10.74%）
- 瑞軒 5/26 收 51.7 / 追進停損 48.85 → 5/27 跌至 48.3 / 5/28 收 48（-7.16%）

`_strong_breakout_state` 三條件 A/B/C 擇一即過，但無「突破後維持 N 日」確認 → 1 日翻盤即陷阱。

### Bug-3（P1）：撼訊 short pill「分批佈空」實際應「等反彈佈空」

撼訊 6150 5/26 收 70.0 vs 空進區 (69.60, 74.70)：
- 距 zlo 僅 +0.57%，技術上仍在區內 → pill 🔴 分批佈空
- 5/27 跌至 66.8 / 5/28 反彈到 68 — 整個 5/27-5/28 在區下方 → 實際應「🟡 等反彈佈空」

### Bug-4（P1）：強勢突破雙重停損家人讀者易混淆

東捷 5/26 第五節：
```
追進停損：143.50 元
回測進場（保守）：139.19 ~ 143.50 元
停損：75.00 元 — 跌破即論點作廢
```

家人讀者看「停損 75」當主停損 → 5/27 跌至 140 不會動作 → 但實際應該看「追進停損 143.5」已觸發。

### Bug-5（P2）：§三十二 spec 與實際 deploy 不一致

CLAUDE.md §三十二 spec 列「微星 retest 120.28-124.00 / target 163」（5 檔強勢突破之一），但 5/26 PDF 實際 entry_zone = 94.50~109.25（未被 _breakout_overrides 覆寫）。

**根因**：微星 5/26 收 126，range_high=124，僅高 +1.6%，不符 strong_breakout B 條件（需 ×1.05 以上）→ helper 未觸發。CLAUDE.md「✅ 驗收結果」表也沒列微星 → 文件 vs 實作脫節。

### Opt-1（P2）：P&F 目標 14 檔中 11 檔顯示「— 元」

`calc_pnf_target` Filter A/B/C 設計保守（避免誤導），但 79% 案例藏起來 = 失去「未來上漲空間」核心參考。

---

## 二、設計原則

### 原則 1：分層職責 — DB cache 為跨用戶共用 base，讀取端 post-process

DB StockAnalysis 跨用戶共用 cache，個人化 P/L gate 必須在讀取端：
- AI 分析時：`_decide_action` 不傳 pl_pct → DB 寫入 base pill
- PDF/dashboard 讀取時：算用戶 P/L → `adjust_pill_for_deep_loss` 覆寫

### 原則 2：強勢突破風險揭露，不靜默停損

Bug-2 不刪除「追進 💪」pill（保留多頭趨勢框架），但加 watermark 明確警告「首日反轉風險高」+ 主/次停損 hierarchy。讓家人讀者主動執行追進停損。

### 原則 3：boundary buffer 防 short 邊界誤判

short path zlo 邊界 +0.5% 緩衝 — 距離 zlo 太近視為「下行勢頭已啟動」改判等反彈。撼訊 5/27-5/28 直接驗證。

### 原則 4：揭露假設條件 > 藏起來

P&F 目標 Filter 失敗時改顯示「理論目標 X 元 — 需先突破/跌破 Y 元觸發」，揭露「未觸發」狀態而非「—」。

---

## 三、影響範圍

### 程式修改
- `modules/ai_analyzer_v2.py`：
  - `_decide_action` 加 pl_pct 參數 + HOLD 深虧 gate
  - `_decide_action` short path 加 zlo×1.005 buffer
  - `_render_operation_framework` breakout=True 分支重整 hierarchy + watermark
  - `_dual_pnf` 整合 relaxed sentence
  - 新 helper `adjust_pill_for_deep_loss`
- `modules/candlestick.py`：新函式 `calc_pnf_target_relaxed`
- `app.py`：`_render_one_block` mode=holding 套用 `adjust_pill_for_deep_loss`
- `static/js/dashboard.js`：`adjustPillForDeepLoss` JS helper + `updateCardPrice` 重評估 pill

### 文件
- `CLAUDE.md` §三十二 驗收表更正（微星實際 4/5 ✅）
- `plan.md` §三十四（本修法）
- spec + impl plan（本文件 / 兄弟文件）

### Tests
- `tests/test_decide_action_pl_gate.py`（新檔，8 case）
- `tests/test_operation_framework_hierarchy.py`（新檔，6 case）
- `tests/test_pnf_target_relaxed.py`（新檔，4 case）
- `tests/test_dual_pnf_quantize.py` 1 case 改寫 + 1 case 新增

### 不動
- AI prompt 結構（純 helper 加性）
- DB schema
- 既有 `_strong_breakout_state` 三條件 A/B/C（Bug-2 採 watermark 不改判定）

---

## 四、修法摘要

詳見對應 commit / impl plan。本 spec 只記設計思路。

---

## 五、為什麼這樣設計

### 1. Bug-1 用 user 端 post-process 而非分析時 inject pl_pct
DB cache 跨用戶共用，inject 個人 cost 會 cross-user 污染。讀取端 post-process 是乾淨的分層。

### 2. Bug-2 採 watermark 不採「延遲確認 N 日」
延遲確認會把矽力 / 合晶等真強勢誤判 → 用戶錯過追進時機。Watermark 讓家人讀者**主動**執行追進停損，由用戶判斷風險承受度。

### 3. Bug-3 buffer ×1.005 不採更大值
撼訊 5/26 70.0 vs zlo 69.60 距離 +0.57% — buffer 至少 0.5% 才生效。更大會誤殺真正在區內的 case（如 vs zlo +1% 反而是「分批佈空」典型場景）。

### 4. Bug-4 用 🔴 主 / 🟠 次 emoji hierarchy
與 _decide_action pill 配色一致（🔴 出場 / 🟠 減碼）— 語義延續性高，家人讀者已熟悉。

### 5. Opt-1 box 寬度上限不放寬
relaxed 仍套用 max_range 15%（日 K） / 20%（週 K）—— 趨勢段絕對不該標「目標」誤導。只是放寬「現價是否已超」濾鏡。

---

## 六、回滾

4 commit 純加性 helper / 既有函式 default None 參數：
- C1 (Bug-1+3) revert → _decide_action 回 §三十一 簽名
- C2 (Bug-2+4) revert → 強勢突破第五節回單一「停損」+ 無 watermark
- C3 (Opt-1) revert → calc_pnf_target_relaxed 不存在 + _dual_pnf 沿用「—」
- 各 commit 獨立 revert 互不依賴
