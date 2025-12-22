from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import csv
import io
import logging
from db.session import get_db
from models.attendee import Attendee
# Removed CSVUploadResponse to allow flexible JSON return
from utils.crypto import generate_random_string

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-csv")
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
        results = []  # <--- COLLECTS DATA FOR FRONTEND

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

                # Generate Invite Code
                invite_code = generate_random_string(8).upper()

                # Create new attendee
                attendee = Attendee(
                    name=row['name'],
                    email=row['email'],
                    dni=row.get('dni'),
                    invite_code=invite_code, # <--- SAVING THE CODE
                    status="pending"
                )

                db.add(attendee)
                attendees_processed += 1
                
                # Add to results list
                results.append({
                    "name": row['name'],
                    "email": row['email'],
                    "invite_code": invite_code
                })

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        # Commit all attendees
        db.commit()

        logger.info(f"✅ Processed {attendees_processed} attendees from CSV")

        # Return the collected results
        return {
            "status": "success",
            "message": f"CSV uploaded successfully",
            "total_processed": attendees_processed,
            "results": results,  # <--- FRONTEND NEEDS THIS
            "errors": errors
        }

    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
