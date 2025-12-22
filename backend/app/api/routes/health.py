from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text  # <--- IMPORTED text
from db.session import get_db
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Changed from "" to "/health" so the URL becomes /api/health
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection using text() wrapper
        db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
            "service": "face-access-control"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
