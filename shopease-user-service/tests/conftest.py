import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_test_key_directory = TemporaryDirectory()
_test_key_path = Path(_test_key_directory.name)
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_key_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
_other_private_key_pem = _other_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
(_test_key_path / "jwt_public.pem").write_bytes(
    _test_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)
os.environ["JWT_PUBLIC_KEY_FILE"] = str(_test_key_path / "jwt_public.pem")
os.environ["JWT_ALGORITHM"] = "RS256"
os.environ.setdefault("MYSQL_DATABASE", "shopease_user_db")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_authenticated_user_id
from app.database.connection import Base, get_db
from app.main import app
from app.models import Address, UserProfile
from jose import jwt
from app.core.config import settings
from app.core.security import JWT_AUDIENCE, JWT_ISSUER
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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


def make_token(user_id=101, private_key=None):
    issued_at = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role": "customer",
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=10),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(
        claims,
        private_key or _test_private_key_pem,
        algorithm=settings.jwt_algorithm,
    )
