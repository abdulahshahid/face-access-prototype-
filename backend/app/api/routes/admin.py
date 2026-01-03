import io
import csv
import logging
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- 1. Imports from your Project Structure ---
from db.session import get_db
from models.attendee import Attendee

# Security & Logic
from core.deps import get_current_admin  # The JWT Auth Guard
from core.security import generate_invite_code
from core.qdrant_ops import qdrant_service  # The Vector DB Singleton

# Pydantic Schemas
from schemas import AttendeeResponse, BatchUploadResponse

# Initialize Router & Logger
router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. LIST ATTENDEES (With Search & Pagination)
# ==============================================================================
@router.get(
    "/attendees", 
    response_model=List[AttendeeResponse], 
    dependencies=[Depends(get_current_admin)]  # LOCKED 🔒
)
def get_attendees(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """
    Get all attendees with pagination.
    Optional: ?search=john to filter by name or email.
    """
    query = db.query(Attendee)
    
    if search:
        # Case-insensitive search for Name OR Email
        search_fmt = f"%{search}%"
        query = query.filter(
            (Attendee.email.ilike(search_fmt)) | 
            (Attendee.name.ilike(search_fmt))
        )
    
    # Sort by creation date (newest first is better for admins)
    users = query.order_by(Attendee.created_at.desc()).offset(skip).limit(limit).all()
    
    return users


# ==============================================================================
# 2. DELETE ATTENDEE (Strict Consistency: SQL + Vector DB)
# ==============================================================================
@router.delete(
    "/attendees/{user_id}", 
    dependencies=[Depends(get_current_admin)]  # LOCKED 🔒
)
def delete_attendee(user_id: int, db: Session = Depends(get_db)):
    """
    Hard Delete:
    1. Removes vector from Qdrant (prevent face access).
    2. Removes record from PostgreSQL.
    """
    # Step A: Check if user exists in SQL
    user = db.query(Attendee).filter(Attendee.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {user_id} not found"
        )
    
    email_backup = user.email # Keep for logging
    
    # Step B: Delete from Vector DB (Qdrant)
    # We prioritize this to ensure security (access revocation)
    vector_deleted = False
    try:
        vector_deleted = qdrant_service.delete_user_vector(user_id)
        if not vector_deleted:
             logger.warning(f"⚠️ Vector deletion returned False for user {user_id}. Vector might not have existed.")
    except Exception as e:
        # We generally continue to delete the SQL user even if Qdrant fails, 
        # but we log it as a CRITICAL sync error.
        logger.error(f"❌ CRITICAL: Failed to delete vector for {user_id}: {e}")

    # Step C: Delete from Relational DB (Postgres)
    try:
        db.delete(user)
        db.commit()
        
        logger.info(f"🗑️ [Admin] Deleted user {user_id} ({email_backup}). Vector Removed: {vector_deleted}")
        
        return {
            "status": "success", 
            "message": f"User {email_backup} deleted successfully.", 
            "vector_cleaned": vector_deleted
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ DB Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal Database Error during deletion."
        )


# ==============================================================================
# 3. BATCH CSV UPLOAD
# ==============================================================================
@router.post(
    "/upload-csv", 
    response_model=BatchUploadResponse, 
    dependencies=[Depends(get_current_admin)]  # LOCKED 🔒
)
async def upload_csv(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Bulk import users.
    Required CSV Header: 'email'
    Optional CSV Header: 'name'
    """
    # 1. Validate File Type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid file format. Please upload a .csv file."
        )

    # 2. Read File
    try:
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
    except Exception as e:
        logger.error(f"CSV Reading Error: {e}")
        raise HTTPException(status_code=400, detail="Could not read or decode CSV file.")
    
    # 3. Validate Headers
    headers = [h.lower().strip() for h in csv_reader.fieldnames or []]
    if 'email' not in headers:
         raise HTTPException(
             status_code=400, 
             detail=f"CSV is missing required 'email' column. Found: {headers}"
         )

    new_attendees = []
    skipped_emails = []
    
    # 4. Process Rows
    for row in csv_reader:
        clean_row = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        
        email = clean_row.get('email')
        name = clean_row.get('name', 'Unknown')

        if not email:
            continue

        # Check for existing user (SQL only is sufficient for this check)
        existing = db.query(Attendee).filter(Attendee.email == email).first()
        if existing:
            skipped_emails.append(email)
            continue

        # Create new record
        invite_code = generate_invite_code()
        attendee = Attendee(
            name=name,
            email=email,
            invite_code=invite_code,
            status="pending"
        )
        db.add(attendee)
        new_attendees.append(attendee)

    # 5. Commit Transaction
    try:
        db.commit()
        logger.info(f"✅ [Admin] Batch Import: {len(new_attendees)} created, {len(skipped_emails)} skipped.")
        
        return {
            "total_processed": len(new_attendees) + len(skipped_emails), 
            "success_count": len(new_attendees),
            "skipped_emails": skipped_emails
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Batch Upload Commit Failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database error while saving users."
        )