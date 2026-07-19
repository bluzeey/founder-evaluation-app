import os
import sys
from pathlib import Path

# Use the test database for all tests. Must be set before any backend module is imported.
os.environ["DATABASE_URL"] = "postgresql+psycopg2://postgres:founderos@localhost:5433/founderos_test"
os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["UMANS_API_KEY"] = "test-key"

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine, get_db
from main import app

# Ensure all tables exist in the test database.
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db():
    """Provide a fresh DB session for a test."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """Provide a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate all tables after each test to keep tests isolated."""
    yield
    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE claims, opportunities, score_snapshots, evidence_items, "
                "social_media_backgrounds, founder_pool_items, theses, founders CASCADE"
            )
        )
        db.commit()
    finally:
        db.close()
