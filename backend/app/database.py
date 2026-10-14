from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# SQLite-specific connect_args
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def run_schema_migrations(target_engine=None):
    eng = target_engine or engine
    with eng.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE medications ADD COLUMN prescribed_dose_qty INTEGER DEFAULT 1"))
            conn.commit()
        except Exception:
            pass
        for col, col_type in [
            ("start_date", "TEXT"),
            ("end_date", "TEXT"),
            ("recurrence", "VARCHAR(30) DEFAULT 'daily'"),
            ("days_of_week", "VARCHAR(50) DEFAULT 'all'")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE schedules ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass
        for col, col_type in [
            ("needs_reconciliation", "BOOLEAN DEFAULT 0"),
            ("quarantine_reason", "TEXT")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE cartridges ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
