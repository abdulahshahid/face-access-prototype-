from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

class AttendeeBase(BaseModel):
    name: str
    email: EmailStr
    
class AttendeeCreate(AttendeeBase):
    pass

class AttendeeResponse(AttendeeBase):
    id: int
    invite_code: str
    status: str  # pending, registered, blocked
    # created_at might be None if the DB field is nullable or missing
    created_at: Optional[datetime] = None

    # This tells Pydantic to read data from SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)

class BatchUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]