from fastapi import APIRouter, UploadFile, File, HTTPException
import face_recognition
import cv2
import numpy as np
import logging
from core.config import settings
from qdrant_client import QdrantClient

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Qdrant
qdrant = QdrantClient(url=settings.QDRANT_URL)
COLLECTION_NAME = "faces"

@router.post("/access-check")
async def access_check(photo: UploadFile = File(...)):
    """
    Production Access Check: Fast & Efficient
    """
    try:
        # 1. Read Image
        content = await photo.read()
        nparr = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {"status": "ERROR", "message": "Invalid image format"}

        # 2. Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 3. Detect Face
        # We keep upsample=1 for speed. If you need more range, set to 2.
        face_locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1)
        
        if not face_locations:
            return {"status": "ERROR", "message": "No face detected. Please look at the camera."}

        # 4. Generate Embedding
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not face_encodings:
             return {"status": "ERROR", "message": "Face unclear."}

        # 5. Search Qdrant
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=face_encodings[0].tolist(),
            limit=1,
            score_threshold=0.5
        )

        if not search_result:
            return {
                "status": "DENIED",
                "message": "Access Denied",
                "confidence": 0
            }

        # Success
        match = search_result[0]
        confidence = match.score * 100
        logger.info(f"✅ Access Granted: {match.payload['name']} ({confidence:.1f}%)")

        return {
            "status": "OK",
            "message": f"Welcome, {match.payload['name']}!",
            "user": match.payload,
            "confidence": confidence
        }

    except Exception as e:
        logger.error(f"Access error: {str(e)}")
        return {"status": "ERROR", "message": "System Error"}
