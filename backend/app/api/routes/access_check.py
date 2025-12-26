from fastapi import APIRouter, UploadFile, File, HTTPException
import face_recognition
import cv2
import numpy as np
import logging
from core.config import settings
from qdrant_client import QdrantClient

router = APIRouter()
logger = logging.getLogger(__name__)

qdrant = QdrantClient(url=settings.QDRANT_URL)
COLLECTION_NAME = "faces"

@router.post("/access-check")
async def access_check(photo: UploadFile = File(...)):
    try:
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {"status": "ERROR", "message": "Invalid image format"}

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Fast detection
        face_locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1)
        
        if not face_locations:
            return {"status": "ERROR", "message": "No face detected"}

        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not face_encodings:
             return {"status": "ERROR", "message": "Face unclear"}

        # --- FIX: Stricter Threshold (0.65) ---
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=face_encodings[0].tolist(),
            limit=1,
            score_threshold=0.65
        )

        if not search_result:
            return {
                "status": "DENIED",
                "message": "Access Denied: Face not recognized",
                "confidence": 0
            }

        match = search_result[0]
        confidence = match.score * 100
        
        return {
            "status": "OK",
            "message": f"Welcome, {match.payload['email']}!",
            "user": match.payload,
            "confidence": confidence
        }

    except Exception as e:
        logger.error(f"Access error: {str(e)}")
        return {"status": "ERROR", "message": "System Error"}
