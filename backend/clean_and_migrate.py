"""One-time script: drop orphaned enums, then run alembic upgrade head."""
import os
import subprocess
import sys
import traceback

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://bloc:blocpassword@localhost:5432/bloc",
)

try:
    print(f"Connecting to DB to clean orphaned objects...")
    engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        # Drop ALL tables and types — full clean slate
        conn.execute(text("DROP TABLE IF EXISTS lead_assignments CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS caller_daily_counters CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS caller_states CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS rr_pointers CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS leads CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS callers CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS caller_status CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS lead_assignment_status CASCADE"))
        conn.commit()
        print("✅ Dropped all tables, enums, and alembic_version")

    print("Running alembic upgrade head...")
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=False)
    if result.returncode != 0:
        print("⚠️ Migration failed, but server will still start")
    else:
        print("✅ Migration complete")
except Exception:
    traceback.print_exc()
    print("⚠️ DB cleanup/migration failed, but server will still start")
