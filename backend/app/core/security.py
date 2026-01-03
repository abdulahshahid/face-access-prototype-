import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt
from core.config import settings
import secrets
import string

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

# core/security.py
from datetime import datetime, timedelta
from jose import jwt
from core.config import settings

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def verify_access_token(token: str):
    """Verify JWT access token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None


def generate_invite_code(length: int = 8) -> str:
    """Generates a secure random alphanumeric invite code."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
