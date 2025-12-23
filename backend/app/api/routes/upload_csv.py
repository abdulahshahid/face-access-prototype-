import sys
import os

# --- FIX: Force Python to see the root 'backend' folder ---
sys.path.append('/app')
# ----------------------------------------------------------

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
# Now it should be able to find 'db' or 'app.db'
from db.session import get_db
from core.security import generate_invite_code
import csv
import io
import logging
from models.attendee import Attendee
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type")

    content = await file.read()
    decoded_content = content.decode('utf-8')
    
    csv_reader = csv.DictReader(io.StringIO(decoded_content))
    
    headers = [h.lower() for h in csv_reader.fieldnames or []]
    if 'email' not in headers:
         raise HTTPException(status_code=400, detail=f"CSV must have an 'email' header. Found: {headers}")

    new_attendees = []
    skipped_emails = []
    
    for row in csv_reader:
        clean_row = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        
        email = clean_row.get('email')
        name = clean_row.get('name', 'Unknown')

        if not email:
            continue

        existing = db.query(Attendee).filter(Attendee.email == email).first()
        
        if existing:
            logger.info(f"Attendee {email} already exists, skipping")
            skipped_emails.append(email)
            continue

        invite_code = generate_invite_code()
        attendee = Attendee(
            name=name,
            email=email,
            invite_code=invite_code,
            status="pending"
        )
        db.add(attendee)
        new_attendees.append({
            "name": name,
            "email": email,
            "invite_code": invite_code
        })

    try:
        db.commit()
        logger.info(f"✅ Processed {len(new_attendees)} new attendees")
        return {
            "total_processed": len(new_attendees), 
            "results": new_attendees,
            "skipped": skipped_emails
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database commit failed")
