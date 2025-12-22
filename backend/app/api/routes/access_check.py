from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from models.attendee import Attendee
from models.embedding import AccessCheckResponse
from services.face_detection import face_detection_service
from services.liveness import liveness_service
from services.matching import face_matching_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/access-check", response_model=AccessCheckResponse)
async def check_access(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Check if face matches any registered attendee
    Returns OK or NO with confidence level
    """
    try:
        # Read image
        image_bytes = await photo.read()
        
        # Validate single face
        has_single_face = await face_detection_service.validate_single_face(image_bytes)
        if not has_single_face:
            return AccessCheckResponse(
                status="NO",
                message="No valid face detected or multiple faces found",
                confidence=0.0
            )
        
        # Basic liveness check
        is_live, liveness_confidence, reason = await liveness_service.check_liveness(image_bytes)
        if not is_live:
            return AccessCheckResponse(
                status="NO",
                message=f"Liveness check failed: {reason}",
                confidence=liveness_confidence * 100
            )
        
        # Find matching face
        matched_id, confidence, is_match = await face_matching_service.find_match(image_bytes)
        
        if is_match and matched_id:
            # Verify attendee is registered
            attendee = db.query(Attendee).filter(Attendee.id == matched_id).first()
            
            if attendee and attendee.is_registered:
                logger.info(f"Access granted for attendee {attendee.name} (ID: {attendee.id})")
                return AccessCheckResponse(
                    status="OK",
                    message=f"Access granted: {attendee.name}",
                    confidence=confidence,
                    matched_attendee_id=matched_id
                )
        
        logger.info(f"Access denied - no match found (confidence: {confidence:.2f}%)")
        return AccessCheckResponse(
            status="NO",
            message="No matching face found",
            confidence=confidence
        )
    
    except Exception as e:
        logger.error(f"Access check error: {str(e)}")
        return AccessCheckResponse(
            status="NO",
            message=f"Error: {str(e)}",
            confidence=0.0
        )