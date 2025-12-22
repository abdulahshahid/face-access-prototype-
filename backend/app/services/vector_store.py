from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np
import logging
import uuid
from typing import List, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.client = QdrantClient(settings.QDRANT_URL)
        self.collection_name = "face_embeddings"
        self.vector_size = 128  # face_recognition embedding size
        
        # Initialize collection
        self._init_collection()
    
    def _init_collection(self):
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.collection_name}")
            else:
                logger.info(f"✅ Collection exists: {self.collection_name}")
        
        except Exception as e:
            logger.error(f"❌ Collection initialization error: {e}")
            raise
    
    async def store_embedding(self, attendee_id: int, embedding: np.ndarray) -> str:
        """Store face embedding in vector database"""
        try:
            point_id = str(uuid.uuid4())
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=embedding.tolist(),
                        payload={
                            "attendee_id": attendee_id,
                            "embedding_id": point_id
                        }
                    )
                ]
            )
            
            logger.info(f"✅ Stored embedding for attendee {attendee_id}")
            return point_id
        
        except Exception as e:
            logger.error(f"❌ Embedding storage error: {e}")
            raise
    
    async def search_similar(self, query_embedding: np.ndarray, limit: int = 5) -> List[Dict]:
        """Search for similar embeddings"""
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                limit=limit
            )
            
            results = []
            for hit in search_result:
                results.append({
                    "attendee_id": hit.payload.get("attendee_id"),
                    "embedding_id": hit.payload.get("embedding_id"),
                    "score": hit.score
                })
            
            return results
        
        except Exception as e:
            logger.error(f"❌ Vector search error: {e}")
            return []
    
    async def delete_embedding(self, embedding_id: str):
        """Delete embedding from vector store"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[embedding_id]
                )
            )
            logger.info(f"✅ Deleted embedding: {embedding_id}")
        
        except Exception as e:
            logger.error(f"❌ Embedding deletion error: {e}")

# Singleton instance
vector_store = VectorStore()