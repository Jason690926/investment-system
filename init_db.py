"""執行一次：建立所有資料庫資料表"""
from modules.database import init_db, engine
from sqlalchemy import text

if __name__ == '__main__':
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
        print("[DB] Supabase 連線成功")
    init_db()
