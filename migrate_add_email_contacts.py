"""一次性 migration：新增 email_contacts 表（分享報表收件人記憶）。"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from modules.database import engine, Base
from modules.models import EmailContact  # noqa: F401  load model into Base.metadata

Base.metadata.create_all(bind=engine, tables=[EmailContact.__table__])
print("[OK] email_contacts 表已建立（IF NOT EXISTS）")
