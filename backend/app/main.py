from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

# Import routers
from app.api.routes import health, register, access_check, upload_csv, invite
from app.core.logging import setup_logging
from app.db.session import SessionLocal, engine
from app.db.base import Base

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Face Access Control System...")
    
    # Create database tables
    logger.info("📦 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Test database connection
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
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
    description="Prototype - Facial recognition access control with privacy by design",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For prototype only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with appropriate prefixes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(upload_csv.router, prefix="/api", tags=["Organizer"])
app.include_router(invite.router, prefix="/api", tags=["Invitation"])
app.include_router(register.router, prefix="/api", tags=["Registration"])
app.include_router(access_check.router, prefix="/api", tags=["Access Check"])

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Face Access Control System",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "upload_csv": "/api/upload-csv",
            "generate_invite": "/api/generate-invite",
            "register": "/api/register",
            "access_check": "/api/access-check"
        },
        "privacy_note": "No photos or ID documents stored - only facial embeddings"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)