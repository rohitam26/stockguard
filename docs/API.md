# StockGuard API Documentation

Base URL: `/api/v1`  
Interactive Swagger UI: `http://localhost:8000/docs`

---

## 1. System Health

### `GET /health`
Returns system status, active database engine, masked connection string, and message broker connectivity.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-11-15T18:47:12.361Z",
  "database": {
    "status": "healthy",
    "engine": "PostgreSQL",
    "url_masked": "localhost:5432/stockguard"
  },
  "messaging": {
    "broker": "In-Memory Event Bus (Fallback)",
    "connected": false
  },
  "version": "1.0.0",
  "environment": "development"
}
```

---

## 2. Products Catalog

### `POST /products`
Registers a new product and initializes its corresponding inventory record.

**Request Body:**
```json
{
  "sku": "LAPTOP-PRO-16",
  "name": "MacBook Pro M3 16-inch 36GB",
  "description": "High-performance developer workstation",
  "price": 2499.00,
  "initial_stock": 25,
  "low_stock_threshold": 5
}
```

### `GET /products`
Lists products with optional pagination and active filters.

### `GET /products/{product_id_or_sku}`
Retrieves a single product by UUID or SKU.

---

## 3. Inventory Management

### `GET /inventory`
Lists all inventory records including available, reserved, allocated, and total units.

### `GET /inventory/{sku}`
Retrieves inventory breakdown for a specific SKU.

### `POST /inventory/adjust`
Applies an atomic inventory restock or deduction.

**Request Body:**
```json
{
  "sku": "LAPTOP-PRO-16",
  "quantity_delta": 10,
  "reason": "Warehouse batch intake"
}
```

---

## 4. Atomic Reservations

### `POST /reservations`
Atomically reserves stock for a product. Guarantees idempotency.

**Request Body:**
```json
{
  "sku": "LAPTOP-PRO-16",
  "quantity": 2,
  "ttl_seconds": 600,
  "idempotency_key": "idemp-client-req-987"
}
```

### `POST /reservations/{reservation_id}/release`
Explicitly cancels an active reservation and restores stock to available inventory.

### `POST /reservations/expire-stale`
Background sweep endpoint that releases expired reservations whose TTL has elapsed.

---

## 5. Orders & Distributed Saga

### `POST /orders`
Creates a customer order in `PENDING` status.

**Request Body:**
```json
{
  "customer_id": "cust-techcorp",
  "items": [
    {"sku": "KEYBOARD-MECH", "quantity": 2},
    {"sku": "MOUSE-PRECISION", "quantity": 2}
  ],
  "idempotency_key": "order-req-202"
}
```

### `POST /orders/{order_id}/checkout`
Executes the Distributed Saga Orchestrator:
- Reserves all items atomically.
- Simulates payment.
- Triggers automatic backward compensation if payment is declined.
- Allocates stock and initiates fulfillment on success.

**Parameters:**
- `payment_method` (string, default: `CREDIT_CARD`)
- `simulate_failure` (boolean, default: `false`)

---

## 6. Transactional Outbox

### `GET /outbox`
Lists staged outbox events, status (`PENDING` or `PUBLISHED`), and retry counts.

### `POST /outbox/process`
Triggers the Outbox Worker to publish pending messages to the message broker.
