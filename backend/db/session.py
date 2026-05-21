from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.config import settings

# Must replace postgresql:// with postgresql+psycopg2:// if needed,
# but Supabase connection string is typically postgresql://, SQLAlchemy handles it or we can replace it.
DB_URL = settings.database_url
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

BUREAU_DB_URL = settings.bureau_database_url
if BUREAU_DB_URL.startswith("postgres://"):
    BUREAU_DB_URL = BUREAU_DB_URL.replace("postgres://", "postgresql://", 1)
if BUREAU_DB_URL.startswith("postgresql://"):
    BUREAU_DB_URL = BUREAU_DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DB_URL, pool_size=5, max_overflow=10, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

bureau_engine = create_engine(BUREAU_DB_URL, pool_size=5, max_overflow=10, pool_recycle=1800)
BureauSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bureau_engine)


class Base(DeclarativeBase):
    pass


class BureauBase(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_bureau_db():
    db = BureauSessionLocal()
    try:
        yield db
    finally:
        db.close()
