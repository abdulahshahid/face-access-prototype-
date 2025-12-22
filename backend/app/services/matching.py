from typing import Optional
import logging
from app.services.face_embedding import face_embedding_service
from app.services.vector_store import vector_store
from app.core.config import settings

logger = logging.getLogger(__name__)

class FaceMatchingService:
    def __init__(self):
        self.threshold = settings.FACE_MATCH_THRESHOLD
    
    async def find_match(self, image_bytes: bytes) -> tuple:
        """
        Find matching face in database
        Returns (matched_attendee_id, confidence, is_match)
        """
        try:
            # Generate embedding for query image
            query_embedding = await face_embedding_service.generate_embedding(image_bytes)
            
            if not query_embedding:
                logger.warning("Could not generate embedding for query image")
                return None, 0.0, False
            
            # Search for similar embeddings
            matches = await vector_store.search_similar(query_embedding, limit=1)
            
            if not matches:
                logger.info("No matches found")
                return None, 0.0, False
            
            best_match = matches[0]
            score = best_match["score"]
            
            # Qdrant cosine similarity: higher is better (0 to 1)
            # Convert to confidence percentage
            confidence = score * 100
            
            # Check if match meets threshold
            is_match = score >= self.threshold
            
            logger.info(f"Best match: attendee_id={best_match['attendee_id']}, "
                       f"confidence={confidence:.2f}%, is_match={is_match}")
            
            if is_match:
                return best_match["attendee_id"], confidence, True
            else:
                return None, confidence, False
        
        except Exception as e:
            logger.error(f"Face matching error: {str(e)}")
            raise

face_matching_service = FaceMatchingService()