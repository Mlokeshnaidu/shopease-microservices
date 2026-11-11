from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings
from app.core.security import JWT_AUDIENCE, JWT_ISSUER
from app.core.dependencies import get_authenticated_user_id
from app.main import app
from conftest import _other_private_key_pem, _test_private_key_pem, make_token


PROFILE = {"full_name": "Asha Customer", "phone_number": "+1 415 555 0134"}
ADDRESS = {
    "address_type": "Home",
    "full_name": "Asha Customer",
    "phone_number": "+1 415 555 0134",
    "address_line_1": "42 Market Street",
    "address_line_2": "Apt 3",
    "city": "San Francisco",
    "state": "California",
    "country": "USA",
    "postal_code": "94105",
}


def test_missing_or_invalid_token_is_unauthorized():
    with TestClient(app) as client:
        assert client.get("/api/users/profile").status_code == 401
        assert client.get(
            "/api/users/profile", headers={"Authorization": "Bearer invalid"}
        ).status_code == 401
        wrong_secret = make_token(private_key=_other_private_key_pem)
        assert client.get(
            "/api/users/profile", headers={"Authorization": f"Bearer {wrong_secret}"}
        ).status_code == 401
        expired = jwt.encode(
            {
                "sub": "101",
                "role": "customer",
                "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                "iss": JWT_ISSUER,
                "aud": JWT_AUDIENCE,
            },
            _test_private_key_pem,
            algorithm=settings.jwt_algorithm,
        )
        assert client.get(
            "/api/users/profile", headers={"Authorization": f"Bearer {expired}"}
        ).status_code == 401


def test_valid_auth_service_token_identifies_user(client):
    app.dependency_overrides.pop(get_authenticated_user_id)
    token = make_token(user_id=333)
    response = client.post(
        "/api/users/profile",
        json=PROFILE,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["auth_user_id"] == 333


def test_profile_crud_and_local_deactivation(client):
    forged = client.post(
        "/api/users/profile",
        json={**PROFILE, "auth_user_id": 999},
    )
    assert forged.status_code == 422

    assert client.get("/api/users/profile").status_code == 404
    created = client.post("/api/users/profile", json=PROFILE)
    assert created.status_code == 201
    assert created.json()["auth_user_id"] == 101
    assert client.post("/api/users/profile", json=PROFILE).status_code == 409
    assert client.get("/api/users/profile").json()["full_name"] == "Asha Customer"

    updated = client.put(
        "/api/users/profile",
        json={**PROFILE, "full_name": "Asha Rao"},
    )
    assert updated.status_code == 200
    patched = client.patch("/api/users/profile", json={"gender": "Woman"})
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "Asha Rao"
    assert patched.json()["gender"] == "Woman"
    assert client.patch(
        "/api/users/profile", json={"phone_number": "not a phone"}
    ).status_code == 422

    deactivated = client.post("/api/users/account/deactivate")
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/users/profile").status_code == 403


def test_addresses_are_owned_and_only_one_is_default(client):
    assert client.post("/api/users/profile", json=PROFILE).status_code == 201
    first = client.post(
        "/api/users/addresses", json={**ADDRESS, "is_default": True}
    )
    second = client.post(
        "/api/users/addresses",
        json={**ADDRESS, "address_line_1": "50 Pine Street"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert len(client.get("/api/users/addresses").json()) == 2
    assert client.get(f"/api/users/addresses/{second.json()['id']}").status_code == 200

    updated = client.put(
        f"/api/users/addresses/{second.json()['id']}",
        json={**ADDRESS, "address_line_1": "50 Pine Street"},
    )
    assert updated.status_code == 200
    set_default = client.patch(f"/api/users/addresses/{second.json()['id']}/default")
    assert set_default.status_code == 200
    addresses = client.get("/api/users/addresses").json()
    assert sum(address["is_default"] for address in addresses) == 1
    assert next(address for address in addresses if address["is_default"])["id"] == second.json()["id"]

    app.dependency_overrides[get_authenticated_user_id] = lambda: 202
    assert client.get("/api/users/profile").status_code == 404
    other_profile = client.post("/api/users/profile", json=PROFILE)
    assert other_profile.status_code == 201
    assert other_profile.json()["auth_user_id"] == 202
    assert client.get("/api/users/profile").json()["auth_user_id"] == 202
    assert client.get(f"/api/users/addresses/{first.json()['id']}").status_code == 403
    assert client.put(
        f"/api/users/addresses/{first.json()['id']}",
        json={**ADDRESS, "is_default": True},
    ).status_code == 403
    assert client.delete(f"/api/users/addresses/{first.json()['id']}").status_code == 403
    assert client.patch(
        f"/api/users/addresses/{first.json()['id']}/default"
    ).status_code == 403
    app.dependency_overrides[get_authenticated_user_id] = lambda: 101
    assert client.delete(f"/api/users/addresses/{first.json()['id']}").status_code == 204
    assert client.get("/api/users/addresses/9999").status_code == 404


def test_address_requires_valid_mandatory_fields(client):
    assert client.post("/api/users/profile", json=PROFILE).status_code == 201
    invalid = {**ADDRESS, "phone_number": "bad", "city": ""}
    assert client.post("/api/users/addresses", json=invalid).status_code == 422
    forged_owner = {**ADDRESS, "user_id": 999}
    assert client.post("/api/users/addresses", json=forged_owner).status_code == 422


def test_new_default_address_replaces_previous_default(client):
    assert client.post("/api/users/profile", json=PROFILE).status_code == 201
    first = client.post(
        "/api/users/addresses", json={**ADDRESS, "is_default": True}
    )
    second = client.post(
        "/api/users/addresses",
        json={**ADDRESS, "address_line_1": "50 Pine Street", "is_default": True},
    )
    assert first.status_code == second.status_code == 201
    addresses = client.get("/api/users/addresses").json()
    assert len(addresses) == 2
    assert sum(address["is_default"] for address in addresses) == 1
    assert next(address for address in addresses if address["is_default"])["id"] == second.json()["id"]


def test_delete_profile_removes_profile_and_addresses_only(client):
    assert client.post("/api/users/profile", json=PROFILE).status_code == 201
    address = client.post("/api/users/addresses", json=ADDRESS)
    assert address.status_code == 201

    deleted = client.delete("/api/users/profile")
    assert deleted.status_code == 204
    assert client.get("/api/users/profile").status_code == 404
    assert client.get(f"/api/users/addresses/{address.json()['id']}").status_code == 404
    assert client.post("/api/users/profile", json=PROFILE).status_code == 201
