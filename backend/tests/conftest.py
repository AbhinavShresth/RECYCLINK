import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.db.base import Base
from app.main import app
from app.models import Role, WasteCategory


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestingSession.begin() as session:
        session.add_all(
            [
                Role(code="USER", description="Standard user"),
                Role(code="RECYCLER", description="Recycler"),
                Role(code="ADMIN", description="Administrator"),
                WasteCategory(code="paper", display_name="Paper and cardboard"),
                WasteCategory(code="plastic", display_name="Plastic"),
            ]
        )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
