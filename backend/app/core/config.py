from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Face Access Control"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # Added this field

    # Database
    DATABASE_URL: str = "postgresql://faceaccess:1234@postgres:5432/faceaccess"
    POSTGRES_PASSWORD: str = "1234"  # Added this field

    # Qdrant Vector Database
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "faces"

    # Security
    SECRET_KEY: str = "ea03da06bae3cf7a79d92303f6d0f3348ef0fb15f25b2e8183f63aca93f9db7c"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Face Matching
    FACE_MATCH_THRESHOLD: float = 0.6  # Cosine similarity threshold

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/jpg"]

    # Invitation
    INVITATION_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Critical fix: allows extra env vars without crashing

settings = Settings()
