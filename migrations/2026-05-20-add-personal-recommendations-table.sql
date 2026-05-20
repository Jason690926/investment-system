-- A 組：PersonalRecommendation cache 表（spec 2026-05-20 §四 Commit 6）
-- 上線到 Supabase 步驟：
-- 1. 進 Supabase Dashboard → SQL Editor
-- 2. **依序執行下面兩個 statement**（Supabase SQL Editor 對 inline CONSTRAINT
--    /UNIQUE 句法有時會 parse 失敗，故拆成 CREATE TABLE + CREATE UNIQUE
--    INDEX 兩段分別跑）
-- 3. 驗證：SELECT * FROM personal_recommendations LIMIT 1;（應 0 row 無錯）

-- Step 1：建表（去除 inline UNIQUE，最小可建）
CREATE TABLE IF NOT EXISTS personal_recommendations (
  id              SERIAL PRIMARY KEY,
  user_id         INTEGER NOT NULL,
  symbol          TEXT NOT NULL,
  analysis_date   DATE NOT NULL,
  html            TEXT NOT NULL,
  generated_at    TIMESTAMP DEFAULT NOW()
);

-- Step 2：獨立加 UNIQUE index（保證 (user_id, symbol, analysis_date) 唯一）
CREATE UNIQUE INDEX IF NOT EXISTS uq_personal_rec_user_sym_date
  ON personal_recommendations (user_id, symbol, analysis_date);

-- 用途：個人化操作建議 cache，避免 print PDF 重複呼叫 Claude
-- 寫入：dashboard「個人建議」按鈕 → /api/recommend-stock 觸發
-- 讀取：print_report 渲染時讀 today's 對應 (user, symbol)
-- 沒有 cache 則該股 personal 段 skip（不阻塞印表）
