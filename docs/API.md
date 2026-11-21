# StockGuard API Specification

**Base URL:** `/api/v1`<br>
**Authentication:** `Authorization: Bearer <access_token>`

---

## 1. Authentication & Identity (`/auth`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register new user account | Public (Rate Limited) |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT access + refresh token | Public (Rate Limited) |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token and obtain new access token | Public (Rate Limited) |
| `POST` | `/api/v1/auth/revoke` | Revoke refresh token (logout) | Public |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Authenticated |

---

## 2. Inventory & Catalog (`/products`, `/inventory`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/products` | List catalog products | Public |
| `POST` | `/api/v1/products` | Create catalog SKU with initial stock | `INVENTORY_MANAGER`, `ADMIN` |
| `GET` | `/api/v1/inventory` | List stock levels & low stock flags | Public |
| `GET` | `/api/v1/inventory/{sku}` | Get inventory level for SKU | Public |
| `POST` | `/api/v1/inventory/{sku}/adjust` | Atomic stock level adjustment (+/-) | `INVENTORY_MANAGER`, `ADMIN` |

---

## 3. Reservations (`/reservations`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reservations` | Create atomic stock reservation (requires `idempotency_key`) | `CUSTOMER`, `ADMIN` |
| `GET` | `/api/v1/reservations` | List active reservations | Public / Filtered |
| `GET` | `/api/v1/reservations/{id}` | Get reservation details | Public / Filtered |
| `POST` | `/api/v1/reservations/{id}/release` | Manually release an active reservation | `CUSTOMER`, `ADMIN` |
| `POST` | `/api/v1/reservations/expire-stale` | Trigger background sweep of expired reservations | `ADMIN` |

---

## 4. Orders & Distributed Saga (`/orders`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/orders` | Create order with items in PENDING state | `CUSTOMER`, `ADMIN` |
| `GET` | `/api/v1/orders` | List orders | Public / Filtered |
| `GET` | `/api/v1/orders/{id}` | Get order details (IDOR protected for customers) | `CUSTOMER` (owner), `ADMIN` |
| `POST` | `/api/v1/orders/{id}/checkout` | Execute multi-step checkout Saga with compensation | `CUSTOMER`, `ADMIN` |

---

## 5. Health, Probes & Observability (`/health`, `/metrics`)

| Method | Endpoint | Description | Role / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Comprehensive system health & topology | Public |
| `GET` | `/api/v1/health/live` | Kubernetes liveness probe (200 OK) | Public |
| `GET` | `/api/v1/health/ready` | Kubernetes readiness probe (PostgreSQL check) | Public |
| `GET` | `/metrics` | Prometheus text exposition metrics | Public |
