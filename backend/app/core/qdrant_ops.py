import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as models
from core.config import settings
import numpy as np

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection = settings.QDRANT_COLLECTION
        self._init_collection()

    def _init_collection(self):
        """Ensures collection exists with Cosine distance."""
        try:
            self.client.get_collection(self.collection)
        except Exception:
            logger.info(f"⚡ Creating collection {self.collection} with COSINE distance")
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=128,  # dlib=128, InsightFace=512
                    distance=models.Distance.COSINE
                )
            )

    def delete_user_vector(self, user_id: int):
        """
        Removes the vector point associated with the SQL User ID.
        """
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.PointIdsList(points=[user_id])
            )
            logger.info(f"🗑️ Deleted vector for User ID {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            return False

    def search_face(self, vector: list, threshold: float = 0.92):
        return self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=3,
            score_threshold=threshold,
            with_payload=True
        )

# Singleton instance
qdrant_service = QdrantService()