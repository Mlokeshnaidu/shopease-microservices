# ShopEase User Management Service

Independent FastAPI microservice for customer profiles and delivery addresses.
Authentication and registration remain in the Authentication Service; this
service stores no passwords or authentication credentials.

## Structure

```text
app/
  core/           settings, JWT verification, request dependencies
  database/       SQLAlchemy engine and session dependency
  models/         user profile and delivery address ORM models
  routers/        user and address HTTP endpoints
  schemas/        request validation and response models
  services/       profile/address business logic
alembic/          schema migration
tests/            API tests
Dockerfile
docker-compose.yml
requirements.txt
```

## Authentication integration

Send `Authorization: Bearer <access_token>` on protected endpoints. The service
validates the token signature, expiry, subject, role, and issued-at claim using
the same `JWT_SECRET_KEY` and `JWT_ALGORITHM` as the Authentication Service.
The authentication service's current token format uses the auth account ID as
the `sub` claim. Share the signing secret securely through deployment
configuration; never commit it. The optional `AUTH_SERVICE_URL` setting
documents/configures the paired service URL, but access-token verification is
local and does not make an HTTP call.

Client-supplied user IDs are never used for ownership. Profiles bind
`auth_user_id` to the JWT subject and all address operations query through the
authenticated profile. Missing or invalid tokens receive 401; cross-account
resource IDs are scoped and reported as 404 to avoid disclosing resource
existence. A deactivated local profile receives 403.

Deactivation (`POST /api/users/account/deactivate`) is local to this service:
it soft-disables the profile and blocks subsequent profile/address operations.
It does not delete or disable the Authentication Service account, revoke
already issued tokens there, or prevent login. The auth team must handle auth
account suspension/token revocation separately when required. Re-enablement
requires an authorized administrative workflow; this service does not provide
one. `DELETE /api/users/profile` permanently removes this profile and its
addresses only, and likewise does not change the auth account.

## Database and configuration

Create `.env` from `.env.example`. The Compose stack provisions its own
`shopease_user_db` MySQL 8 instance with persistent named volume storage.

| Variable | Purpose |
|---|---|
| `MYSQL_HOST`, `MYSQL_PORT` | MySQL connection target (`user-mysql:3306` in Compose) |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` | User database credentials |
| `MYSQL_ROOT_PASSWORD` | MySQL container administration password |
| `DATABASE_URL` | Optional complete SQLAlchemy URL; leave empty to use MySQL variables |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM` | Must match the Authentication Service |
| `AUTH_SERVICE_URL` | Paired Authentication Service URL (informational; JWTs are locally verified) |

`user_profiles.auth_user_id` is unique. `user_addresses.user_id` has a
foreign-key relationship with cascading profile deletion. The application
serializes default-address changes by locking the owning profile row and clears
other defaults in the same transaction.

## Run with Docker

From this directory:

```powershell
Copy-Item .env.example .env
# Set distinct strong MySQL passwords, and set JWT_SECRET_KEY/JWT_ALGORITHM
# to the same values configured for shopease-auth-service.
docker compose up --build
```

Compose waits for MySQL health, runs `alembic upgrade head`, then starts the
API on `http://localhost:8004`. Swagger UI is at `/docs`.

To run outside Docker, install `requirements.txt`, configure `.env` for a
reachable MySQL instance, and run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8004
```

Migration commands:

```powershell
alembic upgrade head
alembic current
alembic downgrade -1
```

## API

All routes are prefixed with `/api`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/users/profile` | Create the authenticated user's profile |
| GET | `/users/profile` | Retrieve the current profile |
| PUT | `/users/profile` | Replace editable profile fields |
| PATCH | `/users/profile` | Partially update profile |
| DELETE | `/users/profile` | Permanently delete profile and saved addresses |
| POST | `/users/account/deactivate` | Soft-deactivate local profile |
| POST | `/users/addresses` | Add a delivery address |
| GET | `/users/addresses` | List current user's addresses |
| GET | `/users/addresses/{address_id}` | Retrieve an owned address |
| PUT | `/users/addresses/{address_id}` | Replace an owned address |
| DELETE | `/users/addresses/{address_id}` | Delete an owned address |
| PATCH | `/users/addresses/{address_id}/default` | Set an owned address as default |

Phone numbers are validated; address mandatory fields are trimmed and checked.
Email, password, and login/registration endpoints are intentionally absent.

## Tests

Run `pytest` in this directory. The API tests cover missing/invalid JWTs,
profile CRUD and duplicate prevention, validation failures, account
deactivation, address CRUD, default-address uniqueness, and cross-account
address access. Tests use an isolated in-memory SQLite database and signed test
tokens; no MySQL or live Authentication Service is required.

The test suite verifies API behavior and local persistence transactions. To
exercise the deployed MySQL schema, migrations, or the real auth-issued token,
start both service stacks with matching JWT settings and use Swagger UI to
repeat the scenarios.
