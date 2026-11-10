# ShopEase Microservices

This repository contains independent ShopEase services. They have separate
source trees, dependency manifests, runtime configuration, and Docker
instructions. They do not import from, call, or share a database with each
other. No service-to-service connection is configured.

## Repository structure

```text
.
├── shopease-auth-service/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   └── README.md
├── shopease-product-service/
│   ├── app/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
├── .gitignore
└── README.md
```

Each service README contains its own setup, API, and testing instructions.

## Service independence

| Service | Responsibility | Dependencies and data | Local URL |
|---|---|---|---|
| Authentication | Registration, login, and JWT-protected auth APIs | Its own `requirements.txt`, `.env`, Docker Compose configuration, and MySQL database | `http://localhost:8002/docs` |
| User | JWT-protected customer profiles, account status, and delivery addresses | Its own `requirements.txt`, `.env`, Docker Compose configuration, and MySQL database; validates auth-issued JWTs using shared settings | `http://localhost:8004/docs` |
| Product | Product CRUD APIs | Its own `requirements.txt`; in-memory product data; no database | `http://localhost:8003/docs` |

Install dependencies and run commands from the corresponding service directory.
Do not install both services' requirements into one shared virtual environment.
The auth and user Compose stacks each own their network and MySQL database.
The User Service performs local JWT validation; configure its JWT key and
algorithm to match Authentication. The Product Service is not attached to
either database network.

## Run a service independently

### Authentication Service

Configure `shopease-auth-service/.env` using its `.env.example`, then run:

```powershell
cd shopease-auth-service
docker compose up --build
```

Open `http://localhost:8002/docs`. The service-specific README documents local
Python setup and database migrations.

### User Management Service

Configure `shopease-user-service/.env` from its `.env.example`, ensuring its
JWT settings match Authentication, then run:

```powershell
cd shopease-user-service
docker compose up --build
```

Open `http://localhost:8004/docs`. The service-specific README documents its
API, account deactivation behavior, and Alembic migrations.

### Product Service

From the monorepo root, build and run only the Product Service:

```powershell
docker build -t shopease-product-service .\shopease-product-service
docker run --rm --name shopease-product-container -p 8003:8003 shopease-product-service
```

Open `http://localhost:8003/docs`. Product records are held in memory and are
not shared with the Authentication Service.

## Configuration and secrets

Each service owns its environment configuration. Real `.env` files and local
virtual environments are ignored by Git; `.env.example` files are intended for
sharing and must contain placeholders only. Never commit credentials, tokens,
or other secrets.

## GitHub

The configured GitHub repository is
[github.com/Mlokeshnaidu/shopease-microservices](https://github.com/Mlokeshnaidu/shopease-microservices).
Clone it once, then work in the appropriate service folder. Keep changes to
each service within its own directory unless intentionally changing shared
repository documentation or ignore rules.
