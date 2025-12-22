from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        
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