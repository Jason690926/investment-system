# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-07 收工）

**所在週次：週5（進行中）**

**狀態：HEAD = `c4e07eb`（已 push origin/main）**

**本次（2026-05-07）進度 — K線型態識別 + 平日新聞報表：**
- ✅ `candlestick.py`：新增 `detect_from_bars()`（轉換 enriched data → DataFrame）；`_MULTI_CANDLE` 移至模組層級
- ✅ `ai_analyzer_v2.py`：`analyze_market_only()` 加入 rule-based 型態偵測（最多5個）並傳入 AI prompt；新增 `analyze_daily_news()` 產生今日新聞 + 明日方向 HTML；日K從20根擴至30根
- ✅ `models.py`：新增 `DailyMarketSummary`（每日財經新聞摘要）、`PatternHistory`（K線型態歷史 + return_3/5/10d 回填）
- ✅ `run_daily_report.py`：批次儲存型態至 `PatternHistory`；回填 return_3/5/10d（bisect O(log N)）；每日財經新聞摘要以 TW 時區存檔（修 TZ mismatch bug）
- ✅ `app.py` + `print_report.html`：週末顯示週報，平日顯示「§ NEWS · 今日財經新聞」
- ✅ 修 Windows cp950 emoji print 崩潰（✅/⚠ → [OK]/[!]）
- ✅ 批次成功跑完（16支全分析，新聞摘要已入 DB）

**先前未解（仍待）：**
- ⏳ 分享 PDF 寄送 timeout：`SSL/465: timed out`（Render → Gmail SMTP 不穩）
  - 決策：暫緩，改手動存 PDF 轉傳給親友
  - 已討論方案供日後參考：A. 換 Resend HTTP API（推薦） / B. Render Starter / C. 加 timeout

**下一步（按優先順序）：**
1. **測試 `/print-report`**：週四平日邏輯 → 確認「§ NEWS · 今日財經新聞」顯示正常
2. **K線型態歷史累積**：目前第一批資料已入 DB，待 1-2 個月後查看 return_3/5/10d 回填結果
3. 測試完成後清理遺留
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
4. 重新跑一次週報驗證 commit `c95d0dd` 修法（會燒 ~$0.20）
5. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB

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
