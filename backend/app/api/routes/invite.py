# app/api/routes/invite.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.session import get_db
from app.models.attendee import Attendee
from app.models.embedding import InviteResponse
from app.utils.crypto import generate_random_string

router = APIRouter()

@router.post("/generate-invite/{attendee_id}", response_model=InviteResponse)
async def generate_invite(attendee_id: int, db: Session = Depends(get_db)):
    attendee = db.query(Attendee).filter(Attendee.id == attendee_id).first()
    if not attendee or attendee.is_registered:
        raise HTTPException(400, "Invalid attendee")

    attendee.invitation_id = generate_random_string(16)
    attendee.registration_code = generate_random_string(8)
    attendee.invitation_expires_at = datetime.utcnow() + timedelta(days=7)
    attendee.status = "invited"
    db.commit()

    return InviteResponse(
        status="success",
        message="Invite generated",
        invitation_url=f"/register?invite={attendee.invitation_id}&code={attendee.registration_code}",
        registration_code=attendee.registration_code,
    )
