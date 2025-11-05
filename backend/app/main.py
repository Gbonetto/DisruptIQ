"""
DisruptIQ - Main FastAPI Application
Smart RAG System for Property Management
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import auth, digest, email_generator, emails, documents, chat, webhooks, admin, webhook_test, health, assistant, coproprietes, coproprietaires, cache, assistant_v2, assistant_v2_stream, sql_tables, workflows, email_safe_send
# Import all models to ensure they're registered with SQLAlchemy
from app.models import User, Email, Vendor, Document
from app.services.scheduler_service import get_scheduler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute", "1000/hour"])

# Create FastAPI app
app = FastAPI(
    title="DisruptIQ API",
    description="Smart RAG System for Property Management - Multi-Agent Assistant",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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

    # Initialize RAG Service (Qdrant collection)
    try:
        from app.services.rag_service import RAGService
        rag_service = RAGService()
        await rag_service.initialize()
        logger.info("rag_service_initialized", message="Qdrant collection ready for indexing")
    except Exception as e:
        logger.error("rag_service_init_failed", error=str(e))
        # Log error but don't fail startup - RAG is important but not critical for basic operations
        logger.warning("rag_service_startup_warning", message="RAG service failed to initialize, indexing will not work until Qdrant is available")

    # Initialize Redis Cache Service
    try:
        from app.services.cache_service import get_cache_service
        cache_service = get_cache_service()
        await cache_service.initialize()
        stats = await cache_service.get_stats()
        logger.info("cache_service_initialized", **stats)
    except Exception as e:
        logger.error("cache_service_init_failed", error=str(e))
        # Log error but don't fail startup - cache is optional
        logger.warning("cache_service_startup_warning", message="Cache service failed to initialize, will continue without caching")

    # Start background scheduler for digest generation
    try:
        scheduler = get_scheduler()
        scheduler.start()
        logger.info("scheduler_initialized", message="Background digest generation enabled")
    except Exception as e:
        logger.error("scheduler_init_failed", error=str(e))
        # Don't raise - scheduler is optional


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("shutting_down_disruptiq")

    # Shutdown cache service
    try:
        from app.services.cache_service import get_cache_service
        cache_service = get_cache_service()
        await cache_service.close()
        logger.info("cache_service_shutdown")
    except Exception as e:
        logger.error("cache_service_shutdown_failed", error=str(e))

    # Shutdown scheduler
    try:
        scheduler = get_scheduler()
        scheduler.shutdown()
        logger.info("scheduler_shutdown")
    except Exception as e:
        logger.error("scheduler_shutdown_failed", error=str(e))

    # Close database connections
    try:
        from app.core.database import close_db
        await close_db()
        logger.info("database_connections_closed")
    except Exception as e:
        logger.error("database_shutdown_failed", error=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "DisruptIQ API",
        "description": "Smart RAG System for Property Management",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/api/docs",
            "redoc": "/api/redoc",
            "health": "/health",
            "health_detailed": "/health/detailed",
            "metrics": "/metrics"
        }
    }


# Include API routers
# Health checks first (no prefix for Kubernetes compatibility)
app.include_router(health.router, tags=["Health & Monitoring"])

# Feature routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(digest.router, prefix="/api/digest", tags=["Email Digest"])
app.include_router(email_generator.router, prefix="/api/email", tags=["Email Generator"])
app.include_router(emails.router, prefix="/api/emails", tags=["Email Management"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["AI Assistant"])
app.include_router(assistant_v2.router, prefix="/api/assistant-v2", tags=["Multi-Agent Assistant"])
app.include_router(assistant_v2_stream.router, prefix="/api/assistant-v2", tags=["Multi-Agent Assistant Streaming"])
app.include_router(coproprietes.router, prefix="/api/coproprietes", tags=["Copropriétés"])
app.include_router(coproprietaires.router, prefix="/api/coproprietaires", tags=["Copropriétaires"])
app.include_router(cache.router, prefix="/api/cache", tags=["Cache Management"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["N8N Webhooks"])
app.include_router(webhook_test.router, prefix="/api/webhook-test", tags=["Webhook Testing"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"])
app.include_router(sql_tables.router, prefix="/api/sql", tags=["SQL Table Management"])

# Phase 2: Workflows & Email Safe-Send
app.include_router(workflows.router, prefix="/api/workflows", tags=["N8N Workflows"])
app.include_router(email_safe_send.router, prefix="/api/email-safe-send", tags=["Email Safe-Send"])
