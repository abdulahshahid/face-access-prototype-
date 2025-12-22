import numpy as np
import logging
import face_recognition
from typing import Optional
import io
from PIL import Image

logger = logging.getLogger(__name__)

class FaceEmbeddingService:
    def __init__(self):
        logger.info("✅ Face embedding service initialized")
    
    async def generate_embedding(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Generate facial embedding from image"""
        try:
            # Load image
            image = face_recognition.load_image_file(io.BytesIO(image_bytes))
            
            # Detect faces and generate embeddings
            face_encodings = face_recognition.face_encodings(image)
            
            if not face_encodings:
                logger.warning("No face encodings generated")
                return None
            
            # Return first face encoding
            embedding = face_encodings[0]
            logger.info(f"Generated embedding with shape: {embedding.shape}")
            return embedding
        
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return None
    
    async def compare_embeddings(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compare two embeddings and return similarity score (0-1)"""
        try:
            distance = face_recognition.face_distance([embedding1], embedding2)[0]
            similarity = 1 - distance  # Convert distance to similarity
            return float(similarity)
        except Exception as e:
            logger.error(f"Embedding comparison error: {e}")
            return 0.0

# Singleton instance
face_embedding_service = FaceEmbeddingService()
