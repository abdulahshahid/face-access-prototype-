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

# --- FIXED: Use raw embeddings (no normalization needed for COSINE) ---
def validate_vector(vector):
    """Validate vector quality without normalization."""
    vector_array = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(vector_array)
    if norm == 0 or np.isnan(norm):
        logger.error(f"Invalid vector detected: zero or NaN norm")
        raise ValueError("Invalid face encoding generated")
    # Just return as-is, Qdrant handles normalization internally for COSINE
    return vector

# --- FIXED: Collection initialization with COSINE similarity ---
def initialize_collection():
    """Initialize or recreate the collection with proper configuration."""
    try:
        # Check if collection exists
        try:
            collection_info = qdrant.get_collection(COLLECTION_NAME)
            # If collection exists but with wrong distance, recreate it
            if (hasattr(collection_info.config.params.vectors, 'distance') and 
                collection_info.config.params.vectors.distance != Distance.COSINE):
                logger.warning(f"Collection exists with wrong distance metric. Recreating...")
                qdrant.delete_collection(COLLECTION_NAME)
                raise Exception("Collection needs recreation")
        except Exception:
            pass
        
        # Create collection with COSINE similarity
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=128, 
                distance=Distance.COSINE  # FIXED: Using COSINE instead of DOT
            )
        )
        logger.info(f"✅ Collection '{COLLECTION_NAME}' created with COSINE distance")
        
    except Exception as e:
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

        # 3. Detect Face with better parameters
        face_locations = face_recognition.face_locations(
            rgb_image,
            number_of_times_to_upsample=1,
            model="hog"  # Use "cnn" for better accuracy if GPU available
        )
        
        if not face_locations:
            raise HTTPException(status_code=400, detail="No face detected. Please try again.")
        
        if len(face_locations) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected. Only one person allowed.")

        # 4. Get high-quality face encoding
        face_encodings = face_recognition.face_encodings(
            rgb_image, 
            face_locations,
            num_jitters=10  # FIXED: Increased from 1 to 10 for better quality
        )
        
        if not face_encodings:
            raise HTTPException(status_code=400, detail="Could not extract features from face.")
            
        # 5. Validate the embedding (no normalization needed)
        embedding = validate_vector(face_encodings[0].tolist())
        
        # Log embedding stats for debugging
        logger.info(f"📊 Embedding norm: {np.linalg.norm(np.array(embedding)):.4f}")
        logger.info(f"📊 Embedding range: [{min(embedding):.3f}, {max(embedding):.3f}]")

        # 6. Check if this face already exists with HIGHER threshold
        try:
            search_result = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=embedding,
                limit=1,
                score_threshold=0.95  # FIXED: Much higher threshold to detect duplicates
            )
            if search_result:
                existing_user = search_result[0].payload
                if existing_user.get("invite_code") != invite_code:
                    raise HTTPException(
                        status_code=400, 
                        detail="This face is already registered with another user."
                    )
        except Exception as e:
            logger.warning(f"Duplicate check warning: {e}")

        # 7. Save to Qdrant
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

        # 8. Update Status
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