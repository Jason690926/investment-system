"""一次性 migration：新增 quote_cache 表（看板輕量行情快取）。"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from modules.database import engine, Base
from modules.models import QuoteCache  # noqa: F401  load model into Base.metadata

Base.metadata.create_all(bind=engine, tables=[QuoteCache.__table__])
print("[OK] quote_cache 表已建立（IF NOT EXISTS）")
