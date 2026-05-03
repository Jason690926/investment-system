"""一次性修正：把 DB 既有 watchlist 內被寫成英文（或其他不正確值）的股名，
依 modules/stock_names.py 對照表刷新為正確中文名。
僅更新「對照表查得到、且與對照表實質不符」的紀錄；其餘保持不動。

註：對照表中部分股名帶 `*`（TWSE 注意股/處置股標記），使用者通常存乾淨版，
故比對時去除 `*` 再判斷，避免把所有股名都加上 `*`。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from modules.database import SessionLocal
from modules.models import Stock
from modules.stock_names import STOCK_NAMES

def _norm(s: str) -> str:
    return (s or '').replace('*', '').strip()

db = SessionLocal()
try:
    rows = db.query(Stock).all()
    fixed = 0
    skipped_no_match = 0
    already_correct = 0
    for s in rows:
        base = s.symbol.replace('.TW', '').replace('.TWO', '')
        correct = STOCK_NAMES.get(base)
        if not correct:
            skipped_no_match += 1
            continue
        if _norm(s.name) == _norm(correct):
            already_correct += 1
            continue
        print(f"修正 {s.symbol}: '{s.name}' -> '{correct}'")
        s.name = correct
        fixed += 1

    if fixed:
        db.commit()
        print(f"\n[OK] 已修正 {fixed} 筆 / 已正確 {already_correct} / 對照表查無 {skipped_no_match}")
    else:
        print(f"\n[INFO] 無需修正（已正確 {already_correct} / 對照表查無 {skipped_no_match}）")
finally:
    db.close()
