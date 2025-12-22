from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

def validate_image(image_bytes: bytes, max_size_mb: int = 10) -> tuple:
    """
    Validate image file
    Returns (is_valid, error_message)
    """
    try:
        # Check size
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            return False, f"Image too large: {size_mb:.2f}MB (max {max_size_mb}MB)"
        
        # Try to open image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Check format
        if image.format not in ['JPEG', 'JPG', 'PNG']:
            return False, f"Unsupported format: {image.format}"
        
        # Check dimensions
        if image.width < 200 or image.height < 200:
            return False, f"Image too small: {image.width}x{image.height} (min 200x200)"
        
        return True, None
    
    except Exception as e:
        logger.error(f"Image validation error: {str(e)}")
        return False, str(e)

def resize_image(image_bytes: bytes, max_width: int = 1024) -> bytes:
    """Resize image if too large"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((max_width, new_height), Image.LANCZOS)
        
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=90)
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"Image resize error: {str(e)}")
        return image_bytes