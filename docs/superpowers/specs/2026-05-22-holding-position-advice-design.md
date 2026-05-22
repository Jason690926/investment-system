# 優化1 — 虧損持股 neutral 時報表自動附「持倉部位建議」：設計

- 日期：2026-05-22
- 觸發：用戶 5/21 報表，晶心科（持股、虧 -35.2%、DIRECTION=neutral）§HOLDINGS
  分析只有「五、操作框架」寫「區間 224.5~260 不操作」，對套牢 35% 的持有人
  缺乏明確部位處理指引。
- 對應 plan：§二十八（待寫）

---

## 一、問題陳述

報表 §HOLDINGS 每股的五節分析（一威科夫～五操作框架）由 `analyze_market_only`
產生。`analyze_market_only` **不接收持股狀態**（簽章只有 name/symbol/
enriched_data/news_list），因此：

- 它產出的是「持股無關」的市場分析，五、操作框架 對 neutral 一律輸出
  「翻多條件/翻空條件/區間（區間內不操作）」。
- 對「已持有且虧損」的人，「不操作」不是建議 —— 他需要的是：續抱還是減碼？
  什麼價位該出場停損？

持倉部位建議目前只存在於 `generate_personal_recommendation`（手動點「個人建議」
才產生，且 `持倉診斷（方向衝突警示）` 模板僅 `_direction=='short' and
status=='holding'` 才觸發）。**未點個人建議的持股，報表完全沒有部位指引。**

## 二、影響範圍

- `analyze_market_only`（modules/ai_analyzer_v2.py）— 簽章 + prompt。
- 呼叫端：`app.py:693 api_analyze_stock`（有 `stock` 物件，含 status/avg_cost/
  trades）、`run_daily_report.py:117`（批次，須確認可取得持股狀態）。
- 不動 `generate_personal_recommendation`（個人建議仍是更詳盡的手動版）。

## 三、修法設計

### 決策 1：`analyze_market_only` 加 optional `holding_ctx` 參數

```
analyze_market_only(name, symbol, enriched_data, news_list=None,
                    holding_ctx: dict | None = None)
```
`holding_ctx`（None=觀察股/不注入）：
```
{'avg_cost': float, 'pnl_pct': float, 'qty_zhang': float}
```
向後相容：預設 None，觀察股與既有呼叫不受影響。

### 決策 2：holding 時 prompt 末段加「六、持倉部位建議」

僅當 `holding_ctx` 非 None 時，prompt 在「五、操作框架」後追加一節，強制
schema 輸出 3 個 bullet（無論 DIRECTION 為 long/short/neutral 都輸出）：

```
### 六、持倉部位建議（你目前持有此股，成本 {avg_cost}、損益 {pnl_pct}）
<ul>
  <li>▶ 整體判斷：（只選一個）續抱 / 減碼 / 出場 / 觀望持有 — 理由（≤40字）</li>
  <li>▶ 部位處理觸發價：跌破 [失效/翻空價] 元減碼；
       [方向對應的反轉/續抱條件價] 元為續抱或加碼依據</li>
  <li><span class="stop-loss">▶ 持倉停損：[失效價] 元 — 跌破請執行</span></li>
</ul>
```
- 價位一律引用上方已注入的【波段操作錨點】鎖定值（與五、操作框架同源，不另算）。
- neutral 持股：即使五、操作框架說「區間不操作」，六、仍須給「續抱條件 vs
  減碼觸發」具體價位 —— 這正是優化1 的核心訴求。
- 維持「模擬分析，不構成投資建議」免責語意（schema 用中性詞，不命令買賣）。

### 決策 3：呼叫端傳入 holding_ctx

- `api_analyze_stock`：`stock.status=='holding'` 時組 holding_ctx（avg_cost、
  以最新 quote 算 pnl_pct）。
- `run_daily_report.py`：批次迴圈確認可取持股 avg_cost；可取則傳，否則 None。

### 決策 4：與 generate_personal_recommendation 不重複

報表 §HOLDINGS 的「六、持倉部位建議」= 精簡 3-bullet，每份報表都有；
`generate_personal_recommendation` = 手動點、更詳盡（持倉診斷+減碼計劃+盤面提醒）。
兩者層級不同、不衝突；六、是「報表必有的最低保障」。

## 四、測試計畫

- `analyze_market_only` 為 AI 呼叫，無法純單測 prompt 行為 → 測「prompt
  組裝」：抽 prompt 組裝為可測點或斷言 holding_ctx 非 None 時 prompt 含
  「六、持倉部位建議」字串、為 None 時不含。
- 呼叫端：`holding_ctx` 組裝（pnl_pct 計算）可加純函式測試。
- 既有測試零退化。

## 五、風險與回滾

- 純加性：新 optional 參數 + holding 才注入的新 prompt 段；觀察股/既有呼叫
  byte-identical。單 commit 可 revert。
- ⚠️ prompt 行為改動，需 deploy + 重跑驗證 AI 是否照 schema 輸出六節。

## 六、驗收

1. pytest 全綠 + py_compile。
2. Deploy 後重跑：持股（晶心科/創惟）報表出現「六、持倉部位建議」3 bullet；
   neutral 持股也有具體續抱/減碼價位；觀察股無此節（向後相容）。

---

## 七、實作修正（2026-05-22，實作時發現）

**spec 原決策 1 的漏洞**：原設計 `holding_ctx` dict 帶 `avg_cost`/`pnl_pct`
注入 prompt。但 `StockAnalysis` **跨用戶共用**（一 symbol 一 row、無 user_id），
把個人成本/損益寫進 `html_content` 會洩漏給其他看同股的用戶（多用戶情境）。

**修正**：
- 參數由 `holding_ctx: dict` 改為 `is_holding: bool`（純旗標，不帶個人數字）。
- 第六節為 **user-agnostic 結構建議**：續抱/減碼判斷（依結構/相位）+ 錨點觸發價
  + 持倉停損 —— 全部與持有人是誰無關，可安全放入共用 row。
- 仍完整解決「neutral 持股缺部位建議」：持有人得到具體續抱/減碼價位，
  只是不含「你已虧 X%」這類個人化措辭（屬可接受取捨）。
- `run_daily_report` 批次：因跨用戶，只要任一用戶持有該股即注入第六節。

cost/pnl 感知的個人化建議仍由 `generate_personal_recommendation`（per-user
`PersonalRecommendation` 表）負責，與本節不衝突。
