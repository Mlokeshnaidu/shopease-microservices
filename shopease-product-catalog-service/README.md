# ShopEase Product Catalog Service

An independent FastAPI microservice for product and category management,
catalog search, and auditable stock operations. It uses its own MySQL database,
SQLAlchemy models, and Alembic migrations; it does not share the legacy
`shopease-product-service` data store or code.

## Technology

- Python 3.11, FastAPI, Pydantic v2
- MySQL 8, SQLAlchemy 2, Alembic
- RS256 JWT verification using the Authentication Service public key
- Docker Compose, Swagger UI, pytest

## Structure

```text
shopease-product-catalog-service/
├── app/
│   ├── core/                 # Environment settings and JWT authorization
│   ├── database/             # SQLAlchemy engine, Base, and request sessions
│   ├── models/               # Category, Product, InventoryTransaction
│   ├── routers/              # Product, category, inventory APIs
│   ├── schemas/              # Request validation and response schemas
│   └── services/             # Database business operations
├── alembic/                  # Migration environment and version scripts
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Database schema

The service owns the `shopease_product_catalog_db` database.

- `categories`: unique name, description, active state, timestamps.
- `products`: category FK, unique SKU, name, description, `DECIMAL(10,2)`
  price and discount, non-negative stock, image URL, brand, active state,
  timestamps.
- `inventory_transactions`: product FK, IN/OUT type, positive quantity,
  previous and updated stock, remarks, timestamp. Initial product stock and
  product updates that change stock are recorded here as well.

Products reference categories with `ON DELETE RESTRICT`. Category deletion
returns `409 Conflict` while any products reference it. Reassign or deactivate
the products before deleting the category. Product deletion is a soft delete
(`is_active=false`) so inventory history remains auditable.

## Configuration

Copy `.env.example` to `.env`, replace all placeholder passwords, and set
`JWT_PUBLIC_KEY_FILE` to the Authentication Service's RS256 public key PEM.
The catalog service only needs the public key; it never receives the private
signing key. Root `.gitignore` excludes `.env` and `keys/`.

| Variable | Purpose |
|---|---|
| `MYSQL_DATABASE` | Catalog database name |
| `MYSQL_USER`, `MYSQL_PASSWORD` | Dedicated MySQL application account |
| `MYSQL_ROOT_PASSWORD` | Local MySQL root password |
| `MYSQL_HOST`, `MYSQL_PORT` | Database connection (Compose uses `catalog-mysql:3306`) |
| `JWT_PUBLIC_KEY_FILE` | Auth Service public-key PEM; Compose mounts it as a secret |
| `JWT_ALGORITHM` | Must be `RS256` |
| `LOW_STOCK_THRESHOLD` | Default low-stock threshold, non-negative (default `10`) |

The verifier enforces the Auth Service's issuer (`shopease-auth-service`),
audience (`shopease-services`), signature, expiry, subject, and role claims.
Every endpoint requires a valid bearer JWT. Authenticated customers can view
active catalog products and categories. Only `admin`/`administrator` roles can
write catalog/category data, see inactive records, or access inventory
operations. Missing or invalid tokens receive `401`; insufficient permissions
receive `403`.

## Run with Docker Compose

From this directory, prepare `.env` and the public key, then start:

```powershell
Copy-Item .env.example .env
# Edit .env and provide real local values and the Auth Service public key path.
docker compose up --build
```

Compose starts the dedicated MySQL 8 database with a persistent named volume
and health check. It waits for the database, runs `alembic upgrade head`, then
starts the API on `http://localhost:8005`. Swagger UI is at
`http://localhost:8005/docs`.

For local development, create a Python 3.11 virtual environment and install
`requirements.txt`. Configure `.env` for a reachable MySQL database and run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8005
```

Migration commands (from this directory):

```powershell
alembic upgrade head
alembic current
alembic revision --autogenerate -m "describe schema change"
```

## API

All routes are prefixed with `/api`. Supply `Authorization: Bearer <access-token>`
for every request.

### Products

| Method | Path | Purpose | Authorization |
|---|---|---|---|
| POST | `/api/products/` | Create product | Admin |
| GET | `/api/products/` | Search/list, filters, pagination, sorting | Customer/Admin |
| GET | `/api/products/{product_id}` | Product details | Customer/Admin |
| PUT | `/api/products/{product_id}` | Replace product fields | Admin |
| PATCH | `/api/products/{product_id}` | Partially update product | Admin |
| DELETE | `/api/products/{product_id}` | Deactivate product (history retained) | Admin |

Product creation requires `category_id`, `name`, `sku`, and positive `price`.
Stock defaults to zero. SKU must be unique; a missing/inactive category is
rejected. Price and discount use decimal values, discount cannot exceed price,
and stock cannot be negative. Initial stock is written to inventory history.

Product listing supports:

```text
GET /api/products/?search=mobile
GET /api/products/?category_id=1
GET /api/products/?min_price=1000&max_price=5000
GET /api/products/?available=true
GET /api/products/?page=1&page_size=10
GET /api/products/?sort_by=price&sort_order=asc
```

`search` matches product name or SKU; `sort_by` is `name`, `price`, or
`created_at`; `sort_order` is `asc` or `desc`; page size is limited to 100.
Customer listings omit inactive products and products in inactive categories.
Admins can pass `include_inactive=true`.

### Categories

| Method | Path | Purpose | Authorization |
|---|---|---|---|
| POST | `/api/categories/` | Create category | Admin |
| GET | `/api/categories/` | List active categories | Customer/Admin |
| GET | `/api/categories/{category_id}` | Get category | Customer/Admin |
| PUT | `/api/categories/{category_id}` | Update name, description, or active state | Admin |
| DELETE | `/api/categories/{category_id}` | Delete if no products reference it | Admin |

Names are trimmed and unique. Admins may deactivate categories; inactive
categories are hidden from customer listings and cannot be assigned to new or
updated products.

### Inventory

| Method | Path | Purpose | Authorization |
|---|---|---|---|
| GET | `/api/inventory/{product_id}` | Get stock and availability | Admin |
| POST | `/api/inventory/{product_id}/stock-in` | Increase stock | Admin |
| POST | `/api/inventory/{product_id}/stock-out` | Decrease stock | Admin |
| GET | `/api/inventory/{product_id}/history` | List transactions | Admin |
| GET | `/api/inventory/low-stock` | List products below threshold | Admin |

Stock requests use `{"quantity": 3, "remarks": "Restock"}`. Quantity must be
positive; stock-out beyond available stock returns `409` without changing
stock. A database row lock serializes concurrent stock changes, and product
stock plus its history row commit or roll back together. The low-stock endpoint
uses `LOW_STOCK_THRESHOLD` by default; admins may set a non-negative
`threshold` query parameter.

## Testing

Run the isolated API tests from this directory:

```powershell
python -m pytest
```

Tests use SQLite in-memory and exercise validation, category/SKU conflicts,
search and filters, inventory stock changes and history, and customer-facing
active listing behavior. This verifies API logic but does not replace the
requested MySQL/Docker/Postman checks. Before release, also verify the Compose
stack, migrations, authenticated Swagger/Postman flows, Auth Service key
integration, and simultaneous stock requests against MySQL. Capture actual
Swagger/Postman results and share the required progress update/screenshots
through the team's designated Excel sheet and Teams group.
