import bcrypt
import logging

logger = logging.getLogger("stockguard.security.password")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with salt rounds."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt or argon2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        # Check if argon2 hash
        if hashed_password.startswith("$argon2"):
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError

            ph = PasswordHasher()
            try:
                return ph.verify(hashed_password, plain_password)
            except VerifyMismatchError:
                return False
        # Default: bcrypt
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning("Password verification error: %s", e)
        return False
