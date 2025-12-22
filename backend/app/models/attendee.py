from sqlalchemy import Column, String, Boolean, Integer, DateTime
from db.base import Base, BaseModel

class Attendee(Base, BaseModel):
    __tablename__ = "attendees"

    # CSV fields
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    dni = Column(String, unique=True, nullable=True)

    # Registration fields
    registration_date = Column(DateTime, nullable=True)
    registration_code = Column(String, unique=True, nullable=True)
    is_registered = Column(Boolean, default=False, nullable=False)

    # Invitation
    invitation_id = Column(String, unique=True, nullable=True)
    invitation_expires_at = Column(DateTime, nullable=True)

    # Status
    status = Column(String, default="pending", nullable=False)

    def __repr__(self):
        return f"<Attendee {self.name} ({self.email})>"
