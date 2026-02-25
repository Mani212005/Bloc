"""One-time script: drop orphaned enums, then run alembic upgrade head."""
import os
import subprocess
import sys

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://bloc:blocpassword@localhost:5432/bloc",
)

print(f"Connecting to DB to clean orphaned objects...")

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    conn.execute(text("DROP TYPE IF EXISTS caller_status CASCADE"))
    conn.execute(text("DROP TYPE IF EXISTS lead_assignment_status CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    conn.commit()
    print("✅ Dropped orphaned enums and alembic_version (if they existed)")

print("Running alembic upgrade head...")
result = subprocess.run(["alembic", "upgrade", "head"], capture_output=False)
sys.exit(result.returncode)
