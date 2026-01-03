# core/security.py
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
import jwt
from jose import jwt as jose_jwt
from core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_registration_code() -> str:
    """Generate unique registration code"""
    return secrets.token_urlsafe(8)[:8].upper()

def generate_invitation_id() -> str:
    """Generate unique invitation ID"""
    return secrets.token_urlsafe(16)[:16]

def hash_dni(dni: str) -> str:
    """Hash DNI for privacy (one-way hash)"""
    salt = settings.SECRET_KEY[:8]
    return hashlib.sha256(f"{salt}{dni}".encode()).hexdigest()

def create_access_token(data: dict):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jose_jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

def verify_access_token(token: str):
    """Verify JWT access token"""
    try:
        payload = jose_jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jose_jwt.JWTError:
        return None

def generate_invite_code(length: int = 8) -> str:
    """Generates a secure random alphanumeric invite code."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# ============================================================================
# PASSWORD HASHING FUNCTIONS (for admin authentication)
# ============================================================================

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)