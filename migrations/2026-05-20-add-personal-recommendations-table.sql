-- A 組：PersonalRecommendation cache 表（spec 2026-05-20 §四 Commit 6）
-- 上線到 Supabase 步驟：
-- 1. 進 Supabase Dashboard → SQL Editor
-- 2. 貼上以下 SQL 並執行（零 downtime，CREATE TABLE 不影響既有表）
-- 3. 驗證：SELECT * FROM personal_recommendations LIMIT 1;

CREATE TABLE IF NOT EXISTS personal_recommendations (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    symbol          VARCHAR(32) NOT NULL,
    analysis_date   DATE NOT NULL,
    html            TEXT NOT NULL,
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_personal_recommendation
        UNIQUE (user_id, symbol, analysis_date)
);

-- 用途：個人化操作建議 cache，避免 print PDF 重複呼叫 Claude
-- 寫入：dashboard「個人建議」按鈕 → /api/recommend-stock 觸發
-- 讀取：print_report 渲染時讀 today's 對應 (user, symbol)
-- 沒有 cache 則該股 personal 段 skip（不阻塞印表）
