# app/services/face_detection.py
import cv2
import numpy as np
import logging
import io
from PIL import Image

logger = logging.getLogger(__name__)

class FaceDetectionService:
    def __init__(self):
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        except Exception:
            self.face_cascade = None

    async def detect_faces(self, image_bytes: bytes) -> list:
        if not self.face_cascade:
            return []
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, 1.1, 5, minSize=(100, 100)
            )
            return faces.tolist() if len(faces) else []
        except Exception:
            return []

    async def validate_single_face(self, image_bytes: bytes) -> bool:
        faces = await self.detect_faces(image_bytes)
        if len(faces) != 1:
            return False
        _, _, w, h = faces[0]
        return w >= 150 and h >= 150

face_detection_service = FaceDetectionService()
