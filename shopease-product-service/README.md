# ShopEase Product Service

A Product Management microservice for the ShopEase e-commerce system, built with FastAPI and run in Docker. It provides CRUD APIs for products using in-memory storage (data is lost when the container restarts).

## Technology Stack

Python 3.11+, FastAPI, Uvicorn, Pydantic, Docker, Swagger UI, Git/GitHub

## Project Structure

```
shopease-product-service/
├── app/
│   ├── main.py
│   ├── routers/product_routes.py
│   ├── schemas/product_schema.py
│   ├── models/product_model.py
│   ├── services/product_service.py
│   └── config/settings.py
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env
└── README.md
```

## Installation

```bash
git clone https://github.com/Mlokeshnaidu/shopease-microservices.git
cd shopease-microservices\shopease-product-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003
```

Open http://localhost:8003/docs

## Run with Docker

```bash
docker build -t shopease-product-service .
docker images
docker run -d --name shopease-product-container -p 8003:8003 shopease-product-service
docker ps
docker logs shopease-product-container
```

Open http://localhost:8003/docs

## API Endpoints

| Method | Endpoint | Description | Success | Errors |
|---|---|---|---|---|
| POST | `/api/products/` | Create a product | 201 | 422 |
| GET | `/api/products/` | List products (`category`, `skip`, `limit`) | 200 | 422 |
| GET | `/api/products/{product_id}` | Get a product | 200 | 404 |
| PUT | `/api/products/{product_id}` | Update a product | 200 | 404, 422 |
| DELETE | `/api/products/{product_id}` | Delete a product | 204 | 404 |

Example request body (create / update):

```json
{
  "name": "Wireless Mouse",
  "description": "Ergonomic mouse",
  "price": 799.99,
  "stock_quantity": 50,
  "category": "Electronics",
  "status": "Active"
}
```

Validation: `name` and `category` required and non-empty; `price` greater than 0; `stock_quantity` 0 or greater; `status` is `Active` or `Inactive`.

## Testing

Start the container, open http://localhost:8003/docs, and use **Try it out** on each endpoint. Tested scenarios (all passed inside Docker):

1. Create a product with valid data (201)
2. Create with empty name (422)
3. Create with negative price (422)
4. Create with negative stock (422)
5. Retrieve all products (200)
6. Retrieve by valid ID (200)
7. Retrieve by invalid ID (404)
8. Update a product (200)
9. Delete a product (204)
10. Retrieve the deleted product (404)
11. Filter by category (200)
12. Pagination with skip and limit (200)