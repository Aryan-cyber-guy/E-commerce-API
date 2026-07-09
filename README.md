# E-commerce API

Feature-rich RESTful backend inspired by production practices for an e-commerce platform, built with **FastAPI**, **PostgreSQL**, and **Redis**. It powers **Nova Store**, providing authentication, product catalog management, cart operations, checkout, mock payments, order history, and admin controls.

**Live API:** [e-commerce-api-production-98ad.up.railway.app](https://e-commerce-api-production-98ad.up.railway.app) \
**Frontend (Nova Store):** [ecom-elevate-one.vercel.app](https://ecom-elevate-one.vercel.app/)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
  - [Authentication](#authentication)
  - [Users](#users)
  - [Products](#products)
  - [Cart](#cart)
  - [Checkout & Payments](#checkout--payments)
  - [Orders](#orders)
  - [Admin](#admin)
- [Data Model](#data-model)
- [Caching Strategy](#caching-strategy)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security Notes](#security-notes)

---

## Features

- **JWT Authentication** with short-lived access tokens and rotating refresh tokens, delivered via `httpOnly` cookies
- **Refresh token blacklisting** on logout/rotation using Redis, to prevent reuse of stale tokens
- **Login rate limiting** (Redis-backed) to slow down brute-force attempts
- **Role-based access control** (`user` / `admin`) with dedicated admin endpoints
- **Password hashing** using Argon2 via Passlib
- **Product catalog** with search, category filtering, and pagination
- **Redis caching** for product listings, individual products, and admin user listings, with automatic cache invalidation on writes
- **Shopping cart** with stock validation and quantity management, auto-created per user
- **Checkout flow** that snapshots order line items (name & price at time of purchase) and prevents duplicate pending orders
- **Mock payment flow** with row-level locking (`SELECT ... FOR UPDATE`) to safely deduct stock and avoid race conditions
- **Order history** with pagination for both individual users and admins
- **Admin panel endpoints** for managing users (search, enable/disable) and products (create, update, soft-delete)
- **Auto-seeded admin account** on startup via environment variables
- **Health check endpoint** for uptime monitoring on Railway

---

## Tech Stack

| Layer                  | Technology                                             |
|--------------------------|-----------------------------------------------------------|
| Framework                  | [FastAPI](https://fastapi.tiangolo.com/)                     |
| Language                     | Python 3.13                                                     |
| ORM                            | SQLAlchemy 2.0 (typed, `Mapped` declarative models)               |
| Database                         | PostgreSQL                                                          |
| Cache / Rate Limiting               | Redis                                                                 |
| Validation                            | Pydantic v2                                                             |
| Auth                                     | JWT (`python-jose`), Argon2 (`passlib`, `argon2-cffi`)                    |
| Server                                     | Uvicorn                                                                      |
| Containerization                             | Docker / Docker Compose                                                        |
| Hosting                                        | Railway (API, Postgres, Redis)                                                    |
| Testing                                          | Pytest, FastAPI `TestClient`, `unittest.mock`, SQLite (integration)                  |

---

## Project Structure

```
.
├── api/
│   ├── auth.py           # Auth dependencies: hashing, JWT, current-user, admin guard
│   ├── cart.py            # Cart router: view / add / update / delete items
│   ├── orders.py           # Order history router (user + admin)
│   └── products.py         # Product catalog router with Redis caching
├── tests/                  # Pytest suite (unit, integration, mocked dependencies)
├── database.py              # Engine, session factory, get_db dependency
├── db_model.py               # SQLAlchemy models & enums (Users, Products, Carts, Orders, Payments)
├── models.py                  # Pydantic schemas for requests/responses
├── redis_client.py             # Shared Redis client instance
├── main.py                      # App entrypoint: auth, checkout, payments, users, admin routes
├── requirements.txt              # Python dependencies
├── Dockerfile                     # Container build definition
├── docker-compose.yml               # Local orchestration (API + Postgres + Redis)
└── .env.example                      # Required environment variables
```

Routers for `cart`, `products`, and `orders` live under `api/` and are mounted in `main.py`. Authentication, user management, checkout, and payments are defined directly in `main.py`.

---

## Architecture Overview

- **Request flow:** Client → CORS middleware → Router → Auth dependency (`get_current_user` / `admin_required`) → SQLAlchemy session → PostgreSQL, with Redis consulted for cacheable reads.
- **Auth model:** Two JWTs are issued on login — a 15-minute access token and a 7-day refresh token — both stored as `httpOnly`, `Secure`, `SameSite=None` cookies so they work across the Vercel frontend and Railway backend. Refresh tokens are blacklisted in Redis on logout or rotation.
- **Consistency:** Payment completion uses `with_for_update()` row locks on the payment and each affected product to prevent overselling stock under concurrent requests.
- **Cache invalidation:** Any write to products or user status clears the relevant Redis keys so subsequent reads are never stale beyond the write itself.

---

## Getting Started

### Prerequisites

- Python 3.13+
- PostgreSQL instance
- Redis instance
- Docker & Docker Compose (optional, for containerized setup)

### Local Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # then fill in the values — see Environment Variables below
   ```

5. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```

   The API will be available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

### Running with Docker Compose

This spins up the API, PostgreSQL, and Redis together:

```bash
cp .env.example .env.docker
# fill in .env.docker (docker-compose reads POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD from here too)
docker compose --env-file .env.docker up
```

The API container waits for Postgres to report healthy and for Redis to start before booting, and exposes a `/health` check used by its own Docker healthcheck.

### Environment Variables

| Variable          | Description                                                              | Required |
|--------------------|------------------------------------------------------------------------------|----------|
| `DATABASE_URL`       | PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/db`)      | Yes |
| `SECRET_KEY`          | Secret used to sign JWTs                                                         | Yes |
| `ADMIN_EMAIL`          | Email for the auto-seeded admin account on startup                                 | Optional |
| `ADMIN_PASSWORD`        | Password for the auto-seeded admin account                                           | Optional |
| `REDIS_URL`              | Redis connection string (defaults to `redis://localhost:6379`)                         | Yes |

> If `ADMIN_EMAIL` / `ADMIN_PASSWORD` are omitted, no admin account is seeded and one must be promoted manually in the database.

---

## API Reference

Base URL (production): `https://e-commerce-api-production-98ad.up.railway.app`

Interactive OpenAPI docs are available at `/docs` on any running instance.

### Authentication

| Method | Endpoint            | Description                                            | Auth |
|--------|------------------------|-------------------------------------------------------------|------|
| POST   | `/auth/register`          | Register a new user, creates an empty cart                     | No |
| POST   | `/auth/login`               | Authenticate and set access/refresh cookies                       | No |
| POST   | `/auth/refresh`                | Rotate tokens using the refresh cookie                               | Cookie |
| POST   | `/auth/logout`                   | Blacklist the refresh token and clear cookies                           | Cookie |

Login is rate-limited to 10 attempts per email per 60-second window via Redis.

### Users

| Method | Endpoint              | Description                        | Auth |
|--------|--------------------------|-----------------------------------------|------|
| GET    | `/users/me`                 | Get the current user's profile             | User |
| PATCH  | `/users/me`                   | Update name / email                          | User |
| PATCH  | `/users/me/password`            | Change password                                | User |

### Products

| Method | Endpoint           | Description                                                             | Auth  |
|--------|-----------------------|------------------------------------------------------------------------------|-------|
| GET    | `/products/`              | List active products — supports `search`, `category`, `page`, `size`             | No |
| GET    | `/products/{id}`             | Get a single active product                                                        | No |
| POST   | `/products/`                    | Create a product                                                                       | Admin |
| PATCH  | `/products/{id}`                   | Update a product                                                                          | Admin |
| DELETE | `/products/{id}`                      | Soft-delete a product (`is_active = false`)                                                | Admin |

Product listings and single-product lookups are cached in Redis for 5 minutes; write operations invalidate matching cache keys.

### Cart

| Method | Endpoint               | Description                                | Auth |
|--------|---------------------------|--------------------------------------------------|------|
| GET    | `/cart/`                      | View current cart contents                          | User |
| POST   | `/cart/items`                    | Add a product to the cart (validates stock)             | User |
| PATCH  | `/cart/items/{id}`                  | Update a cart item's quantity                              | User |
| DELETE | `/cart/items/{id}`                     | Remove an item from the cart                                  | User |

A cart is created automatically for a user on first access if one doesn't exist.

### Checkout & Payments

| Method | Endpoint                                | Description                                                          | Auth |
|--------|---------------------------------------------|----------------------------------------------------------------------------|------|
| POST   | `/checkout`                                     | Create a pending order from the current cart                                   | User |
| GET    | `/payments/pending`                                | Check whether the user has a pending payment                                       | User |
| POST   | `/payments/create-session/{order_id}`                 | Create (or return existing) mock payment session for an order                         | User |
| POST   | `/payments/mock/{payment_id}/success`                    | Mark payment paid, deduct stock, clear cart                                              | User |

Checkout blocks a new order if the user already has one pending, and re-validates stock at both checkout and payment time. Stock deduction uses row-level locks to stay correct under concurrent checkouts.

### Orders

| Method | Endpoint            | Description                                          | Auth  |
|--------|------------------------|-------------------------------------------------------------|-------|
| GET    | `/orders/`                 | Paginated order history for the current user                    | User  |
| GET    | `/orders/{id}`                | Get one of the current user's orders with line items               | User  |
| GET    | `/orders/admin`                 | Paginated order history across all users                              | Admin |

### Admin

| Method | Endpoint                         | Description                                    | Auth  |
|--------|--------------------------------------|------------------------------------------------------|-------|
| GET    | `/admin/users`                          | Paginated, searchable list of users                       | Admin |
| PATCH  | `/admin/users/{user_id}/status`            | Toggle a user's active status (self-disable blocked)          | Admin |

---

## Data Model

Core entities defined in `db_model.py`:

- **DbUsers** — account details, role (`admin` / `user`), one cart, many orders
- **Products** — catalog items with category, price, stock, active flag
- **Carts / CartItems** — one cart per user, many line items referencing products
- **Orders / OrderItems** — order snapshot with status and payment status; line items freeze product name and price at time of purchase
- **Payments** — one payment per order, tracks status and paid timestamp

Enums: `UserRole`, `Category`, `OrderStatus`, `PaymentStatus`.

---

## Caching Strategy

| Cache Key Pattern                              | Populated By              | Invalidated By                                    | TTL |
|-----------------------------------------------------|--------------------------------|--------------------------------------------------------|-----|
| `products:page=*:size=*:category=*:search=*`             | `GET /products/`                    | Product create / update / delete                          | 300s |
| `product:{id}`                                              | `GET /products/{id}`                    | Update / delete of that product                              | 300s |
| `users:page=*:size=*:search=*`                                 | `GET /admin/users`                        | Toggling any user's active status                               | 300s |
| `login_attempts:{email}`                                          | `POST /auth/login`                            | Expires automatically after 60s, or on successful login             | 60s |
| `blacklist:{token_hash}`                                             | Logout / token refresh                            | Expires when the token would have expired anyway                       | Varies |

All Redis calls are wrapped so that Redis outages degrade gracefully (cache misses / skipped rate limiting) rather than causing request failures — with the exception of token blacklisting on refresh/logout, which fails closed with a `503`.

---

## Testing

The project includes a comprehensive Pytest suite covering authentication, user management, products, cart, checkout, payments, orders, and admin functionality.

**Coverage highlights:**
- Password hashing/verification and JWT creation/validation
- Login, logout, refresh flows, rate limiting, and Redis-failure fallback behavior
- Full CRUD and caching behavior for products, including soft-delete
- Cart operations with stock validation, run against an isolated SQLite database
- Checkout edge cases: empty cart, insufficient stock, duplicate pending orders, rollback on failure
- Payment session creation, mock completion, duplicate-payment prevention, and stock deduction
- Paginated order retrieval for users and admins, including empty-result and error handling
- Admin user management, including self-disable protection and database rollback scenarios

**Tools used:** Pytest, FastAPI `TestClient`, `unittest.mock`, SQLite (for isolated integration tests), and `monkeypatch` for runtime dependency overrides.

Run the suite with:
```bash
pytest
```

---

## Deployment

The API is deployed on **Railway** alongside managed PostgreSQL and Redis services, built from the included `Dockerfile`. A `/health` endpoint is used for uptime checks, and `docker-compose.yml` documents the equivalent local topology (API + Postgres + Redis with health-checked startup ordering).

The frontend (**Nova Store**) is a separate project deployed on **Vercel**, configured to call this API via `src/lib/api.ts`. CORS is currently configured in `main.py` to allow the deployed Vercel origin(s) and local development ports.

---

## Security Notes

- Access and refresh tokens are stored in `httpOnly`, `Secure`, `SameSite=None` cookies — never exposed to client-side JavaScript.
- Refresh tokens are single-use in practice: each refresh blacklists the previous token in Redis until its original expiry.
- Passwords are hashed with Argon2, the current OWASP-recommended algorithm.
- Admin routes are protected by a dedicated `admin_required` dependency layered on top of standard authentication.
- Product deletion is a soft-delete (`is_active = false`), preserving historical order data integrity.
