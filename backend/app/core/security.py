import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt
from app.core.config import settings

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token (for organizer/admin if needed)"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

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
