# ShopEase Microservices

This repository contains independent ShopEase services. They have separate
source trees, dependency manifests, runtime configuration, Docker networks,
and databases. No service imports another service's code or shares its
database. User validates Auth JWTs locally using an RS256 public key; only
Authentication has the private signing key.

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
├── shopease-product-catalog-service/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README.md
├── .gitignore
└── README.md
```

Each service README contains its own setup, API, and testing instructions.

## Service independence

| Service | Responsibility | Dependencies and data | Local URL |
|---|---|---|---|
| Authentication | Registration, login, and JWT-protected auth APIs | Its own `requirements.txt`, `.env`, Docker Compose configuration, and MySQL database | `http://localhost:8002/docs` |
| User | JWT-protected customer profiles, account status, and delivery addresses | Its own `requirements.txt`, `.env`, Docker Compose configuration, and MySQL database | `http://localhost:8004/docs` |
| Product | Product CRUD APIs | Its own `requirements.txt`; in-memory product data; no database | `http://localhost:8003/docs` |
| Product Catalog | JWT-protected product/category catalog, search, and transactional inventory management | Its own `requirements.txt`, `.env`, Docker Compose configuration, Alembic migrations, and MySQL database | `http://localhost:8005/docs` |

Install dependencies and run commands from the corresponding service directory.
Do not install multiple services' requirements into one shared virtual environment.
The auth and user Compose stacks each own a network, MySQL database, and
volume. Product has no database and keeps its product data in its own process
memory. User does not call Authentication: it verifies signed tokens locally
with the public key and cannot mint tokens. Auth or User database outages
remain local to their owning service. Product Catalog is separate from the
original Product Service, owns a third isolated MySQL database, and verifies
Auth JWTs locally with the Auth Service public key. See
`shopease-product-catalog-service/README.md` for setup and API details.

## Run a service independently

### Authentication Service

Configure `shopease-auth-service/.env`, then run:

```powershell
cd shopease-auth-service
docker compose up --build
```

Open `http://localhost:8002/docs`. The service-specific README documents local
Python setup and database migrations.

### User Management Service

Copy only Authentication's public key into `shopease-user-service/keys/`,
configure `shopease-user-service/.env`, then run:

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

### Product Catalog Service

Configure `shopease-product-catalog-service/.env` and provide the Auth
Service's public key path, then run:

```powershell
cd shopease-product-catalog-service
docker compose up --build
```

Open `http://localhost:8005/docs`. This service owns a separate MySQL database;
its Compose startup applies Alembic migrations before starting the API.

## Configuration and secrets

Each service owns its environment configuration. Real `.env` files and local
virtual environments are ignored by Git; `.env.example` files are intended for
sharing and must contain placeholders only. Never commit credentials, tokens,
or other secrets.

## Local screenshots

Keep the local `ShopEase_Screenshots.pdf` verification evidence in your
Downloads folder. The PDF is ignored by Git and is not included in the project.

## GitHub

The configured GitHub repository is
[github.com/Mlokeshnaidu/shopease-microservices](https://github.com/Mlokeshnaidu/shopease-microservices).
Clone it once, then work in the appropriate service folder. Keep changes to
each service within its own directory unless intentionally changing shared
repository documentation or ignore rules.
