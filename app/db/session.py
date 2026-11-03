from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# The imported application owns an existing SQLite database. Do not silently
# switch to a platform-provided DATABASE_URL simply because one is present.
DATABASE_URL = os.getenv("SHAKWA_DATABASE_URL", "sqlite:///./gov_complaints.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()