# StockGuard Security Policy & Hardening Guide

## 1. Security Architecture Summary

StockGuard enforces defense-in-depth across the API, application, database, and messaging layers:

- **Authentication & JWT Security:** Signed JWT access tokens (HMAC-SHA256) with 30-minute expiration.
- **Refresh Token Rotation:** Refresh tokens are stored strictly as SHA-256 hashes; each rotation invalidates the prior token, preventing replay attacks.
- **Password Hashing:** Passwords hashed with `bcrypt` (work factor 12) or Argon2. Plaintext passwords are never persisted.
- **Role-Based Access Control (RBAC):** Fine-grained permission enforcement (`ADMIN`, `INVENTORY_MANAGER`, `CUSTOMER`, `SERVICE`).
- **IDOR Protection:** Resource-level ownership validation prevents unauthorized cross-user order and data inspection.
- **Rate Limiting:** Sliding window limiter prevents brute-force attacks on `/api/v1/auth/*` and sensitive endpoints.
- **No Hardcoded Secrets:** Passwords and credentials externalized via environment variables and `.env` (gitignored).
- **SQL Injection Prevention:** 100% of SQL interactions utilize parameterized queries and SQLAlchemy 2.0 ORM expressions.
- **Database CHECK Constraints:** Negative inventory is prohibited by PostgreSQL engine CHECK constraints (`available_stock >= 0`).
- **Dependency Security:** Monitored with `pip-audit`. Zero known vulnerabilities found.

---

## 2. Security Test Matrix

| Category | Implementation | Verification Test |
| :--- | :--- | :--- |
| **Password Hashing** | Bcrypt (12 rounds) / Argon2 | `test_user_registration_and_password_hashing` |
| **Authentication & Login** | Valid credentials required; 401 on bad password | `test_user_login_success_and_failure` |
| **Token Expiration** | Expired signature rejected with 401 | `test_jwt_access_and_expiration` |
| **Token Rotation & Replay** | Single-use refresh token; reuse rejected with 401 | `test_refresh_token_rotation_and_revocation` |
| **IDOR Protection** | Customer forbidden from reading other customer's order | `test_idor_protection_enforcement` |
| **Rate Limiting** | 429 Too Many Requests with Retry-After header | `test_rate_limiter_unit` |
| **Static Security (Bandit)** | Clean scan; zero high or medium severity issues | `bandit -r src/stockguard -ll` |
