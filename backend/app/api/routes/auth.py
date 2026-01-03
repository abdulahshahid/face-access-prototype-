# api/routes/auth.py
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from db.session import get_db
from core.security import create_access_token

router = APIRouter()

# Load admin credentials from environment
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
print(f"Admin Email: {ADMIN_EMAIL}, Admin Password: {ADMIN_PASSWORD}")
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Simple admin login using environment variables.
    """
    
    # Check if credentials match env variables
    if login_data.email == ADMIN_EMAIL and login_data.password == ADMIN_PASSWORD:
        # Create JWT token
        access_token = create_access_token(
            data={
                "sub": ADMIN_EMAIL,
                "user_id": 0,  # Special ID for env admin
                "is_admin": True
            }
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": 0,
                "email": ADMIN_EMAIL,
                "name": "Admin",
                "is_admin": True
            }
        }
    
    # Invalid credentials
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password"
    )

@router.get("/me")
def get_current_user_info():
    """Get current authenticated user info"""
    return {
        "email": ADMIN_EMAIL,
        "name": "Admin",
        "is_admin": True,
        "source": "environment"
    }