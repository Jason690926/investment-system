# 5/28 cross-check Round 2：5 修法設計

- 日期：2026-05-28
- 觸發：§三十四 deploy 後用戶 5/28 20:25 重跑 + 20:39 個股詳情截圖 cross-check
- 對應 plan：§三十五

---

## 一、問題陳述

### Bug-H（P0）：API error 永久污染 cache + 跨入口 leak

用戶 5/28 個股詳情頁「📌 持股操作建議」截圖：

```
AI分析失敗: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error',
'message': 'Your credit balance is too low to access the Anthropic API. ...'}, 'request_id': ...}
```

**根因鏈**：
1. `_generate` 失敗時 return `f"AI分析失敗: {err}"` — 整個 exception 字串
2. `generate_personal_recommendation` 不檢查直接 return 給 caller
3. `api_recommend_stock` 不驗證直接寫入 `PersonalRecommendation.html` cache
4. 下次調用：`existing_rec` 命中即回 cache 的 error string → **永久壞掉**

**影響範圍**：
- 個股詳情頁：直接 leak raw error（已證實）
- 印列 PDF：理論上會 leak（read 同 cache）
- 即使 credit 充值，cache 不會自動修復

### Bug-A（P0）：深虧「續抱」誤導

晶心科 5/28：cost=355 / price=219.5 / pl=-38.2%
- AI direction = **neutral**（5/26 是 long，週 K 動能轉折）
- _decide_action HOLD path：structure_flag != 已轉弱 + breakout=False + entry_zone=None → fallback `🟢 續抱`
- §三十四 Bug-1 修法只 catch「加碼」字眼 → 「續抱」漏網
- 家人讀者掃頂部「🟢 續抱」放心，第六節「持倉停損 213 元」被忽略

### Bug-D（P0）：Opt-1 「需先突破 Y」對「目標已達成」場景誤導

5/28 PDF 多檔顯示：
- 矽力：「P&F理論目標：373 — 需先突破 320」（但現價 620）
- 東捷：「P&F理論目標：52.2 — 需先突破 46.4」（但現價 133）
- 合晶：「P&F理論目標：41.9 — 需先突破 36.2」（但現價 90.7）
- 瑞軒：「P&F理論目標：40.1 — 需先突破 35.5」（但現價 48）

**根因**：`calc_pnf_target_relaxed` 沒區分「Filter A 失敗（未突破）」vs「Filter B 失敗（目標已達成）」。後者顯示「需先突破 X」邏輯不通。

### Bug-G（P1）：is_holding 可能污染 RISK_PCT 客觀性

`analyze_market_only` line 1459-1463 對 `is_holding=True` 注入：
```
【持倉提示】本分析的讀者為「已持有此股」的投資人，請務必輸出第六節...
```

雖然 prompt line 1601 寫「風險 = 與多空無關」，但 AI 可能在評 RISK 時被「讀者是持股人」這個高權重提示暗中加成。晶心科 42%→62% 升 20pp 可能含污染。

### Bug-B（P1）：晶心科 dashboard 錨點 strip 全「— | — | —」

**根因鏈**：
- AI direction=neutral
- `calc_swing_levels(daily_bars, 'neutral', _price_f)` 對 neutral 不回 `entry_zone`（API 語意）
- 寫入 DB entry_low/high=None
- frontend `renderAnchorStrip` 依 `wyckoff_phase='再積累'` 反推 long → 走 long path → entry_low/high 為 None → 顯示 '—'

---

## 二、設計原則

### 原則 1：分層職責 — DB cache 不該污染、cleanup 不靠用戶

Bug-H 多層：`generate_personal_recommendation` raise / endpoint catch / 偵測既有壞 cache 自動清。AI error 不該變成「持久化內容」。

### 原則 2：覆寫範圍要涵蓋所有 default 路徑

Bug-A：`_decide_action` HOLD path 對深虧 + 無明確訊號的 default「續抱」也要被 deep_loss gate 攔截。

### 原則 3：揭露假設條件，但區分狀態

Bug-D：relaxed 不該對所有 Filter 失敗都套同一句。'pending'（未突破）需保留「需先突破」；'reached'（已達成）改「等新箱形成」。

### 原則 4：個人化旗標的影響範圍要明示

Bug-G：is_holding 對 AI 是高權重提示，prompt 必須明示「僅影響第六節是否輸出，禁止影響 RISK/方向/量價」。

### 原則 5：frontend 解 backend API 限制

Bug-B：calc_swing_levels neutral 不回 entry_zone 是合理 API 語意；frontend 應該偵測「entry 為 None」即 fallback 走 neutral path。

---

## 三、影響範圍

### Bug-H
- `modules/ai_analyzer_v2.py`：`AIGenerationError` + `_detect_error_kind` + `generate_personal_recommendation` raise
- `app.py`：`api_recommend_stock` try/except + 偵測既有壞 cache 刪除
- DB cleanup（一次性）：刪除既有 `PersonalRecommendation` where `html LIKE 'AI分析失敗%'`

### Bug-A
- `modules/ai_analyzer_v2.py`：`adjust_pill_for_deep_loss` 擴大 catch 範圍

### Bug-D
- `modules/candlestick.py`：`calc_pnf_target_relaxed` 改三元組 (target, gate, status)
- `modules/ai_analyzer_v2.py`：`_dual_pnf` 依 status 切換 sentence
- 既有 4 個 `test_pnf_target_relaxed.py` 改解構三元組

### Bug-G
- `modules/ai_analyzer_v2.py`：`analyze_market_only` 兩處 prompt 強化

### Bug-B
- `static/js/dashboard.js`：`renderAnchorStrip` neutral fallback 條件擴大

### 不動
- `_generate` 簽名（向後相容）
- DB schema
- `calc_swing_levels` neutral API 語意

---

## 四、為什麼這樣設計

### 1. Bug-H 不改 _generate 全局 raise
`_generate` 被 7+ 個 caller 用（大盤分析 / 週報 / 個股 / NEWS / 產業指標股）。若全部 raise，每個都要包 try/except。範圍太大且風險高。

只對「會寫進 PersonalRecommendation cache」的 `generate_personal_recommendation` raise — 精準針對污染入口。其他 caller 寫入 StockAnalysis.html_content 等 column 不受影響（這些 column 內含 error 也只是該股單次顯示異常，不會 cross-day persist）。

### 2. Bug-A 不解決「entry_zone=None 時走更聰明的 path」
這需要 `_decide_action` HOLD path 對「neutral / 數據不足」更精細區分（如根據 cost_stop_loss 計算）。但設計大改動成本高、副作用未知。

只擴大 deep_loss catch 是最小 surgical fix — 對家人讀者最重要的「不誤導」目標達成。

### 3. Bug-D status 三元組向後相容
既有 4 個 test 解構為 (target, gate) → 改為 (target, gate, _status) 一行 sed 即可。新增 status 在第 3 位，舊 code 若只取 [0], [1] 仍 work。

### 4. Bug-G prompt 而非結構改動
無法在不修改 cross-user cache 設計的前提下移除 is_holding 旗標。只能教 AI 隔離。需 deploy 後重跑驗 prompt 行為。

### 5. Bug-B 後端不改 calc_swing_levels neutral
neutral 不回 entry_zone 是合理的 — neutral 意思是「無方向，不該預設進場區」。改後端會破壞語意。frontend fallback 是乾淨解法。

---

## 五、回滾

5 commit 純加性 + signature 擴展 + 既有函式新參數 default：

- `da4e3ac` revert → AIGenerationError 不存在 + api_recommend_stock 回舊行為（仍會寫 error cache 但前端已改不顯示）
- `db29965` revert → 「續抱」回到不被 deep_loss catch
- `8f0e973` revert → relaxed 回兩元組（**注意：既有 test 已 unpack 3 個，須一併 revert test 改動**）
- `747fbb3` revert → prompt 回舊版 + frontend 回 long-only path

最壞情境：`8f0e973` signature 改動跟既有 callers 不對齊 → fix 既有 test 後再 revert，或保留新 signature 但回到舊 sentence 邏輯。
