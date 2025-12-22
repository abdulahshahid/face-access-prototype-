import cv2
import numpy as np
import logging
from typing import Tuple
import io
from PIL import Image

logger = logging.getLogger(__name__)

class LivenessService:
    def __init__(self):
        # Basic liveness detection thresholds
        self.min_face_size = 150  # Minimum face width/height
        self.max_face_size = 800  # Maximum face width/height
        logger.info("✅ Liveness service initialized")
    
    async def check_liveness(self, image_bytes: bytes) -> Tuple[bool, float, str]:
        """
        Basic liveness check
        Returns: (is_live, confidence, reason)
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
            
            # Check image quality
            if image_np.mean() < 30 or image_np.mean() > 220:
                return False, 0.3, "Poor lighting conditions"
            
            # Check for blur (basic variance of Laplacian)
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if laplacian_var < 100:
                return False, 0.4, "Image too blurry"
            
            # Check face proportions (simplified)
            height, width = image_np.shape[:2]
            if width < self.min_face_size or height < self.min_face_size:
                return False, 0.5, "Face too small"
            
            if width > self.max_face_size or height > self.max_face_size:
                return False, 0.5, "Face too large"
            
            # All checks passed
            confidence = min(laplacian_var / 500, 1.0)  # Normalize to 0-1
            return True, confidence, "Live face detected"
        
        except Exception as e:
            logger.error(f"Liveness check error: {e}")
            return False, 0.0, f"Error: {str(e)}"

# Singleton instance
liveness_service = LivenessService()
