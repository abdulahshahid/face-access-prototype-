import hashlib
import secrets

def generate_random_string(length: int = 12) -> str:
    """Generate a random alphanumeric string"""
    return secrets.token_urlsafe(length)[:length]

def hash_string(text: str) -> str:
    """Create SHA256 hash of string"""
    return hashlib.sha256(text.encode()).hexdigest()

def verify_hash(text: str, hash_value: str) -> bool:
    """Verify text matches hash"""
    return hash_string(text) == hash_value