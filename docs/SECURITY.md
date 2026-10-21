# StockGuard Security Policy & Hardening Guide

## 1. Security Architecture Summary

StockGuard enforces defense-in-depth across the API, application, database, and messaging layers:

- **No Hardcoded Secrets:** Passwords and credentials are fully externalized via environment variables and `.env` (gitignored).
- **SQL Injection Prevention:** 100% of SQL interactions utilize parameterized queries and SQLAlchemy 2.0 ORM expressions. Raw unescaped strings are forbidden.
- **Input Sanitization & Schema Validation:** Strict Pydantic models validate all incoming requests, enforcing string constraints, minimum/maximum lengths, regex patterns, and non-negative amounts.
- **Database CHECK Constraints:** Negative inventory is physically prohibited by database engine CHECK constraints (`available_stock >= 0`, `reserved_stock >= 0`, `allocated_stock >= 0`).
- **CORS Hardening:** Configurable allowed origins preventing unauthorized cross-origin browser interactions.
- **Dependency Vulnerabilities:** Scanned with `pip-audit`. Zero known vulnerabilities found.

## 2. Security Audit Results

| Category | Status | Details |
| :--- | :--- | :--- |
| **Dependency Audit (`pip-audit`)** | PASSED | 0 known CVEs across all installed packages. |
| **Database Constraints** | PASSED | CHECK constraints physically enforced in PostgreSQL 16. |
| **Secrets Exposure** | PASSED | `.env` gitignored, passwords passed via environment variables. |
| **SQL Injection** | PASSED | Parameterized queries used exclusively throughout. |
| **Cross-Site Scripting (XSS)** | PASSED | Modern DOM textContent rendering; no unsafe `innerHTML` injection of unsanitized user inputs. |
| **Transactional Outbox Security** | PASSED | At-least-once delivery with message deduplication preventing replay attacks. |

## 3. Production Deployment Guidelines

1. **Database Credentials:** Configure distinct non-default credentials for PostgreSQL in production (`POSTGRES_PASSWORD`).
2. **TLS / HTTPS:** Terminate SSL/TLS at the reverse proxy (Nginx / Cloudflare / AWS ALB) before routing to the FastAPI backend.
3. **RabbitMQ Security:** Enforce encrypted AMQPS (`amqps://`) with dedicated vhost permissions in production environments.
