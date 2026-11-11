from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    create_access_token,
    load_private_key,
)
from app.models.user_model import User


def registration_payload(**overrides):
    return {
        "full_name": "Test Customer",
        "email": "customer@example.com",
        "password": "SecurePass9",
        "confirm_password": "SecurePass9",
        **overrides,
    }


def login_payload(**overrides):
    return {
        "email": "customer@example.com",
        "password": "SecurePass9",
        **overrides,
    }


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_credentials_error(response):
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_register_success_returns_only_public_fields(client, session_factory):
    response = client.post("/api/auth/register", json=registration_payload())

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"message", "id", "full_name", "email", "is_active"}
    assert body == {
        "message": "Registration successful.",
        "id": body["id"],
        "full_name": "Test Customer",
        "email": "customer@example.com",
        "is_active": True,
    }
    assert "password" not in response.text
    assert "password_hash" not in response.text
    assert "SecurePass9" not in response.text
    with session_factory() as db:
        stored_user = db.get(User, body["id"])
        assert stored_user is not None
        assert stored_user.password_hash != "SecurePass9"



def test_register_duplicate_email_returns_409(client):
    payload = registration_payload()
    assert client.post("/api/auth/register", json=payload).status_code == 201

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "An account with this email already exists."}


def test_register_invalid_email_returns_422(client):
    response = client.post(
        "/api/auth/register",
        json=registration_payload(email="not-an-email"),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "Test Customer", "email": "customer@example.com"},
        {"email": "customer@example.com", "password": "SecurePass9", "confirm_password": "SecurePass9"},
        {"full_name": "Test Customer", "password": "SecurePass9", "confirm_password": "SecurePass9"},
        {"full_name": "Test Customer", "email": "customer@example.com", "confirm_password": "SecurePass9"},
    ],
)
def test_register_missing_required_field_returns_422(client, payload):
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"


def test_register_password_mismatch_returns_422(client):
    response = client.post(
        "/api/auth/register",
        json=registration_payload(confirm_password="OtherPass9"),
    )

    assert response.status_code == 422
    assert "do not match" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("password", ["shortA1", "lowercase9", "UPPERCASE9", "NoDigitPass"])
def test_register_weak_password_returns_422(client, password):
    response = client.post(
        "/api/auth/register",
        json=registration_payload(password=password, confirm_password=password),
    )

    assert response.status_code == 422


def test_login_valid_credentials_returns_token_and_safe_user(client):
    client.post("/api/auth/register", json=registration_payload())

    response = client.post("/api/auth/login", json=login_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Login successful."
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert set(body["user"]) == {
        "id",
        "full_name",
        "email",
        "role",
        "is_active",
        "created_at",
    }
    assert body["user"]["role"] == "user"
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_login_incorrect_password_returns_401(client):
    client.post("/api/auth/register", json=registration_payload())

    response = client.post("/api/auth/login", json=login_payload(password="WrongPass9"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_unknown_email_returns_401(client):
    response = client.post("/api/auth/login", json=login_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


def test_login_inactive_user_returns_generic_401(client, user_factory):
    user_factory(is_active=False)

    response = client.post("/api/auth/login", json=login_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}
    assert response.headers["www-authenticate"] == "Bearer"


def signed_token(user_id: int, role: str, secret: str | None = None, expired: bool = False) -> str:
    now = datetime.now(timezone.utc)
    issued_at = now - timedelta(minutes=2) if expired else now
    expires_at = now - timedelta(minutes=1) if expired else now + timedelta(minutes=10)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": issued_at,
        "exp": expires_at,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    if secret:
        return jwt.encode(claims, secret, algorithm="HS256")
    return jwt.encode(claims, load_private_key(), algorithm=settings.jwt_algorithm)


@pytest.mark.parametrize("path", ["/api/auth/verify-token", "/api/auth/me"])
def test_protected_route_rejects_missing_token(client, path):
    response = client.post(path) if path.endswith("verify-token") else client.get(path)

    assert_credentials_error(response)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        signed_token(1, "user", secret="incorrect-signing-secret"),
        signed_token(1, "user", expired=True),
    ],
    ids=["invalid", "incorrect-signature", "expired"],
)
@pytest.mark.parametrize("path", ["/api/auth/verify-token", "/api/auth/me"])
def test_protected_routes_reject_invalid_tokens(client, path, token):
    response = (
        client.post(path, headers=bearer(token))
        if path.endswith("verify-token")
        else client.get(path, headers=bearer(token))
    )

    assert_credentials_error(response)


def test_verify_token_returns_validity_and_safe_user(client, user_factory):
    user = user_factory()
    token = create_access_token(user.id, user.role)

    response = client.post("/api/auth/verify-token", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["user"]["id"] == user.id
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_me_returns_authenticated_user_without_credentials(client, user_factory):
    user = user_factory()
    token = create_access_token(user.id, user.role)

    response = client.get("/api/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": True,
        "created_at": user.created_at.isoformat(),
    }
    assert "password_hash" not in response.text
    assert "password" not in response.text


def test_inactive_user_token_is_rejected(client, user_factory):
    user = user_factory(is_active=False)
    token = create_access_token(user.id, user.role)

    response = client.get("/api/auth/me", headers=bearer(token))

    assert_credentials_error(response)


def test_change_password_rejects_incorrect_current_password(client, user_factory):
    user = user_factory()
    token = create_access_token(user.id, user.role)

    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={
            "current_password": "WrongPass9",
            "new_password": "NewSecure8",
            "confirm_new_password": "NewSecure8",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is incorrect."}


def test_change_password_mismatched_confirmation_returns_422(client, user_factory):
    user = user_factory()
    token = create_access_token(user.id, user.role)

    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={
            "current_password": "SecurePass9",
            "new_password": "NewSecure8",
            "confirm_new_password": "Different8",
        },
    )

    assert response.status_code == 422


def test_change_password_updates_hash_and_changes_login_password(client, user_factory):
    user = user_factory()
    token = create_access_token(user.id, user.role)

    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={
            "current_password": "SecurePass9",
            "new_password": "NewSecure8",
            "confirm_new_password": "NewSecure8",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully."}
    assert "password" not in response.text
    assert "NewSecure8" not in response.text

    new_password_login = client.post(
        "/api/auth/login",
        json=login_payload(password="NewSecure8"),
    )
    assert new_password_login.status_code == 200

    old_password_login = client.post(
        "/api/auth/login",
        json=login_payload(password="SecurePass9"),
    )
    assert old_password_login.status_code == 401
    assert old_password_login.json() == {"detail": "Invalid email or password."}


def test_change_password_requires_authentication(client):
    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "SecurePass9",
            "new_password": "NewSecure8",
            "confirm_new_password": "NewSecure8",
        },
    )

    assert_credentials_error(response)


def test_swagger_openapi_uses_http_bearer_scheme(client):
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
