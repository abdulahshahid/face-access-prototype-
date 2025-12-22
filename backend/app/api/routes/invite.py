from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from app.db.session import get_db
from app.models.attendee import Attendee
from app.models.embedding import InviteResponse
from app.utils.crypto import generate_random_string

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-invite/{attendee_id}", response_model=InviteResponse)
async def generate_invite(
    attendee_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate invitation link for attendee
    """
    try:
        # Find attendee
        attendee = db.query(Attendee).filter(Attendee.id == attendee_id).first()
        
        if not attendee:
            raise HTTPException(status_code=404, detail="Attendee not found")
        
        if attendee.is_registered:
            raise HTTPException(status_code=400, detail="Attendee already registered")
        
        # Generate unique invitation ID and registration code
        invitation_id = generate_random_string(16)
        registration_code = generate_random_string(8)
        
        # Update attendee
        attendee.invitation_id = invitation_id
        attendee.registration_code = registration_code
        attendee.invitation_expires_at = datetime.utcnow() + timedelta(days=7)
        attendee.status = "invited"
        
        db.commit()
        
        # Generate invitation URL (frontend will handle this)
        invitation_url = f"/register?invite={invitation_id}&code={registration_code}"
        
        logger.info(f"✅ Generated invite for attendee {attendee_id}")
        
        return InviteResponse(
            status="success",
            message="Invitation generated successfully",
            invitation_url=invitation_url,
            registration_code=registration_code
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite generation error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-invite")
async def bulk_invite(
    attendee_ids: list[int],
    db: Session = Depends(get_db)
):
    """
    Generate invitations for multiple attendees
    """
    results = []
    
    for attendee_id in attendee_ids:
        try:
            result = await generate_invite(attendee_id, db)
            results.append({
                "attendee_id": attendee_id,
                "status": "success",
                "invitation_code": result.registration_code
            })
        except Exception as e:
            results.append({
                "attendee_id": attendee_id,
                "status": "error",
                "error": str(e)
            })
    
    return {"results": results}