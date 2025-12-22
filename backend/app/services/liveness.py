# app/services/liveness.py
import cv2
import numpy as np
import logging
import io
from PIL import Image
from typing import Tuple

logger = logging.getLogger(__name__)

class LivenessService:
    def __init__(self):
        self.min_face_size = 150
        self.max_face_size = 800

    async def check_liveness(self, image_bytes: bytes) -> Tuple[bool, float, str]:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            img = np.array(image)
            if img.mean() < 30 or img.mean() > 220:
                return False, 0.3, "Poor lighting"
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            blur = cv2.Laplacian(gray, cv2.CV_64F).var()
            if blur < 100:
                return False, 0.4, "Blurry image"
            h, w = img.shape[:2]
            if w < self.min_face_size or h < self.min_face_size:
                return False, 0.5, "Face too small"
            if w > self.max_face_size or h > self.max_face_size:
                return False, 0.5, "Face too large"
            return True, min(blur / 500, 1.0), "Live"
        except Exception as e:
            return False, 0.0, str(e)

liveness_service = LivenessService()
