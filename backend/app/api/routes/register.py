from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
from datetime import datetime
from app.db.session import get_db
from app.models.attendee import Attendee
from app.models.embedding import RegistrationResponse
from app.services.face_detection import face_detection_service
from app.services.liveness import liveness_service
from app.services.face_embedding import face_embedding_service
from app.services.vector_store import vector_store

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/register", response_model=RegistrationResponse)
async def register_attendee(
    invitation_id: str = Form(...),
    registration_code: str = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Register attendee using invitation code and facial photo
    """
    try:
        # Validate invitation
        attendee = db.query(Attendee).filter(
            Attendee.invitation_id == invitation_id,
            Attendee.registration_code == registration_code,
            Attendee.is_registered == False
        ).first()
        
        if not attendee:
            raise HTTPException(status_code=400, detail="Invalid or expired invitation")
        
        if attendee.invitation_expires_at and attendee.invitation_expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invitation expired")
        
        # Read image
        image_bytes = await photo.read()
        
        # Validate single face
        has_single_face = await face_detection_service.validate_single_face(image_bytes)
        if not has_single_face:
            raise HTTPException(
                status_code=400,
                detail="No valid face detected or multiple faces found"
            )
        
        # Basic liveness check
        is_live, liveness_confidence, reason = await liveness_service.check_liveness(image_bytes)
        if not is_live:
            raise HTTPException(
                status_code=400,
                detail=f"Liveness check failed: {reason}"
            )
        
        # Generate facial embedding
        embedding = await face_embedding_service.generate_embedding(image_bytes)
        if embedding is None:
            raise HTTPException(
                status_code=400,
                detail="Could not generate facial embedding"
            )
        
        # Store embedding in vector database
        embedding_id = await vector_store.store_embedding(attendee.id, embedding)
        
        # Update attendee as registered
        attendee.is_registered = True
        attendee.registration_date = datetime.utcnow()
        attendee.status = "registered"
        
        db.commit()
        
        logger.info(f"✅ Registered attendee {attendee.name} (ID: {attendee.id})")
        
        return RegistrationResponse(
            status="success",
            message="Registration successful",
            attendee_id=attendee.id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
