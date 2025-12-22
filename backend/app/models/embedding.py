from sqlalchemy import Column, String, Float, ForeignKey, Integer, DateTime
from sqlalchemy.orm import relationship
from pydantic import BaseModel as PydanticBase
from typing import Optional
from db.base import Base, BaseModel

# Database Models
class FaceEmbedding(Base, BaseModel):
    __tablename__ = "face_embeddings"
    
    attendee_id = Column(Integer, ForeignKey("attendees.id"), nullable=False)
    embedding_id = Column(String, unique=True, nullable=False)  # Qdrant point ID
    confidence = Column(Float, nullable=False)
    
    # Relationship
    attendee = relationship("Attendee", backref="embeddings")

# Pydantic Schemas
class AccessCheckResponse(PydanticBase):
    status: str  # "OK" or "NO"
    message: str
    confidence: float
    matched_attendee_id: Optional[int] = None

class RegistrationResponse(PydanticBase):
    status: str  # "success" or "error"
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
