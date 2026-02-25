import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://bloc:blocpassword@localhost:5432/bloc",
)

# DEBUG: Print the URL being used (mask password for safety)
_debug_url = DATABASE_URL
if _debug_url and "@" in _debug_url:
    _prefix = _debug_url.split("://")[0] + "://"
    _after_at = _debug_url.split("@", 1)[1]
    print(f"DATABASE_URL BEING USED: {_prefix}***@{_after_at}")
else:
    print(f"DATABASE_URL BEING USED: {_debug_url}")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

