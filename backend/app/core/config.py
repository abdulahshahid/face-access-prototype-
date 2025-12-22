# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Face Access Control"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql://faceaccess:1234@postgres:5432/faceaccess"
    QDRANT_URL: str = "http://qdrant:6333"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    FACE_MATCH_THRESHOLD: float = 0.6

    class Config:
        env_file = ".env"

settings = Settings()
