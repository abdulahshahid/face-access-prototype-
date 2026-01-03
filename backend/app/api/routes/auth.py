from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from core.security import create_access_token
from core.config import settings
import logging

# --- FIX: Initialize the router ---
router = APIRouter()
# ----------------------------------

logger = logging.getLogger(__name__)

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Exchanges admin username/password for a JWT token.
    """
    # Verify credentials against env variables
    if (
        form_data.username != settings.ADMIN_USER
        or form_data.password != settings.ADMIN_PASSWORD
    ):
        logger.warning(f"Failed admin login attempt: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate Token
    access_token = create_access_token(
        data={
            "sub": form_data.username,
            "role": "admin"
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }