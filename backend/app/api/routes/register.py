from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import face_recognition
import cv2
import numpy as np
import logging
from db.session import get_db
from models.attendee import Attendee
from core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Qdrant Client
qdrant = QdrantClient(url=settings.QDRANT_URL)
COLLECTION_NAME = "faces"

# --- FIXED INITIALIZATION LOGIC ---
# Check if collection exists, create only if missing.
try:
    qdrant.get_collection(COLLECTION_NAME)
except Exception:
    try:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE)
        )
    except Exception as e:
        # If the error message says "already exists", we can safely ignore it.
        if "already exists" in str(e) or "Conflict" in str(e):
            pass 
        else:
            # If it's a different error, we still want to crash so we know about it.
            logger.error(f"Failed to create collection: {e}")
            raise e
# ----------------------------------

@router.post("/register")
async def register_face(
    invite_code: str = Form(...),
    photo: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Register a face using an invite code.
    """
    try:
        # 1. Validate User
        attendee = db.query(Attendee).filter(Attendee.invite_code == invite_code).first()
        if not attendee:
            raise HTTPException(status_code=404, detail="Invalid invite code")
        
        if attendee.status == "registered":
            raise HTTPException(status_code=400, detail="User already registered")

        # 2. Process Image
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 3. Detect Face
        face_locations = face_recognition.face_locations(rgb_image)
        if not face_locations:
            raise HTTPException(status_code=400, detail="No face detected. Please try again.")
        
        if len(face_locations) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected. Only one person allowed.")

        # Get 128-d face encoding
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not face_encodings:
            raise HTTPException(status_code=400, detail="Could not extract features from face.")
            
        embedding = face_encodings[0].tolist()

        # 4. Save to Qdrant
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=attendee.id,
                    vector=embedding,
                    payload={
                        "name": attendee.name,
                        "email": attendee.email,
                        "invite_code": attendee.invite_code
                    }
                )
            ]
        )

        # 5. Update Status
        attendee.status = "registered"
        db.commit()

        logger.info(f"✅ Successfully registered face for {attendee.name} ({attendee.email})")

        return {
            "status": "success",
            "message": f"Welcome {attendee.name}, registration complete!",
            "attendee_id": attendee.id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
