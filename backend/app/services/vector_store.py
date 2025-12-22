# app/services/vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np
import uuid
from typing import List, Dict
from app.core.config import settings

class VectorStore:
    def __init__(self):
        self.client = QdrantClient(settings.QDRANT_URL)
        self.collection_name = "face_embeddings"
        self.vector_size = 128
        self._init_collection()

    def _init_collection(self):
        names = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in names:
            self.client.create_collection(
                self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    async def store_embedding(self, attendee_id: int, embedding: np.ndarray) -> str:
        pid = str(uuid.uuid4())
        self.client.upsert(
            self.collection_name,
            [
                models.PointStruct(
                    id=pid,
                    vector=embedding.tolist(),
                    payload={"attendee_id": attendee_id, "embedding_id": pid},
                )
            ],
        )
        return pid

    async def search_similar(self, embedding: np.ndarray, limit: int = 5) -> List[Dict]:
        hits = self.client.search(
            self.collection_name, embedding.tolist(), limit=limit
        )
        return [
            {
                "attendee_id": h.payload.get("attendee_id"),
                "embedding_id": h.payload.get("embedding_id"),
                "score": h.score,
            }
            for h in hits
        ]

vector_store = VectorStore()
