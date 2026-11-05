# ShopEase Authentication Microservice

Independent authentication service for the ShopEase e-commerce platform. It
provides account registration and login, JWT bearer authentication, profile
lookup, token verification, and password changes through a FastAPI API backed
by MySQL.

## Features

- Register users with validated email and password confirmation.
- Hash passwords with bcrypt; never persist plain-text passwords.
- Assign new public accounts the `user` role.
- Issue signed JWT access tokens with user ID, role, issue time, and expiration.
- Protect endpoints by validating the token and reloading the active user.
- Change passwords after verifying the current password.
- Store account data in MySQL and manage schema with Alembic migrations.
- Run as a non-root user in a Docker container.

## Technology stack

- Python 3.11
- FastAPI, Uvicorn, Pydantic v2, and Pydantic Settings
- SQLAlchemy 2.0 and PyMySQL
- Alembic
- Passlib with bcrypt; python-jose for JWTs
- MySQL 8
- Pytest and FastAPI TestClient
- Docker and Docker Compose

## Project structure

```text
shopease-auth-service/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── connection.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── user_model.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── auth_routes.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth_schema.py
│   └── services/
│       ├── __init__.py
│       └── auth_service.py
├── alembic/
│   ├── script.py.mako
│   ├── env.py
│   ├── versions/
│   │   └── 20261105_01_create_users.py
├── tests/
│   ├── conftest.py
│   └── test_auth_routes.py
├── .dockerignore
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Local setup

Requires Python 3.11+ and a reachable MySQL 8 instance. Run commands from the
service root.

### Create a virtual environment and install dependencies

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configure environment

Create your local environment file from the template:

```powershell
Copy-Item .env.example .env
```

Set `MYSQL_HOST=localhost` for a local MySQL server and configure the user,
password, database, and JWT secret in `.env`. The settings use
`DATABASE_URL` when it is supplied; if left blank, the service builds a
`mysql+pymysql` URL from the MySQL settings. The Docker Compose service
overrides the host with `auth-mysql`.

Generate a secret using the Python cryptographic random-number generator:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Generate distinct values for `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, and
`JWT_SECRET_KEY`. Keep `.env` out of source control and never log or return
secrets. Use a secret manager for deployed environments.

### Run migrations and start the API

With the configured database reachable:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The migration command creates or updates the schema before the API starts.
For model changes, generate a migration, review it, then apply it:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

`alembic downgrade -1` rolls back one revision. Alembic owns schema changes;
`Base.metadata.create_all()` is not used as a migration substitute.

## Docker

Set the MySQL and JWT credentials in `.env`, then build and start both
containers:

```powershell
docker compose up --build
```

Compose starts MySQL 8 (`auth-mysql`) on a private bridge network, waits for
its health check, runs `alembic upgrade head`, then starts Uvicorn inside the
API container on port `8000`. MySQL data persists in the named
`auth-mysql-data` volume. The current Compose mapping publishes the API at
http://localhost:8002 because host port 8000 was occupied during validation.
If port 8000 is free on your machine, change the mapping in
`docker-compose.yml` from `8002:8000` to `8000:8000`.

Useful container commands:

```powershell
docker compose ps
docker compose logs -f auth-service
docker compose down
```

`docker compose down` preserves the named database volume. Do not remove that
volume if you need to retain its data.

## API documentation

- Swagger UI: http://localhost:8002/docs when using the current Compose port mapping.
- ReDoc: http://localhost:8002/redoc

For a local Uvicorn run, use the port passed to Uvicorn (the command above
uses port 8000).

## API endpoints

All API routes use the `/api/auth` prefix.

| Method | Endpoint | Authentication | Success | Purpose |
|---|---|---:|---:|---|
| POST | `/api/auth/register` | No | 201 | Create a public user account |
| POST | `/api/auth/login` | No | 200 | Verify credentials and issue an access token |
| GET | `/api/auth/me` | Bearer JWT | 200 | Return the authenticated user's profile |
| POST | `/api/auth/verify-token` | Bearer JWT | 200 | Validate the bearer token and return the user |
| POST | `/api/auth/change-password` | Bearer JWT | 200 | Change the authenticated user's password |

Invalid request data returns 422. Registration with an existing email returns
409. Login with an unknown email or incorrect password returns 401; inactive
accounts are rejected. Protected routes return 401 for missing, invalid,
expired, inactive-user, or otherwise invalid credentials. A wrong current
password or a reused new password returns 400.

### Register

Password policy: at least 8 characters, including an uppercase letter, a
lowercase letter, and a digit. Public registration cannot set a role; the
service assigns `user`.

```powershell
$registration = @{
  full_name = "Avery Example"
  email = "avery@example.com"
  password = "StrongPass9"
  confirm_password = "StrongPass9"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/api/auth/register" `
  -Method Post -ContentType "application/json" -Body $registration
```

Successful response (the `id` is assigned by the database):

```json
{
  "message": "Registration successful.",
  "id": 1,
  "full_name": "Avery Example",
  "email": "avery@example.com",
  "is_active": true
}
```

### Login and JWT usage

```powershell
$login = @{
  email = "avery@example.com"
  password = "StrongPass9"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Uri "http://localhost:8002/api/auth/login" `
  -Method Post -ContentType "application/json" -Body $login
$token = $loginResponse.access_token
```

The response contains `message`, `access_token`, `token_type` (`bearer`), and
safe user information. Use the returned token in the `Authorization` header
for protected routes:

```powershell
Invoke-RestMethod -Uri "http://localhost:8002/api/auth/me" `
  -Headers @{ Authorization = "Bearer $token" }
```

JWT signing algorithm and expiration are configured by `JWT_ALGORITHM` and
`ACCESS_TOKEN_EXPIRE_MINUTES`. The token includes the user ID as a string in
`sub`, the user's `role`, and `iat`/`exp` timestamps. Keep the token private.

Token verification uses the same Bearer header:

```powershell
Invoke-RestMethod -Uri "http://localhost:8002/api/auth/verify-token" `
  -Method Post -Headers @{ Authorization = "Bearer $token" }
```

### Change password

The current password must be correct. The new password must meet the password
policy and match its confirmation; it must differ from the current password.

```powershell
$passwordChange = @{
  current_password = "StrongPass9"
  new_password = "NewStrong8"
  confirm_new_password = "NewStrong8"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/api/auth/change-password" `
  -Method Post -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" -Body $passwordChange
```

Success response:

```json
{
  "message": "Password changed successfully."
}
```

Passwords and password hashes are not included in API responses.

## Tests

Run the API tests from the service root:

```powershell
python -m pytest -q
```

The TestClient suite uses a fresh in-memory SQLite database and overrides the
database dependency; it does not connect to or modify MySQL data. It covers:

- Registration success and the public response fields
- Duplicate email, invalid email, missing fields, password mismatch, and weak passwords
- Successful login, incorrect password, unknown email, and inactive user
- Valid, missing, malformed, expired, and incorrectly signed JWTs
- `/me` with valid, missing, invalid, and inactive-user tokens
- Password change with incorrect current password, mismatched confirmation,
  successful update, login with the new password, and rejection of the old one
- Response bodies and omission of passwords/password hashes

### Actual validation results

- **Pytest:** 44 passed on 2026-11-05 using Python 3.11.9, a clean virtual
  environment, and in-memory SQLite fixtures. One upstream Starlette
  deprecation warning was emitted.
- **Compose config:** `docker compose config --quiet` passed on 2026-11-05.
- **Docker Compose:** `docker compose up --build` was exercised; MySQL became
  healthy, the API container started, and Alembic reported revision
  `20261105_01` at head. The API container was verified not to
  receive `MYSQL_ROOT_PASSWORD`. Host port 8000 was occupied, so validation
  used host port 8002. The validation containers were stopped afterward; the
  named database volume was preserved.
- **Manual Swagger test:** On 2026-11-05, registration returned HTTP 201,
  login returned HTTP 200 with an access token, and the bearer-protected
  `GET /api/auth/me` returned HTTP 200 with the authenticated user's profile.
  Swagger's HTTP Bearer authorization was confirmed. Credentials and token
  values are intentionally not recorded here.
- **Pending:** API route behavior has not been exercised by pytest against a
  live MySQL server. The route suite uses isolated SQLite and should not be
  interpreted as live-MySQL test results. Manual Swagger verification of
  `/api/auth/verify-token`, `/api/auth/change-password`, and the documented
  negative/error scenarios is also still pending.

## Monorepo and Git

This service is stored in the `shopease-auth-service` folder of the ShopEase
monorepo. Manage Git from the monorepo root, not from this service directory;
see the repository-level `README.md`. The root and service `.gitignore` files
exclude `.env` files and virtual environments. Check the staged files before
committing and ensure no secrets are included.
