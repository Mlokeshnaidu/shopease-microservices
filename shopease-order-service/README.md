# ShopEase Order Service

Independent FastAPI order microservice. It owns its MySQL database and calls
the User Management and Product Catalog services through their HTTP APIs. It
does not copy user or product master records.

## Features

- RS256 JWT verification compatible with ShopEase Authentication.
- Customer-scoped order history and saved-address ownership checks.
- Server-side price, catalog discount, tax, shipping, and total calculations.
- Product name, SKU, price, discount, shipping address, and line-total snapshots.
- Atomic, idempotent stock reservation and release through the Product Catalog.
- Order history, order-number lookup, pagination, status/date filtering, and items.
- Administrator-only order/payment transitions and cancellation workflow.
- Separate MySQL database with Alembic migrations.

## Project structure

```text
shopease-order-service/
├── app/
│   ├── core/          # Settings, JWT verification, request dependencies
│   ├── database/      # SQLAlchemy engine and sessions
│   ├── models/        # Order and OrderItem
│   ├── routers/       # Order and item APIs
│   ├── schemas/       # Validated API requests and responses
│   ├── services/      # Order logic and User/Catalog HTTP clients
│   └── main.py
├── alembic/           # Migration environment and versions
├── tests/             # Unit and API integration tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Database schema

`orders` stores a unique `order_number`, JWT subject `user_id`, JSON
`shipping_address` snapshot, decimal subtotal/discount/shipping/tax/total,
order/payment/inventory statuses, notes, and timestamps.

`order_items` belongs to one order and stores the product ID only as a
reference, plus historical product name, SKU, unit price, quantity, discount,
total price, and creation time. No Product or User table is created in this
service.

## Authentication and service integrations

The service validates Auth-issued RS256 access tokens locally using only the
Auth Service public key. It checks issuer, audience, expiry, subject, and role.
User IDs are always taken from the verified JWT, never from the create-order
body. Missing or invalid tokens return 401. Customers can access only their
own orders; administrators (`admin` or `administrator`) can read all orders
and update order/payment statuses.

Order creation calls the User Service using the same bearer token to verify
the active profile and fetch the selected address. User Service address reads
are already scoped to the token owner; the Order Service also checks the
address's profile ID before persisting its JSON snapshot.

Product details, current list and discount prices, active state, SKU, and
available stock come from the Product Catalog API. The final stock check and
decrement happen in the Catalog database in one transaction. Inventory
reservation endpoints use a shared `X-Order-Service-Key` secret and are not
available to customer JWTs.

### Inventory consistency workflow

1. Validate the customer, address, products, prices, and requested quantities.
2. Save the order and items with inventory status `RESERVING`.
3. Ask the Catalog to reserve stock using the unique order number as the
   operation reference. Catalog locks products, checks all requested stock,
   decrements stock, writes its inventory audit entries, and records the
   reservation in one transaction.
4. On confirmation, mark the order `RESERVED` and return it.
5. If reserve fails, the Order Service sends an idempotent release using that
   same reference. If compensation succeeds, it removes the unplaced order.
   If Catalog is unavailable during compensation, the order is marked
   `CANCELLED` / `RELEASE_PENDING`; retry `POST /api/orders/{id}/cancel` to
   complete reconciliation.
6. Cancellation first persists `RELEASE_PENDING`, asks Catalog to release the
   reservation, then marks the order `CANCELLED` / `RELEASED`. Catalog records
   reservation state and restores stock in one transaction. Repeating release
   or cancellation returns the already-released state without adding stock a
   second time. If either service is unavailable, the pending local state is
   retained so the same operation can be safely retried.

The Order and Catalog databases do not share a transaction. The persisted
`inventory_status`, unique order reference, reservation table, and retryable
compensation are the saga/reconciliation mechanism. Failed reservation calls
are compensated before the API returns; incomplete compensations are surfaced
as 503 and remain visible to administrators for retry.

## Pricing rules

All amounts use `Decimal` and are rounded to two decimal places using
half-up rounding:

- `subtotal`: sum of catalog list price × quantity.
- Item discount: catalog list price minus current `discount_price`, multiplied
  by quantity; absent `discount_price` means no discount.
- `discount_amount`: sum of item discounts.
- `tax_amount`: `(subtotal - discount_amount) × TAX_RATE`.
- `shipping_charge`: configured fixed `DEFAULT_SHIPPING_CHARGE`.
- `total_amount`: `subtotal - discount_amount + tax_amount + shipping_charge`.

The client cannot submit price, discount, tax, shipping, or order total values.
The order item stores list price and discount separately so the price
calculation remains auditable after catalog changes.

## API

All endpoints require `Authorization: Bearer <access-token>` except where
noted. Swagger UI is available at `/docs`.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| POST | `/api/orders/` | Authenticated | Validate and create order; reserve stock |
| GET | `/api/orders/` | Authenticated | Paginated order history |
| GET | `/api/orders/{order_id}` | Owner/admin | Order and item snapshots |
| GET | `/api/orders/number/{order_number}` | Owner/admin | Lookup by order number |
| GET | `/api/orders/{order_id}/items` | Owner/admin | Order line items |
| POST | `/api/orders/{order_id}/cancel` | Owner/admin | Cancel eligible order and release stock |
| PATCH | `/api/orders/{order_id}/status` | Administrator | Apply allowed status/payment transition |

Create request example:

```json
{
  "items": [
    { "product_id": 1, "quantity": 2 },
    { "product_id": 3, "quantity": 1 }
  ],
  "shipping_address_id": 5,
  "notes": "Please deliver during evening hours"
}
```

`GET /api/orders/` accepts `page` (default 1), `page_size` (default 20, max
100), `status`, `created_after`, and `created_before`. It returns `items`,
`total`, `page`, and `page_size`. Invalid date ranges return 422.

### Order and payment transitions

Allowed order transitions:

- `PENDING` → `CONFIRMED` or `CANCELLED`
- `CONFIRMED` → `PROCESSING` or `CANCELLED`
- `PROCESSING` → `SHIPPED` or `CANCELLED`
- `SHIPPED` → `DELIVERED`
- `DELIVERED` and `CANCELLED` are terminal

Only the cancellation workflow can transition an order to `CANCELLED`, so
reserved stock is always released first. Customers can cancel their own
pending, confirmed, or processing orders; shipped/delivered orders cannot be
cancelled. A paid order must be cancelled by an administrator and marked
`REFUNDED` in the same status request.

Payment transitions are `PENDING` → `PAID` or `FAILED`, and `PAID` →
`REFUNDED`. Payment status is an administrative record; this service does not
process payments.

## Configuration

Copy `.env.example` to `.env`. Configure MySQL credentials, JWT public key
path, and both upstream URLs. Set the same strong, generated shared value for
`CATALOG_SERVICE_API_KEY` in this service and `ORDER_SERVICE_API_KEY` in
`shopease-product-catalog-service/.env`. Do not commit `.env` files or keys.
For example, generate a local value with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and copy it to
both ignored `.env` files.

In the separate Compose stacks, the Order container reaches the User and
Catalog API ports through `host.docker.internal` (`8004` and `8005`). Start
Authentication, User, and Product Catalog first. Product Catalog must have
the matching service key configured before stock reservations are enabled.

## Migrations

Run from this service directory with the database configured:

```powershell
alembic upgrade head
alembic current
alembic downgrade -1
```

Compose runs `alembic upgrade head` before starting Uvicorn.

## Run locally or with Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or, after configuring `.env` and the Catalog service key:

```powershell
docker compose up --build
```

The Compose stack runs the API on `http://localhost:8006` and a private MySQL
8 database with a named persistent volume and health check.

## Tests

Run `python -m pytest` from this directory. The tests cover JWT auth, ownership,
create/retrieve/list/status/cancel APIs, totals and discounts, stock checks,
inventory reservation compensation, and idempotent cancellation. Catalog
reservation API tests are in
`shopease-product-catalog-service/tests/test_catalog_api.py`.
