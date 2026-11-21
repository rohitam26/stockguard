import logging
from typing import Callable
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from stockguard.database import get_db
from stockguard.models.user import User, UserRole
from stockguard.security.tokens import decode_access_token

logger = logging.getLogger("stockguard.security.deps")

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates JWT Bearer token and returns authenticated User entity.
    Raises HTTP 401 if token is missing, invalid, expired, or user is inactive.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token expired"'
            },
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated"
        )

    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns authenticated user if valid token present, otherwise None."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Role-Based Access Control (RBAC) dependency factory.
    Verifies that the authenticated user possesses at least one of the allowed roles.
    Raises HTTP 403 Forbidden on authorization failure.
    """
    allowed_role_values = {r.value if hasattr(r, "value") else str(r) for r in allowed_roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_val = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        # ADMIN role always passes authorization checks (superuser)
        if user_role_val == UserRole.ADMIN.value or user_role_val in allowed_role_values:
            return current_user

        logger.warning(
            "Access denied for user %s (role: %s). Required roles: %s",
            current_user.id,
            user_role_val,
            allowed_role_values,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires one of the following roles: {', '.join(allowed_role_values)}",
        )

    return role_checker


def check_resource_ownership(
    resource_owner_id: str, current_user: User, resource_name: str = "resource"
):
    """
    IDOR Protection: ensures that non-admin users can only access resources they own.
    """
    user_role_val = (
        current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    )
    if user_role_val in (UserRole.ADMIN.value, UserRole.SERVICE.value):
        return
    if str(resource_owner_id) != str(current_user.id):
        logger.warning(
            "IDOR violation prevented: User %s attempted to access %s owned by %s",
            current_user.id,
            resource_name,
            resource_owner_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to access this {resource_name}",
        )
