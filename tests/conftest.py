
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, SessionLocal
from app import models  # Register all ORM models


@pytest.fixture(autouse=True)
def isolated_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    original_bind = SessionLocal.kw.get("bind")
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        SessionLocal.configure(bind=original_bind)
        engine.dispose()
