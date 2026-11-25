# StockGuard API Specification

**Base URL:** `/api/v1`<br>
**Authentication:** `Authorization: Bearer <access_token>`

---

## 1. Authentication & Identity (`/auth`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register new user account | `{"email", "password", "role"}` | Public (Rate Limited) |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT access (30m) + refresh token (7d) | `{"email", "password"}` | Public (Rate Limited) |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token and obtain new access token (30m) | `{"refresh_token"}` | Public (Rate Limited) |
| `POST` | `/api/v1/auth/revoke` | Revoke refresh token (logout) | `{"refresh_token"}` | Public |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | None | Authenticated |

---

## 2. Products Catalog (`/products`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/products` | List catalog products | `skip`, `limit` | Public |
| `POST` | `/api/v1/products` | Create catalog SKU with initial stock | `{"sku", "name", "price", ...}` | `INVENTORY_MANAGER`, `ADMIN` |
| `GET` | `/api/v1/products/{product_id}` | Get product details by ID | `product_id` | Public |
| `PUT` | `/api/v1/products/{product_id}` | Update product information | `{"name", "price", ...}` | `INVENTORY_MANAGER`, `ADMIN` |

---

## 3. Inventory Control (`/inventory`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/inventory` | List stock levels & low stock indicators | `skip`, `limit` | Public |
| `GET` | `/api/v1/inventory/{sku}` | Get inventory level for SKU | `sku` | Public |
| `POST` | `/api/v1/inventory/adjust` | Atomic stock level adjustment (+/-) | `{"sku", "quantity_delta", "reason"}` | `INVENTORY_MANAGER`, `ADMIN` |

---

## 4. Reservations (`/reservations`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reservations` | Create atomic stock reservation | `{"sku", "quantity", "idempotency_key"}` | `CUSTOMER`, `ADMIN` |
| `GET` | `/api/v1/reservations` | List active reservations | `skip`, `limit` | Public |
| `GET` | `/api/v1/reservations/{reservation_id}` | Get reservation details | `reservation_id` | Public |
| `POST` | `/api/v1/reservations/{reservation_id}/release` | Manually release an active hold | `reservation_id`, `{"reason"}` | `CUSTOMER`, `ADMIN` |
| `POST` | `/api/v1/reservations/expire-stale` | Trigger background sweep of expired holds | None | `ADMIN` |

---

## 5. Orders & Distributed Saga (`/orders`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/orders` | Create order with items in PENDING state | `{"customer_id", "items": [...]}` | `CUSTOMER`, `ADMIN` |
| `GET` | `/api/v1/orders` | List order history | `skip`, `limit` | Public |
| `GET` | `/api/v1/orders/{order_id}` | Get order details (IDOR protected) | `order_id` | `CUSTOMER` (owner), `ADMIN` |
| `POST` | `/api/v1/orders/{order_id}/checkout` | Execute multi-step checkout Saga with compensation | `payment_method`, `simulate_failure` | `CUSTOMER`, `ADMIN` |

---

## 6. Payment Operations (`/payments`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/payments/process` | Process or simulate order payment | `{"order_id", "payment_method", ...}` | `CUSTOMER`, `ADMIN` |
| `GET` | `/api/v1/payments/order/{order_id}` | Get payment transaction for an order | `order_id` | Authenticated |

---

## 7. Fulfillment Operations (`/fulfillment`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/fulfillment/order/{order_id}` | Initiate packing & fulfillment dispatch | `order_id`, `{"carrier", "notes"}` | `INVENTORY_MANAGER`, `ADMIN` |
| `GET` | `/api/v1/fulfillment/order/{order_id}` | Get fulfillment & tracking status for order | `order_id` | Authenticated |

---

## 8. Transactional Outbox Operations (`/outbox`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/outbox` | View outbox event stream | `skip`, `limit` | `ADMIN` |
| `POST` | `/api/v1/outbox/process` | Trigger outbox event dispatch batch | `batch_size` | `ADMIN` |

---

## 9. Health, Probes & Observability (`/health`, `/metrics`)

| Method | Endpoint | Description | Key Parameters / Payload | Role / Auth |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Comprehensive system health & topology | None | Public |
| `GET` | `/api/v1/health/live` | Kubernetes liveness probe (200 OK) | None | Public |
| `GET` | `/api/v1/health/ready` | Kubernetes readiness probe (PostgreSQL check) | None | Public |
| `GET` | `/api/v1/health/metrics` | In-app Prometheus metrics exposition | None | Public |
| `GET` | `/metrics` | Top-level Prometheus text exposition | None | Public |
