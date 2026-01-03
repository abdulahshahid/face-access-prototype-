from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from core.config import settings

# This tells FastAPI that the client must send a "Bearer <token>" in the Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_admin(token: str = Depends(oauth2_scheme)):
    """
    Validates the JWT token. If valid, returns the user/role.
    If invalid, raises 401 Unauthorized.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the token using your SECRET_KEY
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None or role != "admin":
            raise credentials_exception
            
        return {"username": username, "role": role}
        
    except JWTError:
        raise credentials_exception