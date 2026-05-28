-- §三十三：StockAnalysis 加 entry_low / entry_high 欄位（spec 2026-05-28 §四 F1）
-- 上線到 Supabase 步驟：
-- 1. 進 Supabase Dashboard → SQL Editor
-- 2. 貼上以下 SQL 並執行（零 downtime，加欄位不鎖表）
-- 3. 驗證：SELECT column_name FROM information_schema.columns
--         WHERE table_name = 'stock_analyses'
--           AND column_name IN ('entry_low', 'entry_high');
--         預期 2 row

ALTER TABLE stock_analyses
  ADD COLUMN IF NOT EXISTS entry_low NUMERIC(10, 2);

ALTER TABLE stock_analyses
  ADD COLUMN IF NOT EXISTS entry_high NUMERIC(10, 2);

-- 用途：dashboard mini-card 錨點 strip「進 X-Y」顯示精確進場區間
-- 來源：ai_analyzer_v2 swing_levels['entry_zone'] = (range_low, mid) 拆寫
-- 強勢突破成立時被 §三十二 _breakout_overrides 覆寫為 (rh*0.97, rh)
-- 既有 row 保留 NULL（向後相容；前端 strip 顯示「—」不 crash）
