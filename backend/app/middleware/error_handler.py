"""
Error Handling Middleware for Production
Masks stack traces and sensitive information in production mode
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from typing import Union
import traceback

from app.core.config import settings

logger = structlog.get_logger()


class ProductionErrorHandler:
    """
    Middleware to handle errors safely in production.
    Masks stack traces and sensitive information.
    """

    @staticmethod
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """
        Handle HTTP exceptions
        """
        # Log the error with full details (server-side only)
        logger.error(
            "http_exception",
            status_code=exc.status_code,
            detail=str(exc.detail),
            path=request.url.path,
            method=request.method,
        )

        # In production, return sanitized error
        if not settings.DEBUG:
            # Don't expose internal details for 500 errors
            if exc.status_code >= 500:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "error": "Internal Server Error",
                        "message": "An unexpected error occurred. Please try again later.",
                        "status_code": exc.status_code,
                    },
                )

        # For 4xx errors or DEBUG mode, return original detail
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "status_code": exc.status_code,
            },
        )

    @staticmethod
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle Pydantic validation errors
        """
        logger.warning(
            "validation_error",
            errors=exc.errors(),
            path=request.url.path,
            method=request.method,
        )

        # Always show validation errors (they don't contain sensitive info)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "detail": exc.errors(),
                "status_code": 422,
            },
        )

    @staticmethod
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all unhandled exceptions
        """
        # Log full stack trace server-side
        logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            path=request.url.path,
            method=request.method,
            stack_trace=traceback.format_exc() if settings.DEBUG else None,
        )

        # In production, return generic error
        if not settings.DEBUG:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please contact support if the problem persists.",
                    "status_code": 500,
                },
            )

        # In DEBUG mode, return detailed error for developers
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "stack_trace": traceback.format_exc(),
                "status_code": 500,
            },
        )


def setup_error_handlers(app):
    """
    Setup error handlers for the FastAPI app

    Usage in main.py:
        from app.middleware.error_handler import setup_error_handlers
        setup_error_handlers(app)
    """
    error_handler = ProductionErrorHandler()

    # HTTP exceptions
    app.add_exception_handler(
        StarletteHTTPException,
        error_handler.http_exception_handler
    )

    # Validation errors
    app.add_exception_handler(
        RequestValidationError,
        error_handler.validation_exception_handler
    )

    # Catch-all for unhandled exceptions
    app.add_exception_handler(
        Exception,
        error_handler.general_exception_handler
    )

    logger.info(
        "error_handlers_configured",
        debug_mode=settings.DEBUG,
        message="Production error masking enabled" if not settings.DEBUG else "Debug mode: detailed errors enabled"
    )
