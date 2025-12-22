from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import csv
import io
import logging
from db.session import get_db
from models.attendee import Attendee
from models.embedding import CSVUploadResponse
from utils.crypto import generate_random_string

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload CSV file with attendee data
    CSV format: name,email,dni (optional)
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Read CSV content
        content = await file.read()
        text_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(text_content))
        
        attendees_processed = 0
        errors = []
        
        # Process each row
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                # Validate required fields
                if not row.get('name') or not row.get('email'):
                    errors.append(f"Row {row_num}: Missing name or email")
                    continue
                
                # Check if attendee already exists
                existing = db.query(Attendee).filter(
                    (Attendee.email == row['email']) | 
                    (Attendee.dni == row.get('dni'))
                ).first()
                
                if existing:
                    logger.info(f"Attendee {row['email']} already exists, skipping")
                    continue
                
                # Create new attendee
                attendee = Attendee(
                    name=row['name'],
                    email=row['email'],
                    dni=row.get('dni'),
                    status="pending"
                )
                
                db.add(attendee)
                attendees_processed += 1
            
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # Commit all attendees
        db.commit()
        
        logger.info(f"✅ Processed {attendees_processed} attendees from CSV")
        
        return CSVUploadResponse(
            status="success",
            message=f"CSV uploaded successfully",
            attendees_processed=attendees_processed,
            errors=errors
        )
    
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))