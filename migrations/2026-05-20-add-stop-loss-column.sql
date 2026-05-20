-- B1c：StockAnalysis 加 stop_loss 欄位（spec 2026-05-20 §三）
-- 上線到 Supabase 步驟：
-- 1. 進 Supabase Dashboard → SQL Editor
-- 2. 貼上以下 SQL 並執行（零 downtime，加欄位不鎖表）
-- 3. 驗證：SELECT column_name FROM information_schema.columns
--         WHERE table_name = 'stock_analyses' AND column_name = 'stop_loss';

ALTER TABLE stock_analyses
ADD COLUMN IF NOT EXISTS stop_loss NUMERIC(10, 2);

-- 用途：short 股的失效停損價（前高 × 1.03）
-- long / neutral 股此欄位為 NULL（向後相容）
-- 對應 pill：空停（short 顯示）；long 不用此欄位（撐/壓/目標已足夠）
