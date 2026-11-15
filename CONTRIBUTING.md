# Contributing to StockGuard

Thank you for your interest in contributing to StockGuard! We welcome contributions to our distributed inventory intelligence and saga coordination platform.

---

## 1. Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16 (running locally on port 5432)
- RabbitMQ 3.13 (optional; in-memory fallback is active when broker is offline)

### Installation
```bash
git clone https://github.com/rohitam26/stockguard.git
cd stockguard
python -m pip install -r requirements.txt
pip install -e .
```

### Environment Configuration
Copy `.env.example` to `.env` and verify database connection details:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgrespassword@localhost:5432/stockguard
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
ENVIRONMENT=development
```

---

## 2. Running Verification & Quality Checks

Before submitting any Pull Request, ensure that all test suites and quality gates pass:

```bash
# 1. Complete Pytest Suite
python -m pytest -v

# 2. 25-Endpoint API Verification
python scripts/verify_all_api_endpoints.py

# 3. Real-Time Multi-Window Polling & Fault Recovery Verification
python scripts/test_realtime_sync.py

# 4. Frontend UI Browser Audit
python scripts/audit_frontend.py

# 5. Dependency Vulnerability Audit
python -m pip_audit -r requirements.txt
```

---

## 3. Pull Request Guidelines

- **Zero Overselling Invariant:** Never modify database CHECK constraints (`available_stock >= 0`) or remove atomic conditional SQL update guards.
- **Idempotency Guarantees:** Any new mutation endpoints must accept and enforce client idempotency keys.
- **Transactional Outbox:** All domain state transitions intended for asynchronous event consumption must be recorded to `outbox_messages` within the same database transaction.
- **Security:** Do not commit hardcoded credentials, `.env` files, or secrets. Ensure all dynamic DOM injections use `escapeHtml()`.
- **Code Style:** Adhere to PEP 8 standards and Pydantic validation schemas.
