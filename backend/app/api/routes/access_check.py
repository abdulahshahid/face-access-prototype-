from fastapi import APIRouter, UploadFile, File, HTTPException
import face_recognition
import cv2
import numpy as np
import logging
import time
from core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

COLLECTION_NAME = settings.QDRANT_COLLECTION

router = APIRouter()
logger = logging.getLogger(__name__)

qdrant = QdrantClient(url=settings.QDRANT_URL)

# --- UPDATED: Normalization function (same as in registration) ---
def normalize_vector(vector):
    """Normalize a vector to unit length for cosine similarity."""
    vector_array = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(vector_array)
    if norm == 0 or np.isnan(norm):
        logger.warning(f"Zero or NaN norm detected in access check vector")
        return vector
    normalized = (vector_array / norm).tolist()
    return normalized

@router.post("/access-check")
async def access_check(photo: UploadFile = File(...)):
    """
    Check if a face matches any registered face for access.
    """
    start_time = time.time()
    
    try:
        # 1. Read and validate image
        content = await photo.read()
        if len(content) == 0:
            return {"status": "ERROR", "message": "Empty image file"}
            
        nparr = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {"status": "ERROR", "message": "Invalid image format"}

        # 2. Convert to RGB and detect faces
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Fast detection for access control
        face_locations = face_recognition.face_locations(
            rgb_image, 
            number_of_times_to_upsample=1,  # Faster processing
            model="hog"  # Use HOG for faster CPU processing (use "cnn" for better accuracy)
        )
        
        if not face_locations:
            return {
                "status": "ERROR", 
                "message": "No face detected. Please ensure your face is clearly visible."
            }

        # 3. Check for multiple faces
        if len(face_locations) > 1:
            return {
                "status": "ERROR", 
                "message": "Multiple faces detected. Only one person can be verified at a time."
            }

        # 4. Extract face encoding
        face_encodings = face_recognition.face_encodings(
            rgb_image, 
            face_locations,
            num_jitters=1  # Reduce for speed, increase for accuracy
        )
        
        if not face_encodings:
            return {"status": "ERROR", "message": "Face unclear. Please try again with better lighting."}

        # 5. Normalize the query vector
        query_vector = normalize_vector(face_encodings[0].tolist())
        
        # DEBUG: Log vector statistics
        logger.info(f"🔬 Query vector norm: {np.linalg.norm(np.array(query_vector)):.6f}")
        logger.info(f"🔬 Vector first 5 values: {query_vector[:5]}")
        
        # 6. Search in Qdrant with DOT product
        threshold = getattr(settings, 'FACE_MATCH_THRESHOLD', 0.7)
        logger.info(f"🔬 Using threshold: {threshold}")
        
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=3,  # Get top 3 matches for verification
            score_threshold=threshold,
            with_payload=True,
            with_vectors=False
        )

        # DEBUG: Log search results
        logger.info(f"🔬 Number of results returned: {len(search_result)}")
        if search_result:
            logger.info(f"🔍 Match found: Score={search_result[0].score:.6f}, Threshold={threshold:.6f}")
            logger.info(f"🔍 All scores: {[round(r.score, 6) for r in search_result]}")
            logger.info(f"🔍 Best match user: {search_result[0].payload.get('email')}")
            logger.info(f"🔍 Score is {'ABOVE' if search_result[0].score >= threshold else 'BELOW'} threshold")
            
            # Calculate how much the score exceeds threshold
            score_diff = search_result[0].score - threshold
            logger.info(f"🔍 Score difference from threshold: {score_diff:.6f} ({score_diff*100:.2f}%)")

        # 7. Process results
        if not search_result:
            processing_time = time.time() - start_time
            logger.info(f"❌ Access denied: No match found ({processing_time:.2f}s)")
            return {
                "status": "DENIED",
                "message": "Access Denied: Face not recognized",
                "confidence": 0,
                "processing_time": f"{processing_time:.2f}s"
            }

        # Get best match
        match = search_result[0]
        confidence = match.score * 100  # Convert to percentage
        
        logger.info(f"🔍 Calculated confidence: {confidence:.2f}%")
        
        # 8. Secondary verification (ensure clear best match)
        if len(search_result) > 1:
            score_gap = match.score - search_result[1].score
            min_score_gap = getattr(settings, 'MIN_SCORE_GAP', 0.05)
            
            logger.info(f"🔍 Score gap between 1st and 2nd: {score_gap:.6f} (min required: {min_score_gap})")
            
            if score_gap < min_score_gap:
                # Multiple close matches - ambiguous result
                processing_time = time.time() - start_time
                logger.warning(f"⚠️ Ambiguous match: {match.payload.get('email')} "
                             f"Score: {match.score:.3f}, Gap: {score_gap:.3f}")
                return {
                    "status": "DENIED",
                    "message": "Multiple possible matches detected. Please try again.",
                    "confidence": confidence,
                    "processing_time": f"{processing_time:.2f}s"
                }

        # 9. Check if confidence meets minimum requirement
        min_confidence = getattr(settings, 'FACE_MIN_CONFIDENCE', 70.0)
        logger.info(f"🔍 Min confidence required: {min_confidence}%, Got: {confidence:.2f}%")
        
        if confidence < min_confidence:
            processing_time = time.time() - start_time
            logger.info(f"❌ Access denied: Low confidence {confidence:.1f}% for {match.payload.get('email')}")
            return {
                "status": "DENIED",
                "message": f"Access Denied: Low confidence match ({confidence:.1f}%)",
                "confidence": confidence,
                "processing_time": f"{processing_time:.2f}s"
            }

        # 10. Access granted
        processing_time = time.time() - start_time
        logger.info(f"✅ Access granted: {match.payload.get('email')}, "
                   f"Confidence: {confidence:.1f}%, "
                   f"Time: {processing_time:.2f}s")

        return {
            "status": "OK",
            "message": f"Welcome, {match.payload.get('name', 'User')}!",
            "user": {
                "name": match.payload.get("name"),
                "email": match.payload.get("email"),
                "invite_code": match.payload.get("invite_code")
            },
            "confidence": round(confidence, 1),
            "match_score": round(match.score, 3),
            "processing_time": f"{processing_time:.2f}s"
        }

    except Exception as e:
        logger.error(f"Access check error: {str(e)}", exc_info=True)
        return {
            "status": "ERROR", 
            "message": "System error. Please try again.",
            "confidence": 0
        }