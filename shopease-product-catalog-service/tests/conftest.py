import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_claims, require_admin
from app.database.connection import Base, get_db
from app.main import app
from app.models import Category, InventoryTransaction, Product  # noqa: F401

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    db = TestSession()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_claims] = lambda: {"sub": "25", "role": "customer"}
    app.dependency_overrides[require_admin] = lambda: {"sub": "1", "role": "admin"}
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
