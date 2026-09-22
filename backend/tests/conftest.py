import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEV_AUTH"] = "true"
os.environ["DEV_SESSION_SECRET"] = "test-secret-must-be-32-bytes-ok!"
os.environ["JOB_WORKER_ENABLED"] = "false"
os.environ["SKIP_MIGRATIONS"] = "true"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
# EmbeddingGemma (D70) has no "absent API key" state the way the old Gemini
# adapter did - without this, every test run would try to load a real
# 300M-param model (gated HF download, needs HF_TOKEN, needs network).
os.environ["EMBEDDINGS_ENABLED"] = "false"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import get_session
from app.main import app
from app.models import Base

get_settings.cache_clear()

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)


def _session() -> Generator[Session, None, None]:
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_session] = _session


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Direct DB access for tests that assert on rows the API doesn't expose."""
    yield from _session()
