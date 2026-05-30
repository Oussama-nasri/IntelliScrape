import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://scraper:scraper@db:3306/scraper_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # reconnect on stale connections
    pool_recycle=1800,        # recycle connections every 30 min
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()