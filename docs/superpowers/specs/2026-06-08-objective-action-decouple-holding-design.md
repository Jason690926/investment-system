# 6/8 cross-check：建議動作客觀化（與持有解耦）+ 2 渲染 bug 設計

- 日期：2026-06-08
- 觸發：用戶提供 6/8 20:06 持股分析報告 PDF（23 頁、3 持股 + 9 觀察），當日大盤 -3.48% 重挫，多檔跳空跌破箱底，逼出渲染邊界 bug
- 對應 plan：§三十七
- 用戶定案：建議動作 + 一~五節全客觀（持股人/觀察者同一套）；持倉專屬只剩 COST/QTY/P-L 列 + 第六節；deep-loss 採 **A 法**（不另做個人化覆寫，靠 P/L 列紅字 + §6）

---

## 一、問題陳述

### 核心訴求：建議動作不該因「持有」而改變

用戶原話：「我是希望不要納入因為持有該檔股票，所以建議操作而有所不同，持有會有持有的建議操作，但是每檔分析應該是更專業的對當下局勢或走勢發展來建議」。

**現況**：`_decide_action(status='hold'/'watch')`（`ai_analyzer_v2.py:1395 / :1827`）對同一客觀局勢，依持有與否產生**不同字典**：

| status | pill 字典 |
|--------|-----------|
| hold | 加碼 💪 / 加碼 / 續抱 / 減碼 / 出場 / 觀望持有 |
| watch | 追進 💪 / 進場區可佈 / 等回測 / 突破未驗 / 跌穿觀察 / 不宜進 / 分批佈空 / 等反彈佈空 / 論點作廢 / 觀望（不宜空）/ 觀望 |

標頭 pill 與第五節操作框架（`_render_operation_framework`，由 pill 渲染）因此都隨持有變動。第六節「持倉部位建議」（AI 生成、user-agnostic）才是持倉專屬。

**已隔離（不需動）**：RISK_PCT / WYCKOFF / DIRECTION / 量價 已由 §三十五 Bug-G 鐵律（`:1551`）約束對三類讀者一致。

### 此模型同時結構性解掉兩個並存矛盾

6/8 PDF 證據：

**創惟（HOLD, long, -13.3%）** page 3：pill `🟢 加碼`；第三節「進場區下緣距現價<3%，優先標neutral觀望」；第六節「持有但**不加碼**」。
**大聯大（HOLD, long, -4.4%）** page 5：pill `🟢 加碼`；現價 108＝進場區下緣＝停損（gap 0%）；第六節「**暫不加碼**」。
**晶心科（HOLD, short 結構, -43%）** page 1/3：pill `🔴 出場`；第六節「觀望持有」。

根因：HOLD 字典（加碼/出場）由 `_decide_action` 確定性路徑產生（`:844-849` price 在 entry_zone → 加碼；deep-loss gate 只在 ≤ -20% 觸發，創惟 -13.3% 未達），AI 第六節看全局後標保守 → 兩條決策路徑分歧。**標頭改客觀後 HOLD 字典從標頭消失，矛盾的兩個來源不再並存，無需個別 patch。**

### 連帶 Bug P1-1：short 標頭「空標」跑到現價上方（財務反向）

| 股 | 標頭空標 | 現價 | 第五節/四節 P&F 空標 |
|----|---------|------|---------------------|
| 晶心科 | **224.5** | 202.5 | 192 |
| 華星光 | **594** | 537 | 525 |

根因：`app.py:169` short 空標 = `a.support_price` = swing `range_low`（箱底）。今日跳空跌破箱底 → `range_low` 滯留於現價上方，當「下行目標」顯示在現價之上，語義反了；且與第五節（`_render_operation_framework:1022` 用 `sl.target`）、第四節（P&F `target_pnf`）數字不一致 → 同張報表兩個「空標」。

### 連帶 Bug P2-1：方向 badge 與結論矛盾

**采鈺（WATCH）** page 7/8：標頭方向=**多**、箱底/箱頂（long 視覺）；但 pill `⚪ 觀望`、第四節「本次方向：neutral」、第五節「neutral 觀望中」。

根因：`app.py:158` badge = `phase_to_direction(再積累)=long`，但 AI 實際 DIRECTION=neutral（跌穿 long 失效價 506）。pill 用真實 direction 算（neutral）→ ⚪ 觀望；badge 用相位反推 → 多。§三十五 Bug-B 只修了 dashboard 錨點 strip，PDF 標頭 badge 未修。

---

## 二、設計原則

### 原則 1：標頭建議 = 客觀局勢判讀，持有不改變它
同一支股、同一份客觀資料，對「持股人 / 觀察者 / 觀望者」標頭建議 pill 必須一致。持有與否只決定「是否額外輸出第六節」與「是否顯示 COST/QTY/P-L 列」。

### 原則 2：持倉操作建議只活在第六節（A 法）
續抱/減碼/出場/觀望持有等持倉動作只出現在第六節。深虧（≤ -20%）的個人化提醒**不再疊加到標頭**——靠 P/L 列紅字（已顯示 -43%）+ 第六節結構建議承載。第六節維持 user-agnostic（不回退 §二十八 跨用戶 cache 污染）。

### 原則 3：第五節已是 direction 驅動，pill 客觀化即自動一致
`_render_operation_framework` 以 `direction`（long/short/neutral）分支，進場區/停損/目標/空進/空停/空標皆取自 swing_levels，本就客觀；只有頂部「建議動作：{pill}」echo 了 pill 字串。pill 客觀化後第五節自動對齊，無需改 framework 結構。

### 原則 4：空標必在現價下方，否則不顯示（誠實 > 錯誤）
short「空標（下行目標）」語義上必在現價下方。改用 `target_pnf`（calc_pnf_target short 幾何鏡像，必在價下，且 = 第四節 P&F 句同源）。None 或 ≥ 現價 → 不顯示該 pill。

### 原則 5：方向 badge 與 pill 同源（零 migration 沿用 dashboard 既有判據）
§三十五 Bug-B dashboard 已用「同 phase 但 entry_low/high 皆 None → neutral」判據。PDF badge 沿用：相位反推為 long/short 但 entry_low 與 entry_high 皆 None → 視為 neutral，badge 顯「觀望」+ 撐/壓 中性版面，與 pill `⚪ 觀望` 一致。

---

## 三、影響範圍

### F1 — 建議 pill + 第五節客觀化（解核心 + P1-2 + P2-2）
- `modules/ai_analyzer_v2.py`：兩 `_decide_action` call site（`:1395`、`:1827`）`status` 改恆為 `'watch'`（持有改走客觀路徑）
- `app.py`：移除標頭 `adjust_pill_for_deep_loss` 疊加（`:190-193`，A 法）
- **不動**：`_decide_action` HOLD 分支（`:831-856`）保留為死碼/留待 §6 未來重用、保既有測試綠；`adjust_pill_for_deep_loss` 函式保留定義；第六節觸發鏈（`is_holding` prompt 注入 `:1551` + `_strip_section_six:1755`）；COST/QTY/P-L 列；`_render_operation_framework` 結構
- 測試：`tests/test_objective_action_decouple.py` 新檔
  - 持股 long 在 entry_zone → 標頭 pill = `🟢 進場區可佈`（非 `🟢 加碼`）
  - 持股 short 價跌穿放空區 → 標頭 pill = `🟡 等反彈佈空`（非 `🔴 出場`）
  - 深虧持股（-43%）→ 標頭 pill 客觀不被覆寫（移除 adjust 疊加後）
  - `is_holding=True` 仍輸出第六節（回歸不退化）

### F2 — P1-1 short 標頭空標
- `app.py:169`：short 空標 `a.support_price` → `a.target_price`，加 guard：None 或 ≥ 現價 → 不顯示
- 測試（併入 F1 新檔或 `test_print_report` 擴充）：short 現價 < range_low → 空標取下行目標（< 現價）；target_price ≥ price → 該 pill 不出現

### F3 — P2-1 方向 badge 與 pill 同源
- `app.py:156-184`：phase 反推 long/short 但 `entry_low` 與 `entry_high` 皆 None → badge 走 neutral（「觀望」+ 撐/壓），與 pill ⚪ 觀望 一致
- 測試：phase=再積累 + entry_low/high 皆 None（采鈺風格）→ badge='觀望'；正常 long（entry 有值）→ badge='多' 不退化

### 不動
- `calc_swing_levels` / `calc_pnf_target` 簽名與邏輯
- 第六節 AI 模板與 user-agnostic 性質
- DB schema（零 migration）
- prompt 結構（is_holding 注入維持只觸發 §6）
- dashboard.js（讀 DB 既存 action_pill，F1 分析時客觀化後自動生效）

---

## 四、為什麼這樣設計

### 1. status 恆 'watch' 而非刪 HOLD 分支
最小改動 + 可逆：改 call site 一行 ×2，revert 即還原；HOLD 分支與其測試保持綠，未來若 §6 想複用其判斷邏輯可直接取用。

### 2. deep-loss 採 A 法（不另做個人化標頭覆寫）
標頭要對所有讀者一致，個人化覆寫與此衝突。第六節 user-agnostic 無法承載個人損益，硬塞會回退 §二十八 跨用戶污染。-43% 損益已由 P/L 列紅字顯示，加第六節結構建議，足以提醒，符合用戶 Q2「§6 不動、只把建議客觀化」。日後不足再評估 B 法（§6 旁新增 read-time 個人小字）。

### 3. P1-1 改用 target_pnf 而非 support_price
`target_pnf` 對 short = `pnf_short`（`:1349`）= calc_pnf_target 幾何鏡像下行目標，恆在價下，且 = 第四節「P&F概念目標」同源 → 標頭/四節對齊。`support_price`（range_low）在跳空跌破時滯留價上，是反向 bug 來源。（註：第五節空標用 `sl.target`，與 `target_pnf` 可能因 lookback 微差，屬既有 §5-vs-四節小不一致，本輪不擴大；本 bug 的明顯錯誤是「空標在價上」，改 target_pnf 即解。）

### 4. P2-1 沿用 dashboard entry-None 判據而非加 direction 欄位
零 migration、與已上線的 §三十五 Bug-B dashboard 修法同判據，前後端一致。代價：極端「long 但 swing 算不出 entry」會被當 neutral，但該情境本就無可操作錨點，標觀望合理。robust 替代（新增 nullable `direction` 欄位持久化 AI 真實方向）列為日後選項，本輪不採。

---

## 五、回滾

3 組純加性 / 一行改動，各自獨立 `git revert`：
- F1 revert → 標頭恢復 hold/watch 雙字典 + deep-loss 疊加（創惟/晶心科矛盾復現）
- F2 revert → short 空標恢復 range_low（跳空時又顯示價上目標）
- F3 revert → 方向 badge 恢復純相位反推（采鈺又顯「多」）

F1 為行為主軸（持股報表標頭字變），但純客觀化、不碰 §6 與 RISK，風險集中且可逆。
