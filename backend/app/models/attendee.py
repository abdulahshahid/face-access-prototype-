from sqlalchemy import Column, Integer, String, DateTime, Boolean, LargeBinary
from sqlalchemy.sql import func
from db.base import Base

class Attendee(Base):
    __tablename__ = "attendees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    dni = Column(String, unique=True, index=True, nullable=True)
    invite_code = Column(String, unique=True, index=True)
    
    # NEW: QR Code fields
    qr_code_data = Column(String, unique=True, index=True, nullable=True)  # The unique token/data in QR
    qr_image_url = Column(String, nullable=True)  # URL or path to QR image
    qr_enabled = Column(Boolean, default=True)  # Can they use QR?
    
    # NEW: Biometric fields
    has_biometric = Column(Boolean, default=False)  # Do they have face registered?
    face_embedding_id = Column(String, nullable=True)  # Qdrant point ID
    
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_access_at = Column(DateTime(timezone=True), nullable=True)
    access_method = Column(String, nullable=True)  # "face" or "qr" - last used method