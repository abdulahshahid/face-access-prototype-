from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from db.base import Base

class Attendee(Base):
    __tablename__ = "attendees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    dni = Column(String, unique=True, index=True, nullable=True)
    
    # This is the column that was missing
    invite_code = Column(String, unique=True, index=True) 
    
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
