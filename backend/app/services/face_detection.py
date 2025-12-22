import cv2
import numpy as np
import logging
from typing import Tuple
import io
from PIL import Image

logger = logging.getLogger(__name__)

class FaceDetectionService:
    def __init__(self):
        # Load face detector
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            logger.info("✅ Face detection model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load face detector: {e}")
            self.face_cascade = None
    
    async def detect_faces(self, image_bytes: bytes) -> list:
        """Detect faces in image"""
        if not self.face_cascade:
            return []
        
        try:
            # Convert bytes to numpy array
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
            
            # Convert to grayscale
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100)
            )
            
            logger.info(f"Detected {len(faces)} face(s)")
            return faces.tolist() if len(faces) > 0 else []
        
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []
    
    async def validate_single_face(self, image_bytes: bytes) -> bool:
        """Validate that image contains exactly one clear face"""
        faces = await self.detect_faces(image_bytes)
        
        if len(faces) == 0:
            logger.warning("No faces detected")
            return False
        
        if len(faces) > 1:
            logger.warning(f"Multiple faces detected: {len(faces)}")
            return False
        
        # Check face size (should be reasonably large)
        x, y, w, h = faces[0]
        if w < 150 or h < 150:
            logger.warning(f"Face too small: {w}x{h}")
            return False
        
        return True

# Singleton instance
face_detection_service = FaceDetectionService()
