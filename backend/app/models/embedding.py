# app/models/embedding.py
from sqlalchemy import Column, String, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship
from pydantic import BaseModel as PydanticBase
from typing import Optional
from app.db.base import Base, BaseModel

class FaceEmbedding(Base, BaseModel):
    __tablename__ = "face_embeddings"

    attendee_id = Column(Integer, ForeignKey("attendees.id"), nullable=False)
    embedding_id = Column(String, unique=True, nullable=False)
    confidence = Column(Float, nullable=False)

    attendee = relationship("Attendee", backref="embeddings")

class AccessCheckResponse(PydanticBase):
    status: str
    message: str
    confidence: float
    matched_attendee_id: Optional[int] = None

class RegistrationResponse(PydanticBase):
    status: str
    message: str
    attendee_id: Optional[int] = None

class InviteResponse(PydanticBase):
    status: str
    message: str
    invitation_url: Optional[str] = None
    registration_code: Optional[str] = None

class CSVUploadResponse(PydanticBase):
    status: str
    message: str
    attendees_processed: int
    errors: list = []
