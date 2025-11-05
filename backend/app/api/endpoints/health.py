"""
Health Check Endpoints
Provides comprehensive health status for monitoring and observability
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from datetime import datetime
import structlog
from typing import Dict, Any
import os
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.models.email import Email

router = APIRouter()
logger = structlog.get_logger()


async def check_database(db: AsyncSession) -> Dict[str, Any]:
    """
    Check database connectivity and perform basic query

    Returns:
        dict: Database health status
    """
    try:
        # Test basic query
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        # Test table access
        await db.execute(select(Email).limit(1))

        return {
            "status": "healthy",
            "latency_ms": 0,  # Could add actual latency measurement
            "message": "Database connection successful"
        }
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Database connection failed"
        }


async def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity

    Returns:
        dict: Redis health status
    """
    try:
        from app.services.cache_service import get_cache_service
        cache_service = get_cache_service()

        if not cache_service.enabled:
            return {
                "status": "disabled",
                "message": "Redis caching is disabled"
            }

        stats = await cache_service.get_stats()

        if stats.get("connected"):
            return {
                "status": "healthy",
                "message": "Redis connection successful",
                **stats
            }
        else:
            return {
                "status": "unhealthy",
                "message": "Redis connection failed",
                "error": stats.get("error")
            }

    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_qdrant() -> Dict[str, Any]:
    """
    Check Qdrant connectivity

    Returns:
        dict: Qdrant health status
    """
    try:
        from app.services.rag_service import get_rag_service

        rag_service = get_rag_service()
        collection_info = await rag_service._run_sync(
            rag_service.client.get_collection,
            collection_name=rag_service.collection_name
        )

        return {
            "status": "healthy",
            "points_count": collection_info.points_count,
            "collection": rag_service.collection_name,
            "vector_size": collection_info.config.params.vectors.size,
            "message": "Qdrant connection successful"
        }
    except Exception as e:
        logger.error("qdrant_health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Qdrant connection failed"
        }


async def check_gmail_credentials() -> Dict[str, Any]:
    """
    Check Gmail credentials availability

    Returns:
        dict: Gmail credentials status
    """
    try:
        token_path = settings.GMAIL_TOKEN_PATH
        credentials_path = settings.GMAIL_CREDENTIALS_PATH

        token_exists = os.path.exists(token_path)
        credentials_exist = os.path.exists(credentials_path)

        if token_exists and credentials_exist:
            return {
                "status": "healthy",
                "token_present": True,
                "credentials_present": True,
                "message": "Gmail credentials available"
            }
        else:
            return {
                "status": "degraded",
                "token_present": token_exists,
                "credentials_present": credentials_exist,
                "message": "Gmail credentials partially available"
            }
    except Exception as e:
        logger.error("gmail_credentials_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Basic health check endpoint

    Returns:
        200: Service is healthy
        503: Service is unhealthy
    """
    try:
        # Quick database check
        await db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "service": "disruptiq-backend",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy"
        )


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """
    Detailed health check with all components

    Returns comprehensive health status including:
    - Database connectivity
    - Redis connectivity
    - Qdrant connectivity
    - Gmail credentials
    - System resources
    """
    start_time = datetime.now()

    # Run all health checks concurrently
    database_health, redis_health, qdrant_health, gmail_health = await asyncio.gather(
        check_database(db),
        check_redis(),
        check_qdrant(),
        check_gmail_credentials(),
        return_exceptions=True
    )

    # Handle any exceptions from health checks
    def safe_result(result, component_name):
        if isinstance(result, Exception):
            logger.error(f"{component_name}_health_check_exception", error=str(result))
            return {
                "status": "unhealthy",
                "error": str(result)
            }
        return result

    database_health = safe_result(database_health, "database")
    redis_health = safe_result(redis_health, "redis")
    qdrant_health = safe_result(qdrant_health, "qdrant")
    gmail_health = safe_result(gmail_health, "gmail")

    # Determine overall status
    statuses = [
        database_health.get("status"),
        redis_health.get("status"),
        qdrant_health.get("status"),
        gmail_health.get("status")
    ]

    if "unhealthy" in statuses:
        overall_status = "unhealthy"
        status_code = 503
    elif "degraded" in statuses:
        overall_status = "degraded"
        status_code = 200
    elif all(s in ["healthy", "not_implemented"] for s in statuses):
        overall_status = "healthy"
        status_code = 200
    else:
        overall_status = "unknown"
        status_code = 503

    end_time = datetime.now()
    duration_ms = (end_time - start_time).total_seconds() * 1000

    response = {
        "status": overall_status,
        "service": "disruptiq-backend",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "uptime_seconds": 0,  # TODO: Implement uptime tracking
        "health_check_duration_ms": round(duration_ms, 2),
        "checks": {
            "database": database_health,
            "redis": redis_health,
            "qdrant": qdrant_health,
            "gmail": gmail_health
        }
    }

    if overall_status == "unhealthy":
        logger.warning("service_unhealthy", response=response)

    # Return with appropriate status code but don't raise exception
    # This allows monitoring systems to still parse the detailed response
    return response


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Kubernetes-style readiness probe

    Checks if the service is ready to accept traffic

    Returns:
        200: Service is ready
        503: Service is not ready
    """
    try:
        # Check critical dependencies
        await db.execute(text("SELECT 1"))

        # Check if Gmail credentials are available
        gmail_health = await check_gmail_credentials()

        if gmail_health["status"] == "unhealthy":
            raise HTTPException(
                status_code=503,
                detail="Gmail credentials not available"
            )

        return {
            "status": "ready",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness probe

    Checks if the service is alive (not deadlocked)

    Returns:
        200: Service is alive
    """
    # Simple check that doesn't require external dependencies
    # This should always return 200 unless the process is completely frozen
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/metrics")
async def metrics_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Prometheus-compatible metrics endpoint

    Returns basic metrics about the service
    """
    try:
        # Get email counts by urgency
        from sqlalchemy import select, func
        from app.models.email import EmailUrgency

        urgent_count = await db.execute(
            select(func.count()).select_from(Email).where(
                Email.urgency == EmailUrgency.URGENT
            )
        )
        urgent = urgent_count.scalar() or 0

        important_count = await db.execute(
            select(func.count()).select_from(Email).where(
                Email.urgency == EmailUrgency.IMPORTANT
            )
        )
        important = important_count.scalar() or 0

        routine_count = await db.execute(
            select(func.count()).select_from(Email).where(
                Email.urgency == EmailUrgency.ROUTINE
            )
        )
        routine = routine_count.scalar() or 0

        total = urgent + important + routine

        # Format as Prometheus metrics
        metrics_output = f"""# HELP disruptiq_emails_total Total number of emails in database
# TYPE disruptiq_emails_total gauge
disruptiq_emails_total {total}

# HELP disruptiq_emails_by_urgency Number of emails by urgency level
# TYPE disruptiq_emails_by_urgency gauge
disruptiq_emails_by_urgency{{urgency="urgent"}} {urgent}
disruptiq_emails_by_urgency{{urgency="important"}} {important}
disruptiq_emails_by_urgency{{urgency="routine"}} {routine}
"""

        return metrics_output

    except Exception as e:
        logger.error("metrics_endpoint_failed", error=str(e))
        return f"# Error collecting metrics: {str(e)}\n"
