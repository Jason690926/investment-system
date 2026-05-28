# 5/28 cross-check Round 3：Bug-I + Bug-J 設計

- 日期：2026-05-28
- 觸發：§三十五 deploy 後 21:14 重跑新 PDF cross-check
- 對應 plan：§三十六

---

## 一、問題陳述

### Bug-I（P1）：跌穿停損後 P&F 顯示「需先突破」邏輯矛盾

晶心科 5/28 21:14 重跑 PDF（page 3）：
```
建議動作：🔴 出場
停損：224.50 元 — 跌破即論點作廢
P&F理論目標：286元 — 需先突破 260 元觸發
```

程式邏輯：
- `_decide_action` HOLD path：price 219.5 < stop 224.5 → '🔴 出場'
- `_dual_pnf` 同時計算：long P&F target = 286 / 需先突破 260
- AI verbatim 引用後第四節同段顯示「需先突破 260」

家人讀者：「我該出場還是該等突破？」混亂。

### Bug-J（P2）：WATCH long 跌穿 entry_low 但 pill 為「⚪ 觀望」

瑞耘 6532 5/28 21:14 PDF（page 23）：
- phase = 再積累（long phase）
- 5/28 收 96.2 < entry_low 96.8（**已跌穿**）
- pill = ⚪ 觀望（_decide_action WATCH long fall-through default）
- 同段顯示「停損：96.80 元 — 跌破即論點作廢」
- 矛盾：沒進場為何顯示停損？「⚪ 觀望」對「已跌穿失效價」描述太溫和

---

## 二、設計原則

### 原則 1：論點失效時 P&F 不該指向未來
跌穿支撐 / 站回壓力 = 多空論點已被市場否決。P&F target 是「論點成立 → 等幅量度目標」前提，論點失效後不該再顯示。

### 原則 2：判斷時機要早於 AI prompt
P&F 句經 _dual_pnf 注入到 prompt block，AI verbatim 引用後成為第四節內文。後處理無法乾淨覆寫 AI 內文，故 invalidation gate 必須在 _dual_pnf 階段就決定。

### 原則 3：1.5% buffer 避免價格貼著停損晃動反覆切換
晶心科 219.5 / stop 224.5 = -2.2% 明確破位；但若 219.5 / 220 = -0.2% 算「已跌穿」反覆 toggle 不穩。1.5% buffer 確保語義穩定。

### 原則 4：跌穿失效是「主動觀察」狀態，不是「無動作」
🟡 跌穿觀察 vs ⚪ 觀望 — 前者促使家人讀者主動關注「止跌訊號」，後者讓人覺得「保持原樣」。

### 原則 5：結構閘優先於價位閘
若 structure_flag='結構已轉弱'，無論價位在哪都該優先標 🔴 不宜進。跌穿 entry_low 判定只在「結構未轉弱但價已跌穿」的灰色地帶觸發。

---

## 三、影響範圍

### Bug-I
- `modules/ai_analyzer_v2.py`：`_dual_pnf` 早期計算 calc_swing_levels 並偵測 invalidation buffer
- `tests/test_dual_pnf_invalidated.py` 新檔（5 case）

### Bug-J
- `modules/ai_analyzer_v2.py`：`_decide_action` WATCH long path 加跌穿判斷
- `tests/test_decide_action_below_entry.py` 新檔（4 case）

### 不動
- `calc_swing_levels` 簽名
- 其他 pill 字典項
- prompt 結構

---

## 四、為什麼這樣設計

### 1. Bug-I 在 _dual_pnf 而非 _render_operation_framework
P&F sentence 注入 prompt block 給 AI verbatim 引用 → AI 把它寫進第四節「三宗師融合結論」。後處理只能改 _render_operation_framework 的第五節，無法改第四節 AI 內文。所以 invalidation gate 必須在「P&F 句進入 prompt 之前」就決定。

### 2. 1.5% buffer 而非嚴格 cur < stop
家人讀者體驗：價格在 stop ±0.5% 之間反覆 → 系統反覆切換「需先突破」⇄「論點已失效」混亂。1.5% buffer 確保「明確破位」才切換語義。

### 3. Bug-J 新 pill 而非直接用既有「⚪ 觀望」
- ⚪ 觀望 = 「無方向，不該預設進場」
- 🟡 跌穿觀察 = 「結構未轉弱但價已破，主動關注止跌訊號」

兩者實務行為不同，新 pill 更明確。

### 4. 結構閘優先 (line 723) 已是既有設計
`_decide_action` WATCH long path line 723 「if structure_flag == '結構已轉弱': return '🔴 不宜進'」已在跌穿判斷之前，無需改動。

---

## 五、回滾

2 commit 純加性 + 新 pill 字典項：
- `9611f02` revert → _dual_pnf 回 §三十五（晶心科又顯示誤導句）
- `8946529` revert → WATCH long 跌穿回 default ⚪ 觀望

各 commit 獨立 revert 互不依賴。
