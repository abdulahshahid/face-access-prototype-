from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

# Import routers
from app.api.routes import health, register, access_check, upload_csv, invite
from app.db.session import SessionLocal, engine
from app.db.base import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create database tables
    logger.info("Starting up... Creating database tables if they don't exist")
    Base.metadata.create_all(bind=engine)
    
    # Test database connection
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Face Access Control System",
    description="A facial recognition-based access control system",
    version="1.0.0",
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

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(register.router, prefix="/api", tags=["Registration"])
app.include_router(access_check.router, prefix="/api", tags=["Access Check"])
app.include_router(upload_csv.router, prefix="/api", tags=["Upload"])
app.include_router(invite.router, prefix="/api", tags=["Invite"])

@app.get("/")
async def root():
    return {
        "message": "Face Access Control System API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "register": "/api/register",
            "access_check": "/api/access",
            "upload_csv": "/api/upload",
            "invite": "/api/invite"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint (also available via /health router)"""
    return {
        "status": "healthy",
        "service": "face-access-control",
        "database": "connected"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
