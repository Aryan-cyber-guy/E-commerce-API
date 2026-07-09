# E-commerce API

A production-style e-commerce backend built with **FastAPI** and **SQLAlchemy**, backed by **PostgreSQL** for persistence and **Redis** for caching, rate limiting, and token blacklisting. The API covers the full customer journey — registration, product browsing, cart management, checkout, mock payments, and order history — plus an admin surface for managing products and users.

Deployed on **Railway** with a managed Postgres and Redis instance.

---

## Features

- **Authentication** — JWT access/refresh tokens delivered via `httpOnly` cookies, Argon2 password hashing, refresh-token rotation with Redis-backed blacklisting, and login rate limiting.
- **User management** — Registration, profile updates, password changes, and admin-only account enable/disable.
- **Product catalog** — Paginated, searchable, filterable product listing with Redis caching and cache invalidation on writes; admin-only create/update/soft-delete.
- **Cart** — Per-user cart with stock validation on add/update.
- **Checkout & payments** — Cart-to-order conversion, mock payment session creation, stock deduction on payment success, and duplicate-payment / pending-order guards.
- **Orders** — Paginated order history for users, plus an admin endpoint to view all orders.
- **Admin panel support** — User listing/search with caching, and account status toggling with self-disable protection.
- **Resilience** — Redis failures degrade gracefully (cache/rate-limit/blacklist checks are wrapped and fail open where appropriate) rather than taking down the API.

---

## Tech Stack

| Layer          | Technology                              |
|-----------------|------------------------------------------|
| Framework       | FastAPI                                  |
| ORM             | SQLAlchemy 2.0 (typed `Mapped` models)   |
| Database        | PostgreSQL                               |
| Cache / Sessions| Redis                                    |
| Auth            | JWT (`python-jose`), Argon2 (`passlib`)  |
| Validation      | Pydantic v2                              |
| Server          | Uvicorn                                  |
| Containerization| Docker / Docker Compose                 |
| Hosting         | Railway                                  |

---

## Project Structure

```
.
├── api/
│   ├── auth.py           # Auth dependencies: hashing, JWT, current-user/admin guards
│   ├── cart.py            # Cart endpoints
│   ├── orders.py          # Order history endpoints (user + admin)
│   └── products.py        # Product catalog endpoints (with Redis caching)
├── tests/                 # Pytest suite (unit, integration, and API tests)
├── database.py             # SQLAlchemy engine/session setup
├── db_model.py              # ORM models (Users, Products, Carts, Orders, Payments, etc.)
├── models.py                # Pydantic request/response schemas
├── redis_client.py          # Shared Redis client
├── main.py                  # App entrypoint: routes, middleware, checkout & payment logic
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Data Model

- **Users** — email/password auth, `USER`/`ADMIN` roles, soft-disable via `is_active`.
- **Products** — name, description, price, category, stock quantity, soft-delete via `is_active`.
- **Carts / CartItems** — one cart per user, line items referencing products.
- **Orders / OrderItems** — snapshotted product name and price at time of purchase.
- **Payments** — one-to-one with an order, tracks `PENDING` / `PAID` / `FAILED` / `REFUNDED` status.

---

## Getting Started

### Prerequisites

- Python 3.13
- PostgreSQL instance
- Redis instance
- Docker & Docker Compose (optional, for containerized setup)

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd <repo-directory>
cp .env.example .env
```

Fill in `.env`:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<db>
SECRET_KEY=<a-strong-random-secret>
ADMIN_EMAIL=<admin-email-to-seed-on-startup>
ADMIN_PASSWORD=<admin-password-to-seed-on-startup>
REDIS_URL=redis://<host>:<port>
```

> On startup, if `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set, the app seeds a default admin account if one doesn't already exist.

### 2. Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### 3. Run with Docker Compose

```bash
docker compose up --build
```

This spins up the API alongside `postgres:18` and `redis:alpine`, with health checks gating startup order. Compose expects a `.env.docker` file (same variables as above, with `DATABASE_URL`/`REDIS_URL` pointing at the service names, e.g. `postgres` and `redis`).

---

## API Overview

All endpoints are prefixed as shown; authenticated endpoints expect `access_token` / `refresh_token` cookies set by the login flow.

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create a new user + cart |
| POST | `/auth/login` | Authenticate, set auth cookies (rate-limited) |
| POST | `/auth/refresh` | Rotate access/refresh tokens |
| POST | `/auth/logout` | Clear cookies, blacklist refresh token |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Get the current user's profile |
| PATCH | `/users/me` | Update name/email |
| PATCH | `/users/me/password` | Change password |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/products/` | Paginated, searchable, filterable product list (cached) |
| GET | `/products/{id}` | Get a single product (cached) |
| POST | `/products/` | Create a product *(admin)* |
| PATCH | `/products/{id}` | Update a product *(admin)* |
| DELETE | `/products/{id}` | Soft-delete a product *(admin)* |

### Cart
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cart/` | View current cart |
| POST | `/cart/items` | Add item (stock-checked) |
| PATCH | `/cart/items/{id}` | Update item quantity |
| DELETE | `/cart/items/{id}` | Remove item |

### Checkout & Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/checkout` | Convert cart into a pending order |
| GET | `/payments/pending` | Get the current user's pending payment, if any |
| POST | `/payments/create-session/{order_id}` | Create a mock payment session |
| POST | `/payments/mock/{payment_id}/success` | Mark payment paid, deduct stock, clear cart |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/orders/` | Paginated order history for the current user |
| GET | `/orders/{id}` | Get one of the current user's orders |
| GET | `/orders/admin` | Paginated list of all orders *(admin)* |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | Paginated, searchable user list (cached) |
| PATCH | `/admin/users/{user_id}/status` | Enable/disable a user (self-disable blocked) |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` / `/health` | Health check |

---

## Testing

The project includes a comprehensive Pytest suite covering authentication, user management, products, cart, checkout, payments, orders, and admin functionality — with both mocked unit tests and isolated SQLite integration tests for cart operations.

**Coverage highlights:**
- Password hashing/verification, JWT creation/validation, login/logout/refresh flows, rate limiting, and Redis-failure fallback behavior
- Registration, profile updates, password changes, duplicate-email handling
- Product CRUD, caching, soft-delete, and DB exception handling
- Cart add/update/delete with stock validation
- Checkout edge cases: empty cart, insufficient stock, existing pending order, rollback on failure
- Payment session creation, mock completion, duplicate-payment prevention, stock deduction
- Order pagination for users and admins
- Admin user enable/disable, including self-disable protection

**Tools used:** Pytest, FastAPI `TestClient`, `unittest.mock`, SQLite (for isolated integration tests), and FastAPI dependency overrides.

Run the suite:

```bash
pytest
```

---

## Deployment Notes

- Deployed on **Railway** with managed PostgreSQL and Redis add-ons.
- CORS is currently configured for a fixed set of frontend origins in `main.py` — update `allow_origins` when adding new frontend deployments.
- Auth cookies are set with `secure=True` and `samesite="None"`, which requires the API to be served over HTTPS in production.
- `Base.metadata.create_all()` runs on startup for schema creation; consider migrating to Alembic for production schema management as the project grows.

---

## License

[![MIT License](https://shields.io)](https://choosealicense.com)

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
