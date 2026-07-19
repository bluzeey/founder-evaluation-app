import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Convert legacy postgres:// URLs to SQLAlchemy-compatible postgresql+psycopg2://."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize_database_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://localhost:5432/founderos",
    )
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables. Useful for local dev; production should use Alembic."""
    logger.info("database.create_tables.start")
    Base.metadata.create_all(bind=engine)
    logger.info("database.create_tables.end")
