# In your auth routes file (e.g., routes/auth.py)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.security import create_access_token, verify_access_token
from db.session import get_db
from models.admin import Admin  # You'll need an Admin model

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    # Check if admin exists
    admin = db.query(Admin).filter(Admin.email == login_data.email).first()
    
    if not admin or not verify_access_token(login_data.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create JWT token
    access_token = create_access_token(data={"sub": admin.email, "is_admin": True})
    
    return {"access_token": access_token, "token_type": "bearer"}