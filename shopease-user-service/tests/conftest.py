import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("JWT_SECRET_KEY", "user-service-test-signing-secret-32-bytes-minimum")
os.environ.setdefault("MYSQL_DATABASE", "shopease_user_db")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_authenticated_user_id
from app.database.connection import Base, get_db
from app.main import app
from app.models import Address, UserProfile
from app.core.security import verify_access_token
from jose import jwt
from app.core.config import settings

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_authenticated_user_id] = lambda: 101
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def make_token(user_id=101, secret=None):
    issued_at = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": "customer",
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=10),
        },
        secret or settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
