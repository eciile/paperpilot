"""Shared pytest fixtures for PaperPilot tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from paperpilot.database import get_database_session
from paperpilot.main import app
from paperpilot.models import Base


@pytest.fixture
def database_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    test_engine.dispose()


@pytest.fixture
def client(
    database_session: Session,
) -> Generator[TestClient, None, None]:
    """Provide an API client using the isolated test database."""

    def get_test_session() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_database_session] = get_test_session

    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()