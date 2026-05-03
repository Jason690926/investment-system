# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-03 第二次收工）

**所在週次：週5（進行中）**

**本次（接續上次後）進度：**
- ✅ 修 bug：8064（上櫃股）看板偶爾不顯示股價
  - 加 `QuoteCache` 表（OHLC + prev_close，跨 process 持久化）
  - 前端 `fetchQuoteWithRetry` 失敗 1.5 秒 retry 一次
  - 讀取順序：_quote_cache → QuoteCache → MarketDataCache → Yahoo
  - 對 prod DB 已 migrate
- ✅ 修 bug：週報只剩標題（AI markdown 包裝）+ 大盤週報空白（AI 寫巨大 CSS 被截斷、未閉合 `<style>` 吃掉內容）
  - `_clean_html_output` 加強：未閉合 `<style>/<head>/<script>` 也砍
  - 兩個週報函式 prompt 嚴禁輸出 `<head>/<style>` 等 document tag、嚴禁 markdown 包裝
  - 已對重跑後的壞記錄做兩次刪除 + 重跑（共燒 ~$0.4）
- ✅ CLAUDE.md 加入「**修改 AI 功能的紀律**」章節（避免下次再燒 token 試錯）
  - 規則：修 AI 相關 bug 前必先撈 DB 真實 raw 輸出在本機推演
- ✅ `/print-report` 加入大盤週報 + 產業指標股區塊（PDF 內容更完整）
- ⏳ 部分修：分享 PDF 寄送
  - 第一輪 `[Errno 101] Network is unreachable` → 已修（強制 IPv4 + 587/465 fallback）
  - 第二輪 `SSL/465: timed out` → **未解**（Render → Gmail SMTP 通信不穩）

**下一步（按優先順序）：**
1. **🔴 修 PDF 寄送 timeout**：選一條走（已討論完不需再評估）
   - A. 換 [Resend](https://resend.com) HTTP API（推薦；免費 100/日；改 ~30 行）
   - B. 升級 Render Starter ($7/月；不保證能解）
   - C. 加大 timeout 20s → 45s 試試（最低成本但賭運氣）
2. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
3. 實測拖拉排序、name→code 下拉建議
4. 測試完成後清理遺留（測試中，勿提前修改）
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
5. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB

**待確認：**
- 財經新聞來源（週報用；目前週報手動所以非急迫）

## 費用速查

| 情境 | 月費 |
|------|------|
| 個人使用（1人 × 18支）| 約 US$15（NT$480）|
| 對外收費建議 | NT$300/人/月 |
| 打平門檻 | 5-6人（5人接近打平，6人開始盈餘）|

詳細估算見 `plan.md` 第零節（每日 ~$0.64、每週含週報 ~$3.40）。

## 專案基本資訊
- GitHub：`https://github.com/Jason690926/investment-system`（私人）
- 部署：Render `https://investment-system-lxq5.onrender.com`
- 資料庫：PostgreSQL via Supabase
- 本機路徑：`C:\Users\frodo.MSI\OneDrive\Desktop\investment-system`

---

## 修改 AI 功能的紀律（避免燒 token）

修改會呼叫 Claude API 的程式碼前（週報產生、個股分析、產業指標股、市場分析等），必須在本機**用 DB 既有的真實 raw 輸出**完整推演 cleanup / prompt / 渲染管道，確認修法在實際資料上會 work，再讓使用者重跑。

**Why：** 每次週報重跑燒 ~$0.20、每次個股全分析燒 ~$0.6+。一輪「推測 → push → 使用者重跑 → 還是壞 → 再推測」就燒掉 $0.40+。1 人月預算才 $15，反覆燒會明顯吃掉預算且使用者體驗差。

**How to apply（修 AI 相關 bug 必做）：**
1. **先撈 DB 既有壞掉的 raw 輸出**（如 `WeeklyReport.html_market`、`StockAnalysis.html_content`）看實際內容，**不要憑想像**
2. **本機跑 cleanup / 渲染 pipeline 在那份真實壞資料上**驗證，確認修法 work
3. **覆蓋多種失敗情境**：完整輸出、截斷輸出、未閉合標籤、markdown 包裝等都要測
4. 如果只能用 AI 重跑才能驗證（如 prompt 改動），明確告知使用者「這次修法是基於分析、不確定 AI 會否規矩遵守，請評估是否值得花 ~$X 重跑」
5. 不確定就用「prompt + cleanup 雙保險」（prompt 約束根本面、cleanup 防禦邊界）— 不要只改其中一個就 push

---

## 前端設計原則

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration. This project uses a dark theme — keep it dark and extend it with character.

Motion: Use animations for effects and micro-interactions. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context.
</frontend_aesthetics>
