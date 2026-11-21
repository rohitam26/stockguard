# ADR 005: JWT Authentication, RBAC & Refresh Token Rotation

## Status
Accepted

## Context
Securing API endpoints requires authentication, role enforcement, and secure token lifecycle management without storing passwords in plaintext or exposing session tokens to replay attacks.

## Decision
Implement a layered security model:
1. **Password Hashing:** Passwords hashed with `bcrypt` (12 rounds) with Argon2 verification support. Plaintext passwords are never stored.
2. **Stateless Access Tokens:** Short-lived JWTs (30 minutes) carrying subject ID, email, and role.
3. **Stateful Refresh Token Rotation:** Refresh tokens stored as SHA-256 hashes in `refresh_tokens`. Every refresh invalidates the old token and issues a new pair, mitigating replay attacks.
4. **Role-Based Access Control (RBAC):** Hierarchical role evaluation (`ADMIN`, `INVENTORY_MANAGER`, `CUSTOMER`, `SERVICE`).
5. **IDOR Prevention:** Route-level checks ensure customers can only access orders and resources they own.
6. **Rate Limiting:** Sliding-window rate limiter protecting auth and sensitive endpoints.

## Consequences
- **Positive:** Defense-in-depth protection, zero plaintext credential storage, resilient token rotation.
- **Negative:** Database lookup required during token refresh and revocation.
