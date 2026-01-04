# api/routes/auth.py
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from fastapi import Response  # add this import
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
def login(
    login_data: LoginRequest,
    response: Response,  # add this parameter
    db: Session = Depends(get_db)
):
    if login_data.email == ADMIN_EMAIL and login_data.password == ADMIN_PASSWORD:
        access_token = create_access_token(
            data={
                "sub": ADMIN_EMAIL,
                "user_id": 0,
                "is_admin": True
            }
        )

        # Set HttpOnly cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,          # prevents JS access (mitigates XSS)
            secure=True,            # only send over HTTPS (set False in dev if needed)
            samesite="lax",         # or "strict" depending on your needs
            max_age=86400,          # 24 hours, match your token expiry
            path="/"
        )

        return {
            "access_token": access_token,  # still return for frontend if needed
            "token_type": "bearer",
            "user": {
                "id": 0,
                "email": ADMIN_EMAIL,
                "name": "Admin",
                "is_admin": True
            }
        }

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