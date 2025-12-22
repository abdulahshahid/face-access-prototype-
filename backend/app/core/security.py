# app/core/security.py
import hashlib, secrets, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings

def generate_registration_code() -> str:
    return secrets.token_urlsafe(8)[:8].upper()

def generate_invitation_id() -> str:
    return secrets.token_urlsafe(16)[:16]

def hash_dni(dni: str) -> str:
    return hashlib.sha256((settings.SECRET_KEY + dni).encode()).hexdigest()

def create_access_token(data: dict, expires: Optional[timedelta] = None):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + (expires or timedelta(hours=24))
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
