"""
DisruptIQ - Main FastAPI Application
Smart RAG System for Property Management
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import auth, digest, email_generator, documents, chat, webhooks, admin
# Import all models to ensure they're registered with SQLAlchemy
from app.models import User, Email, Vendor, Document

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="DisruptIQ API",
    description="Smart RAG System for Property Management - Multi-Agent Assistant",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("starting_disruptiq", version="1.0.0")

    # Initialize database tables
    try:
        await init_db()
        logger.info("database_initialized", message="All tables created successfully")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("shutting_down_disruptiq")
    # TODO: Close database connections


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "DisruptIQ",
            "version": "1.0.0"
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DisruptIQ API - Smart RAG for Property Management",
        "docs": "/api/docs",
        "health": "/health"
    }


# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(digest.router, prefix="/api/digest", tags=["Email Digest"])
app.include_router(email_generator.router, prefix="/api/email", tags=["Email Generator"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["N8N Webhooks"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"])
