#!/usr/bin/env python3
"""
startup.py — Run this once to verify everything works before launching.
Usage:  python startup.py
Then:   uvicorn app.main:app --reload
"""

import sys
import os

# ── 1. Check .env ──────────────────────────────────────────────────────────
if not os.path.exists(".env"):
    print("❌ .env file not found. Copy .env.example → .env and fill it in.")
    sys.exit(1)

from app.config import settings
print(f"✅ Config loaded — APP_NAME={settings.APP_NAME}")
print(f"   DATABASE_URL = {settings.DATABASE_URL}")
print(f"   SMTP_USER    = {settings.SMTP_USER}")
print(f"   SMTP_PASSWORD set: {'YES ✓' if settings.SMTP_PASSWORD else 'NO — emails will be skipped in dev mode'}")

# ── 2. Test DB connection ──────────────────────────────────────────────────
from sqlalchemy import text
from app.database import engine, Base
import app.models  # noqa — registers all models

print("\n🔌 Testing database connection…")
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ Database connection OK")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("   Check DATABASE_URL in .env and ensure MySQL is running.")
    sys.exit(1)

# ── 3. Create tables ───────────────────────────────────────────────────────
print("\n🗄  Creating tables…")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created (or already exist):")
    for tbl in Base.metadata.tables.keys():
        print(f"   • {tbl}")
except Exception as e:
    print(f"❌ Table creation failed: {e}")
    sys.exit(1)

# ── 4. Done ────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("🚀 Everything looks good! Start the server with:")
print()
print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
print()
print("📖 API docs: http://localhost:8000/docs")
print("🖥  Streamlit: streamlit run frontend/otp_registration.py")
print("="*50)
