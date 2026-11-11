from collections.abc import Callable, Generator
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_test_key_directory = TemporaryDirectory()
_test_key_path = Path(_test_key_directory.name)
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
(_test_key_path / "jwt_private.pem").write_bytes(
    _test_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
(_test_key_path / "jwt_public.pem").write_bytes(
    _test_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)
os.environ["JWT_PRIVATE_KEY_FILE"] = str(_test_key_path / "jwt_private.pem")
os.environ["JWT_PUBLIC_KEY_FILE"] = str(_test_key_path / "jwt_public.pem")
os.environ["JWT_ALGORITHM"] = "RS256"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.user_model import User


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def session_factory(test_engine):
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture
def client(session_factory) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def user_factory(session_factory) -> Callable[..., User]:
    def create_user(
        *,
        email: str = "customer@example.com",
        password: str = "SecurePass9",
        full_name: str = "Test Customer",
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        with session_factory() as db:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user

    return create_user
