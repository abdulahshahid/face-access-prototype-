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
import time

COLLECTION_NAME = settings.QDRANT_COLLECTION

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Qdrant Client
qdrant = QdrantClient(url=settings.QDRANT_URL)

# --- UPDATED: Normalization function ---
def normalize_vector(vector):
    """Normalize a vector to unit length for cosine similarity."""
    vector_array = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(vector_array)
    if norm == 0 or np.isnan(norm):
        logger.warning(f"Zero or NaN norm detected in vector: {vector_array[:5]}...")
        return vector
    normalized = (vector_array / norm).tolist()
    return normalized

# --- UPDATED: Collection initialization with DOT product ---
def initialize_collection():
    """Initialize or recreate the collection with proper configuration."""
    try:
        # Check if collection exists
        try:
            collection_info = qdrant.get_collection(COLLECTION_NAME)
            # If collection exists but with wrong distance, recreate it
            if (hasattr(collection_info.config.params.vectors, 'distance') and 
                collection_info.config.params.vectors.distance != Distance.DOT):
                logger.warning(f"Collection exists with wrong distance metric. Recreating...")
                qdrant.delete_collection(COLLECTION_NAME)
                raise Exception("Collection needs recreation")
        except Exception:
            # Collection doesn't exist or needs recreation
            pass
        
        # Create collection with DOT product
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=128, 
                distance=Distance.DOT  # Changed from COSINE to DOT
            )
        )
        logger.info(f"✅ Collection '{COLLECTION_NAME}' created with DOT distance")
        
    except Exception as e:
        # If the error message says "already exists", we can safely ignore it.
        if "already exists" in str(e) or "Conflict" in str(e):
            logger.info(f"Collection '{COLLECTION_NAME}' already exists")
            pass
        else:
            logger.error(f"Failed to create collection: {e}")
            raise e

# Initialize collection on startup
initialize_collection()

@router.post("/register")
async def register_face(
    invite_code: str = Form(...),
    photo: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Register a face using an invite code.
    """
    start_time = time.time()
    
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

        # Convert to RGB for face_recognition
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
            
        # 4. Normalize the embedding
        raw_embedding = face_encodings[0].tolist()
        embedding = normalize_vector(raw_embedding)
        
        # Log embedding stats for debugging
        logger.debug(f"Raw embedding norm: {np.linalg.norm(np.array(raw_embedding)):.4f}")
        logger.debug(f"Normalized embedding norm: {np.linalg.norm(np.array(embedding)):.4f}")

        # 5. Check if this face already exists (optional: prevent duplicate registrations)
        try:
            search_result = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=embedding,
                limit=1,
                score_threshold=0.8  # High threshold to detect duplicates
            )
            if search_result:
                # Face already registered with high confidence
                existing_user = search_result[0].payload
                if existing_user.get("invite_code") != invite_code:
                    raise HTTPException(
                        status_code=400, 
                        detail="This face is already registered with another user."
                    )
        except Exception as e:
            logger.warning(f"Duplicate check failed: {e}")

        # 6. Save to Qdrant
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=attendee.id,
                    vector=embedding,
                    payload={
                        "name": attendee.name,
                        "email": attendee.email,
                        "invite_code": attendee.invite_code,
                        "registered_at": time.time(),
                        "attendee_id": attendee.id
                    }
                )
            ]
        )

        # 7. Update Status
        attendee.status = "registered"
        db.commit()

        processing_time = time.time() - start_time
        logger.info(f"✅ Successfully registered face for {attendee.name} ({attendee.email}) "
                   f"in {processing_time:.2f}s")

        return {
            "status": "success",
            "message": f"Welcome {attendee.name}, registration complete!",
            "attendee_id": attendee.id,
            "processing_time": f"{processing_time:.2f}s"
        }

    except HTTPException as he:
        logger.warning(f"Registration HTTP error: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")