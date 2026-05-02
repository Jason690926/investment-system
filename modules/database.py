from urllib.parse import quote_plus
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

class Base(DeclarativeBase):
    pass

def get_database_url():
    password = quote_plus(os.getenv('SUPABASE_DB_PASSWORD', ''))
    host = os.getenv('SUPABASE_DB_HOST', '')
    user = os.getenv('SUPABASE_DB_USER', 'postgres')
    name = os.getenv('SUPABASE_DB_NAME', 'postgres')
    port = os.getenv('SUPABASE_DB_PORT', '5432')
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from modules.models import User, Stock, Trade, StockAnalysis
    Base.metadata.create_all(bind=engine)
    print("[DB] 資料庫初始化完成")
