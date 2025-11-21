"""
Security Headers Middleware
Adds security headers to all responses for production hardening
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all HTTP responses

    Headers included:
    - Content-Security-Policy (CSP)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Content Security Policy (CSP)
        # Restricts sources of content that can be loaded
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Allow inline scripts for React
            "style-src 'self' 'unsafe-inline'; "  # Allow inline styles for Tailwind
            "img-src 'self' data: https:; "  # Allow images from self, data URIs, and HTTPS
            "font-src 'self' data:; "
            "connect-src 'self' https://api.openai.com https://api.mistral.ai; "  # API endpoints
            "frame-ancestors 'none'; "  # Prevent clickjacking
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy - control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature Policy)
        # Disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=()"
        )

        # HTTPS enforcement (HSTS) - only in production
        if not settings.DEBUG:
            # Force HTTPS for 1 year, including subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


def add_security_headers(app):
    """
    Add security headers middleware to the FastAPI app

    Usage in main.py:
        from app.middleware.security_headers import add_security_headers
        add_security_headers(app)
    """
    app.add_middleware(SecurityHeadersMiddleware)

    logger.info(
        "security_headers_configured",
        debug_mode=settings.DEBUG,
        hsts_enabled=not settings.DEBUG,
        message="Security headers middleware enabled"
    )
