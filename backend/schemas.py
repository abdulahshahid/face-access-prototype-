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
    invite_code: Optional[str] = None  # Make this optional since QR users don't have invite codes
    status: str
    created_at: datetime
    qr_enabled: Optional[bool] = None
    has_biometric: Optional[bool] = None
    last_access_at: Optional[datetime] = None
    access_method: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class BatchAttendeeResult(BaseModel):
    name: str
    email: str
    invite_code: Optional[str] = None  # Make this optional too

# This model should NOT inherit from AttendeeResult
class BatchQRResult(BaseModel):
    name: str
    email: str
    qr_code_data: str
    qr_url: str
    id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

# This should use BatchQRResult, not BatchAttendeeResult
class BatchQRUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]
    results: List[BatchQRResult]  # Make sure this is BatchQRResult

# This is for regular attendees (with invite codes)
class BatchUploadResponse(BaseModel):
    total_processed: int
    success_count: int
    skipped_emails: List[str]
    results: List[BatchAttendeeResult]  # This requires invite_code


class GenerateQRCodesRequest(BaseModel):
    emails: List[str]


class QRVerificationRequest(BaseModel):
    qr_data: str  # The scanned QR code data