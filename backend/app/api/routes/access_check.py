from fastapi import APIRouter, UploadFile, File
import face_recognition
import cv2
import numpy as np
import logging
import math
from core.config import settings
from qdrant_client import QdrantClient

COLLECTION_NAME = settings.QDRANT_COLLECTION

router = APIRouter()
logger = logging.getLogger(__name__)

qdrant = QdrantClient(url=settings.QDRANT_URL)

@router.post("/access-check")
async def access_check(photo: UploadFile = File(...)):
    try:
        # 1. Image Pre-processing
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {"status": "ERROR", "message": "Invalid image format"}

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 2. Face Detection
        face_locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1)
        if not face_locations:
            return {"status": "ERROR", "message": "No face detected"}

        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not face_encodings:
             return {"status": "ERROR", "message": "Face unclear"}

        # 3. Query Qdrant (No threshold here, we do it manually for precision)
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=face_encodings[0].tolist(),
            limit=1
        )

        if not search_result:
            return {"status": "DENIED", "message": "No match found in database", "confidence": 0}

        match = search_result[0]

        # 4. Calculate Euclidean Distance
        # Qdrant with EUCLID returns "score" as negative squared distance.
        # Formula: distance = sqrt(-score)
        try:
            # Ensure score is negative before sqrt (Qdrant specific behavior for sorting)
            if match.score > 0:
                # Fallback in case a different Qdrant version is used
                distance = match.score 
            else:
                distance = math.sqrt(-match.score)
        except ValueError:
             # Safety net
             distance = 1.0 

        # 5. Authorization Logic
        # 0.50 = Very Strict
        # 0.55 = Strict (Recommended)
        # 0.60 = Standard (dlib default)
        THRESHOLD = 0.55

        if distance > THRESHOLD:
            logger.warning(f"Access Denied. Distance: {distance} > Threshold {THRESHOLD}")
            return {
                "status": "DENIED",
                "message": "Access Denied: Face not recognized",
                "confidence": 0,
                "debug_dist": distance
            }

        # 6. Success - Calculate User-Friendly Confidence
        # This maps the distance (0 to 0.6) to a percentage (100% to 0%)
        confidence = max(0, (1.0 - (distance / 0.6)) * 100)
        
        return {
            "status": "OK",
            "message": f"Welcome, {match.payload['email']}!",
            "user": match.payload,
            "confidence": round(confidence, 2)
        }

    except Exception as e:
        logger.error(f"Access error: {str(e)}")
        return {"status": "ERROR", "message": "System Error"}