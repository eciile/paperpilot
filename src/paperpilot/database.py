"""Database configuration for PaperPilot."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from paperpilot.models import Base
from collections.abc import Generator

DATABASE_URL = "sqlite:///./paperpilot.db"


def create_database_engine(
    database_url: str = DATABASE_URL,
) -> Engine:
    """Create a SQLAlchemy database engine."""
    connect_args: dict[str, object] = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        connect_args=connect_args,
    )


engine = create_database_engine()

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)

def get_database_session() -> Generator[Session, None, None]:
    """provide one database session for an API request"""
    with SessionLocal() as session:
        yield session

def initialize_database(
    database_engine: Engine = engine,
) -> None:
    """Create all PaperPilot database tables."""
    Base.metadata.create_all(database_engine)