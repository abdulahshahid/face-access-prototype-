from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.session import SessionLocal

def get_db() -> Generator:
    """Dependency for getting database session"""
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()