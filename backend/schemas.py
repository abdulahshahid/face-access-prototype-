from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

class AttendeeBase(BaseModel):
    name: str
    email: EmailStr
    
class AttendeeCreate(AttendeeBase):
    pass

class AttendeeResult(BaseModel):
    id: int
    name: str
    email: str
    dni: Optional[str] = None
    invite_code: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BatchAttendeeResult(BaseModel):
    name: str
    email: str
    invite_code: str

# FIXED: Remove inheritance from AttendeeResult since BatchQRResult doesn't have invite_code
class BatchQRResult(BaseModel):
    name: str
    email: str
    qr_code_data: str
    qr_url: str
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class BatchQRUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]
    results: List[BatchQRResult]

class BatchUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]
    results: List[BatchAttendeeResult]


class GenerateQRCodesRequest(BaseModel):
    emails: List[str]


class QRVerificationRequest(BaseModel):
    qr_data: str  # The scanned QR code data