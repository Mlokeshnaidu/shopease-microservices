from app.core.dependencies import get_current_claims, require_admin
from app.main import app


def _category(client, name="Electronics"):
    response = client.post(
        "/api/categories/",
        json={"name": name, "description": "Consumer electronics"},
    )
    assert response.status_code == 201
    return response.json()


def _product(client, category_id, **overrides):
    payload = {
        "category_id": category_id,
        "name": "Phone",
        "sku": "PHONE-001",
        "price": "499.99",
        "discount_price": "449.99",
        "stock_quantity": 5,
    }
    payload.update(overrides)
    return client.post("/api/products/", json=payload)


def test_category_uniqueness_and_products_prevent_category_deletion(client):
    category = _category(client)
    assert client.post("/api/categories/", json={"name": "Electronics"}).status_code == 409
    assert _product(client, category["id"]).status_code == 201

    deleted = client.delete(f"/api/categories/{category['id']}")
    assert deleted.status_code == 409


def test_product_validation_search_filters_and_pagination(client):
    category = _category(client)
    assert _product(client, category["id"]).status_code == 201
    assert _product(client, category["id"]).status_code == 409
    assert _product(client, 999, sku="PHONE-002").status_code == 400
    assert _product(client, category["id"], sku="PHONE-003", price="-1").status_code == 422

    response = client.get("/api/products/?search=PHONE&min_price=100&max_price=500&page=1&page_size=1")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["sku"] == "PHONE-001"

    assert client.get("/api/products/?min_price=500&max_price=100").status_code == 422
    assert client.get("/api/products/?sort_by=sku").status_code == 422


def test_listing_category_availability_sorting_and_pagination(client):
    category = _category(client)
    assert _product(
        client,
        category["id"],
        sku="PHONE-Z",
        name="Mobile device",
        price="30.00",
        discount_price=None,
        stock_quantity=2,
    ).status_code == 201
    assert _product(
        client,
        category["id"],
        sku="PHONE-A",
        name="Tablet",
        price="20.00",
        discount_price=None,
        stock_quantity=0,
    ).status_code == 201

    ascending = client.get(
        f"/api/products/?category_id={category['id']}&sort_by=price&sort_order=asc&page=1&page_size=1"
    ).json()
    assert ascending["total"] == 2
    assert ascending["items"][0]["sku"] == "PHONE-A"
    assert client.get("/api/products/?search=mobile").json()["total"] == 1
    assert client.get("/api/products/?available=true").json()["total"] == 1
    assert client.get("/api/products/?available=false").json()["total"] == 1


def test_inventory_updates_are_logged_and_negative_stock_is_rejected(client):
    category = _category(client)
    product = _product(client, category["id"]).json()
    path = f"/api/inventory/{product['id']}"

    stock_out = client.post(f"{path}/stock-out", json={"quantity": 2, "remarks": "Order"})
    assert stock_out.status_code == 200
    assert stock_out.json()["stock_quantity"] == 3

    insufficient = client.post(f"{path}/stock-out", json={"quantity": 4})
    assert insufficient.status_code == 409
    assert client.get(path).json()["stock_quantity"] == 3

    stock_in = client.post(f"{path}/stock-in", json={"quantity": 3})
    assert stock_in.json()["stock_quantity"] == 6
    history = client.get(f"{path}/history").json()
    assert [(entry["transaction_type"], entry["previous_stock"], entry["updated_stock"]) for entry in history] == [
        ("IN", 3, 6),
        ("OUT", 5, 3),
        ("IN", 0, 5),
    ]


def test_product_patch_stock_change_updates_inventory_history(client):
    category = _category(client)
    product = _product(client, category["id"]).json()
    response = client.patch(
        f"/api/products/{product['id']}",
        json={"brand": "ShopEase", "stock_quantity": 8},
    )
    assert response.status_code == 200
    assert response.json()["brand"] == "ShopEase"
    history = client.get(f"/api/inventory/{product['id']}/history").json()
    assert len(history) == 2
    assert history[0]["transaction_type"] == "IN"
    assert history[0]["previous_stock"] == 5
    assert history[0]["updated_stock"] == 8


def test_category_and_product_deactivation_hide_them_from_customer_listings(client):
    category = _category(client)
    product = _product(client, category["id"]).json()
    assert client.patch(f"/api/products/{product['id']}", json={"is_active": False}).status_code == 200
    assert client.get("/api/products/").json()["total"] == 0

    assert client.put(f"/api/categories/{category['id']}", json={"is_active": False}).status_code == 200
    assert client.get("/api/categories/").json() == []


def test_product_details_and_deactivation(client):
    category = _category(client)
    product = _product(client, category["id"]).json()
    assert client.get("/api/products/999").status_code == 404
    assert client.delete(f"/api/products/{product['id']}").status_code == 204
    assert client.get("/api/products/").json()["total"] == 0


def test_admin_routes_reject_customer_and_unauthenticated_requests(client):
    app.dependency_overrides.pop(require_admin)
    body = {"name": "Home"}

    customer_response = client.post("/api/categories/", json=body)
    assert customer_response.status_code == 403

    app.dependency_overrides.pop(get_current_claims)
    unauthenticated_response = client.post("/api/categories/", json=body)
    assert unauthenticated_response.status_code == 401
