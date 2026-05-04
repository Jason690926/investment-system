# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-04 收工）

**所在週次：週5（進行中）**

**狀態：本次 10 個 commit 已 push origin/main（HEAD = `0ff235e`）**

**本次（2026-05-04）進度 — 持股 PDF 報表大改版：**
- ✅ 視覺改版：終端機印刷風（IBM Plex Mono/Sans + Noto Sans TC + 象牙紙 + 琥珀強調）
  - 脫離 Material Indigo 範本感、台股慣例紅漲綠跌、設計 token 抽到 `:root`
  - 章節結構：封面 → 大盤週報 → 產業指標股 → § HOLDINGS · 持股 → § WATCHLIST · 觀察 → 免責
- ✅ 修排序 bug：原本 `order_by(created_at)`，改成走 `display_order`（與 dashboard 一致）
  - 注意：`get_user_stocks` 回 dict 不是 ORM；route 直接 query Stock 並複製 service 的排序邏輯
- ✅ 新增當日收盤 + 漲跌百分比：批次撈 `QuoteCache`（不打 Yahoo）
- ✅ 拆 holdings vs watchlist 兩節：持有版多顯示 COST/QTY/P/L/RISK 數據列
- ✅ `_strip_inline_styles` render-time 防禦（防 DB 既有殘留蓋過 token）
- ✅ AI markdown 渲染：mistune 進 pipeline（`### → <h3>`、`- → <ul>`、`**bold**`）
- ✅ K 線表格緊縮：shrink-to-fit、tabular-nums、緊 padding、數字欄右對齊
- ✅ key-point 改 block-level callout（▶ 前綴、獨立橫條，不再 inline 半截話）
- ✅ 螢幕版加 `max-width:820px` 置中（瀏覽器預覽不再撐到 1920px；PDF 不受影響）
- ✅ pytest 骨架 + 28 cases 單元測試（`tests/test_print_report.py`）
- 📄 spec：`docs/superpowers/specs/2026-05-04-print-report-redesign-design.md`
- 📄 plan：`docs/superpowers/plans/2026-05-04-print-report-redesign.md`

**先前未解（仍待）：**
- ⏳ 分享 PDF 寄送 timeout：第二輪 `SSL/465: timed out`（Render → Gmail SMTP 不穩）
  - 已討論方案：A. 換 Resend HTTP API（推薦） / B. Render Starter / C. 加 timeout

**下一步（按優先順序）：**
1. **🔴 修 PDF 寄送 timeout**：A/B/C 擇一（前次討論結論未動工）
2. **K 線多日型態識別（第二輪 PDF 改版，會燒 token）**：
   - 改 prompt 讓 AI 識別十字星 / 黃昏之星 / 三白兵 / 烏雲罩頂 / 看漲/看跌吞噬 / 早晨之星
   - **估算：3-4 小時工時 + $13-15 token**（試點 5 支 ~$2-3 + 全跑 18 支 ~$11）
   - 流程：(a) 設計 + 列型態清單 30 分（$0）→ (b) 改 prompt + 本機驗證 1-2 hr（$0）→ (c) 試點 3-5 支 → (d) 看 PDF 微調（每輪 +$2-3）→ (e) 全跑 18 支 ~$11
   - 風險：AI 識別精度（臨界 case 可能誤判）、prompt 變長可能擠到 max_tokens（之前週報空白 bug 那種風險）
   - 開工建議：先做 (a)+(b) 0 成本，看本機推演滿不滿意再決定要不要燒 token 試點
3. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
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
