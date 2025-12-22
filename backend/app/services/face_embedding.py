# app/services/face_embedding.py
import numpy as np
import logging
import face_recognition
import io
from PIL import Image
from typing import Optional

logger = logging.getLogger(__name__)

class FaceEmbeddingService:
    async def generate_embedding(self, image_bytes: bytes) -> Optional[np.ndarray]:
        try:
            image = face_recognition.load_image_file(io.BytesIO(image_bytes))
            encodings = face_recognition.face_encodings(image)
            return encodings[0] if encodings else None
        except Exception:
            return None

    async def compare_embeddings(self, e1: np.ndarray, e2: np.ndarray) -> float:
        try:
            d = face_recognition.face_distance([e1], e2)[0]
            return float(1 - d)
        except Exception:
            return 0.0

face_embedding_service = FaceEmbeddingService()
