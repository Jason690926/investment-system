# Investment System — Claude 指引

## 工作流程
- **開工指令**：「繼續 investment-system 工作」→ 讀本檔「當前進度」區塊，給一段摘要，然後繼續
- **收工指令**：「先停這裡」→ 更新下方「當前進度」快照，再結束
- **架構決策**：討論完方案後，先更新 `plan.md`，再開始寫程式
- `plan.md` 只在需要查架構細節時才讀（節省 token）

## 當前進度（2026-05-03）

**所在週次：週5（進行中）**

**下一步（按優先順序）：**
1. 測試完成後清理遺留（測試中，勿提前修改）
   - 還原時間鎖 `< 0` → `< 15`、冷卻 `< 0` → `< 4 * 3600`（`app.py`）
   - 移除「🗑 清快取」按鈕（`dashboard.html`、`dashboard.js`、`app.py`）
2. ✅ 產業週報（每週六自動跑）— 已完成
3. ✅ PDF 匯出 — 已完成（Dashboard「⬇ PDF」→ /export/pdf）
4. ✅ Prompt Caching + max_tokens 優化 — 已完成（預估省 40-45% 費用）
5. Render Free → Starter 升級暫緩（目前 5 人以下，Free 方案足夠）

**待確認：**
- 財經新聞來源（計畫用 Google News RSS）
- 週報固定跑哪天（建議週六上午）

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
