from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

class AttendeeBase(BaseModel):
    name: str
    email: EmailStr
    
class AttendeeCreate(AttendeeBase):
    pass

class AttendeeResult(BaseModel):
    name: str
    email: str
    invite_code: str

class BatchUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]
    results: List[AttendeeResult]  # Add th