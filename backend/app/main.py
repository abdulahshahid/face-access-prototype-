import sys
import os

# Add /app to Python path
sys.path.insert(0, '/app')

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn
from sqlalchemy import text

from api.routes import health, register, access_check, invite, admin, auth
from db.session import SessionLocal, engine
from db.base import Base
from core.logging import setup_logging
from core.deps import get_current_admin

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Face Access Control System (Phase 02)...")

    # Create database tables
    logger.info("📦 Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Test database connection
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("👋 Shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Face Access Control System",
    description="Phase 02 - Production Hardening & Admin Panel",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PUBLIC ROUTERS ---
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(invite.router, prefix="/api", tags=["Invitation"])
app.include_router(register.router, prefix="/api", tags=["Registration"])
app.include_router(access_check.router, prefix="/api", tags=["Access Check"])

# --- ADMIN ROUTERS (NO GLOBAL PROTECTION) ---
# Protection is handled individually in each route using check_auth_and_redirect()
app.include_router(
    admin.router, 
    prefix="/api/admin", 
    tags=["Admin Control"]
    # ❌ REMOVED: dependencies=[Depends(get_current_admin)]
    # ✅ Each route in admin.py now handles its own auth
)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Face Access Control System",
        "phase": "02 - Hardened",
        "status": "operational",
        "endpoints": {
            "health": "/api/health",
            "auth": "/api/auth/login",
            "admin_portal": "/api/admin/portal",
            "admin_login": "/api/admin/portal/login",
            "admin_upload": "/api/admin/upload-csv (Protected)",
            "admin_list": "/api/admin/attendees (Protected)",
            "register": "/api/register",
            "access_check": "/api/access-check"
        },
        "instructions": "Login at /api/admin/portal/login to access admin features"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)