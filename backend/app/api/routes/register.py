# app/api/routes/register.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.models.attendee import Attendee
from app.models.embedding import RegistrationResponse
from app.services.face_detection import face_detection_service
from app.services.liveness import liveness_service
from app.services.face_embedding import face_embedding_service
from app.services.vector_store import vector_store

router = APIRouter()

@router.post("/register", response_model=RegistrationResponse)
async def register_attendee(
    invitation_id: str = Form(...),
    registration_code: str = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    attendee = db.query(Attendee).filter(
        Attendee.invitation_id == invitation_id,
        Attendee.registration_code == registration_code,
        Attendee.is_registered == False,
    ).first()

    if not attendee or attendee.invitation_expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid invite")

    img = await photo.read()

    if not await face_detection_service.validate_single_face(img):
        raise HTTPException(400, "Invalid face")

    live, _, _ = await liveness_service.check_liveness(img)
    if not live:
        raise HTTPException(400, "Liveness failed")

    emb = await face_embedding_service.generate_embedding(img)
    if emb is None:
        raise HTTPException(400, "Embedding failed")

    await vector_store.store_embedding(attendee.id, emb)

    attendee.is_registered = True
    attendee.registration_date = datetime.utcnow()
    attendee.status = "registered"
    db.commit()

    return RegistrationResponse(
        status="success",
        message="Registered",
        attendee_id=attendee.id,
    )
