# app/api/routes/upload_csv.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import csv, io
from app.db.session import get_db
from app.models.attendee import Attendee
from app.models.embedding import CSVUploadResponse

router = APIRouter()

@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV allowed")

    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    processed, errors = 0, []

    for i, row in enumerate(reader, 1):
        try:
            if not row.get("name") or not row.get("email"):
                errors.append(f"Row {i}: missing fields")
                continue
            if db.query(Attendee).filter(Attendee.email == row["email"]).first():
                continue
            db.add(Attendee(name=row["name"], email=row["email"], dni=row.get("dni")))
            processed += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    db.commit()
    return CSVUploadResponse(
        status="success",
        message="CSV uploaded",
        attendees_processed=processed,
        errors=errors,
    )
