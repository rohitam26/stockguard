import time
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from stockguard.main import app
from stockguard.database import get_session_factory
from stockguard.models.user import User, UserRole
from stockguard.security.tokens import create_access_token
from stockguard.security.password import verify_password
from stockguard.security.deps import check_resource_ownership
from stockguard.security.rate_limiter import InMemoryRateLimiter
from fastapi import HTTPException

client = TestClient(app)


def test_user_registration_and_password_hashing():
    SessionFactory = get_session_factory()
    email = f"test_{int(time.time()*1000)}@example.com"
    pwd = "SecurePassword123!"

    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": pwd,
        "full_name": "Test User",
        "role": "CUSTOMER"
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == email
    assert data["role"] == "CUSTOMER"
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify directly in database that password is NOT plaintext
    with SessionFactory() as db:
        user = db.get(User, data["id"])
        assert user is not None
        assert user.hashed_password != pwd
        assert user.hashed_password.startswith("$2b$") or user.hashed_password.startswith("$argon2")
        assert verify_password(pwd, user.hashed_password) is True


def test_user_login_success_and_failure():
    email = f"login_{int(time.time()*1000)}@example.com"
    pwd = "ValidPassword123!"

    # Register
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": pwd,
        "full_name": "Login Tester"
    })
    assert reg_resp.status_code == 201

    # Login with wrong password
    bad_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword!"
    })
    assert bad_resp.status_code == 401
    assert "Invalid email or password" in bad_resp.json()["detail"]

    # Login with correct password
    good_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": pwd
    })
    assert good_resp.status_code == 200
    token_data = good_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "Bearer"
    assert token_data["email"] == email


def test_jwt_access_and_expiration():
    email = f"jwt_{int(time.time()*1000)}@example.com"
    pwd = "Password123!"

    client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user_id"]

    # Access /auth/me with valid token
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # Access with no token
    no_token_resp = client.get("/api/v1/auth/me")
    assert no_token_resp.status_code == 401

    # Access with invalid signature / malformed token
    bad_token_resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert bad_token_resp.status_code == 401

    # Expired token test
    expired_token, _ = create_access_token(
        subject=user_id,
        role="CUSTOMER",
        email=email,
        expires_delta=timedelta(seconds=-10)  # already expired
    )
    exp_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert exp_resp.status_code == 401
    assert "expired" in exp_resp.json()["detail"].lower()


def test_refresh_token_rotation_and_revocation():
    email = f"refresh_{int(time.time()*1000)}@example.com"
    pwd = "Password123!"

    client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    first_refresh = login_resp.json()["refresh_token"]

    # Rotate refresh token
    rotate_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotate_resp.status_code == 200
    new_refresh = rotate_resp.json()["refresh_token"]
    assert new_refresh != first_refresh

    # Attempting replay attack with already-used refresh token must be rejected
    replay_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert replay_resp.status_code == 401

    # Explicit revocation (logout)
    revoke_resp = client.post("/api/v1/auth/revoke", json={"refresh_token": new_refresh})
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked"] is True

    # Attempting to refresh after revocation must fail
    after_revoke_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after_revoke_resp.status_code == 401


def test_idor_protection_enforcement():
    customer_a = User(id="cust-a-uuid", email="a@test.com", hashed_password="x", role=UserRole.CUSTOMER)
    customer_b = User(id="cust-b-uuid", email="b@test.com", hashed_password="x", role=UserRole.CUSTOMER)
    admin_user = User(id="admin-uuid", email="admin@test.com", hashed_password="x", role=UserRole.ADMIN)

    # Customer A accessing their own resource: Allowed
    check_resource_ownership(resource_owner_id="cust-a-uuid", current_user=customer_a, resource_name="order")

    # Admin accessing Customer A's resource: Allowed
    check_resource_ownership(resource_owner_id="cust-a-uuid", current_user=admin_user, resource_name="order")

    # Customer B attempting to access Customer A's resource: Rejected with 403 Forbidden
    with pytest.raises(HTTPException) as excinfo:
        check_resource_ownership(resource_owner_id="cust-a-uuid", current_user=customer_b, resource_name="order")
    assert excinfo.value.status_code == 403
    assert "permission" in str(excinfo.value.detail).lower()


def test_rate_limiter_unit():
    limiter = InMemoryRateLimiter(requests_limit=3, window_seconds=10)
    key = "test-user-ip"

    # First 3 requests pass
    for _ in range(3):
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False

    # 4th request in same window is limited
    limited, retry_after = limiter.is_rate_limited(key)
    assert limited is True
    assert retry_after > 0
