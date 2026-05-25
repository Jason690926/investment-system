"""一次性 migration：為 stock_analyses 表加上 action_pill 欄位（建議動作 pill 字串，plan §三十一）。
NULL 預設值 = 該分析是 §三十一 之前產生的，dashboard 卡片不顯示 action chip。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from modules.database import engine

with engine.begin() as conn:
    conn.execute(text(
        "ALTER TABLE stock_analyses ADD COLUMN IF NOT EXISTS action_pill VARCHAR(32)"
    ))
print("[OK] stock_analyses.action_pill 欄位已加入（IF NOT EXISTS）")
