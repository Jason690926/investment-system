# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-03 收工）

**所在週次：週5（進行中）**

**本次進度：**
- ✅ 修復 bug：上櫃股名變英文（`.TW`/`.TWO` base 提取順序錯誤；4 處統一修正）
- ✅ Server 端 `add_stock` 強制以 `STOCK_NAMES` 覆寫 name（不信前端）
- ✅ `fix_stock_names.py` 一次性修 DB 既有英文名（已對 prod 執行）
- ✅ 新功能：dashboard 卡片拖拉排序（`display_order` + SortableJS，1 人手動模式 OK）
- ✅ 新功能：新增股票時輸入「股名」自動帶「代號」（`/api/market/search` + 下拉建議）
- ✅ 費用估算更新：1 人 × 18 支基準，每月 ~$15（含週報、PDF）
- ✅ 停用 GitHub Actions 自動排程（cron 註解、保留 workflow_dispatch）→ 改全手動
- ✅ 新功能：📧 分享 PDF 報表給朋友（`EmailContact` + html2pdf.js + SMTP，含收件人記憶）

**下一步（按優先順序）：**
1. 實測新功能（拖拉排序、name→code、分享 PDF）
2. 測試完成後清理遺留（測試中，勿提前修改）
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
3. （未做）「移除聯絡人」UI — v1 沒做，要刪要進 DB
4. Render Free → Starter 升級暫緩（1 人手動，Free 足夠）

**待確認：**
- 財經新聞來源（週報用，目前週報已轉手動所以非急迫）

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
