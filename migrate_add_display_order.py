"""一次性 migration：為 stocks 表加上 display_order 欄位（自訂卡片排序用）。
NULL 預設值 = 未手動排過，後續以 COALESCE 排在最後（沿用原本 created_at 順序）。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from modules.database import engine

with engine.begin() as conn:
    conn.execute(text(
        "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS display_order INTEGER"
    ))
print("[OK] stocks.display_order 欄位已加入（IF NOT EXISTS）")
