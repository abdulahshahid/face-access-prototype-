from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Face Access Control"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str = "postgresql://faceaccess:1234@postgres:5432/faceaccess"
    POSTGRES_PASSWORD: str = "1234"
    
    # Qdrant Vector Database
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "faces"
    
    # Face Recognition Settings - FIXED: Added type annotations and removed duplicates
    FACE_MATCH_THRESHOLD: float = 0.92  # CRITICAL: Increased from 0.6 to 0.92
    FACE_MIN_CONFIDENCE: float = 92.0   # CRITICAL: Increased from 70.0 to 92.0
    MIN_SCORE_GAP: float = 0.02         # Minimum gap between top matches
    
    # Performance Settings
    FACE_DETECTION_MODEL: str = "hog"  # "hog" for CPU, "cnn" for GPU
    NUM_JITTERS: int = 10  # FIXED: Increased from 1 to 10 for better accuracy
    UPSAMPLE_TIMES: int = 1  # For face detection
    
    # Security
    SECRET_KEY: str = "ea03da06bae3cf7a79d92303f6d0f3348ef0fb15f25b2e8183f63aca93f9db7c"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/jpg"]
    
    # Invitation
    INVITATION_EXPIRE_DAYS: int = 7
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allows extra env vars without crashing

settings = Settings()