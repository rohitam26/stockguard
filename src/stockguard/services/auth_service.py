import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from stockguard.config import get_settings
from stockguard.models.user import User, RefreshToken
from stockguard.schemas.auth import UserRegisterRequest, TokenResponse
from stockguard.security.password import hash_password, verify_password
from stockguard.security.tokens import create_access_token, generate_refresh_token, hash_token

logger = logging.getLogger("stockguard.services.auth_service")
settings = get_settings()


class AuthenticationException(Exception):
    pass


class UserAlreadyExistsException(Exception):
    pass


class InvalidTokenException(Exception):
    pass


class AuthService:
    @staticmethod
    def register_user(db: Session, req: UserRegisterRequest) -> User:
        """Register a new user account with secure password hashing."""
        existing = db.execute(
            select(User).where(User.email == req.email.lower().strip())
        ).scalar_one_or_none()
        if existing:
            raise UserAlreadyExistsException(f"User with email '{req.email}' already exists.")

        hashed_pwd = hash_password(req.password)
        user = User(
            email=req.email.lower().strip(),
            hashed_password=hashed_pwd,
            full_name=req.full_name,
            role=req.role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Registered user %s with role %s", user.email, user.role.value)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Authenticate user credentials."""
        user = db.execute(
            select(User).where(User.email == email.lower().strip())
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            logger.warning("Failed login attempt for email: %s", email)
            raise AuthenticationException("Invalid email or password")

        if not user.is_active:
            raise AuthenticationException("User account is deactivated")

        return user

    @staticmethod
    def issue_tokens(db: Session, user: User) -> TokenResponse:
        """Generate access token and store rotated refresh token."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        access_token, expires_in = create_access_token(
            subject=user.id, role=role_str, email=user.email
        )

        raw_refresh = generate_refresh_token()
        token_hash = hash_token(raw_refresh)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_record = RefreshToken(
            user_id=user.id, token_hash=token_hash, expires_at=expires_at, revoked=False
        )
        db.add(refresh_record)
        db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="Bearer",
            expires_in=expires_in,
            user_id=user.id,
            email=user.email,
            role=role_str,
        )

    @staticmethod
    def rotate_refresh_token(db: Session, refresh_token_str: str) -> TokenResponse:
        """
        Rotates refresh token: marks old token revoked and issues a fresh pair.
        Prevents replay attacks.
        """
        token_hash = hash_token(refresh_token_str)
        token_record = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

        if not token_record or token_record.revoked:
            logger.warning("Refresh token rotation rejected: token not found or already revoked.")
            raise InvalidTokenException("Invalid or revoked refresh token")

        now = datetime.now(timezone.utc)
        if token_record.expires_at < now:
            logger.warning("Refresh token expired for user %s", token_record.user_id)
            raise InvalidTokenException("Refresh token has expired")

        user = db.get(User, token_record.user_id)
        if not user or not user.is_active:
            raise AuthenticationException("User account is invalid or deactivated")

        # Invalidate old token (Rotation)
        token_record.revoked = True
        db.flush()

        # Issue new token pair
        return AuthService.issue_tokens(db, user)

    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token_str: str) -> bool:
        """Revoke a refresh token (logout)."""
        token_hash = hash_token(refresh_token_str)
        token_record = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()

        if token_record and not token_record.revoked:
            token_record.revoked = True
            db.commit()
            return True
        return False
