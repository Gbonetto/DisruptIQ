"""
Monitoring and Error Tracking Configuration

Integrates Sentry for error tracking and performance monitoring.
"""

import os
import logging
import structlog
from typing import Optional

# Sentry is optional for development
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from app.core.config import settings

logger = structlog.get_logger()


def init_sentry() -> bool:
    """
    Initialize Sentry error tracking and performance monitoring

    Returns:
        bool: True if Sentry was initialized, False otherwise
    """
    if not SENTRY_AVAILABLE:
        logger.warning(
            "sentry_not_available",
            message="Sentry SDK not installed. Error tracking disabled. Install with: pip install sentry-sdk"
        )
        return False

    sentry_dsn = os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        logger.info(
            "sentry_disabled",
            message="SENTRY_DSN not set. Error tracking disabled for this environment."
        )
        return False

    environment = os.getenv("ENVIRONMENT", "development")
    release_version = os.getenv("RELEASE_VERSION", "dev")

    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            release=f"disruptiq-backend@{release_version}",

            # Performance Monitoring
            traces_sample_rate=_get_traces_sample_rate(environment),
            profiles_sample_rate=_get_profiles_sample_rate(environment),

            # Integrations
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint",  # /chat/ask instead of just /chat/{path}
                    failed_request_status_codes=[400, 499, 500, 599],  # Track 4xx and 5xx
                ),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(
                    level=logging.INFO,       # Capture info and above as breadcrumbs
                    event_level=logging.ERROR  # Send errors and above as events
                ),
            ],

            # Error Sampling
            sample_rate=1.0,  # 100% of errors

            # PII (Personally Identifiable Information)
            send_default_pii=False,  # GDPR compliance

            # Request body
            max_request_body_size="medium",  # Capture request body (small/medium/always)

            # Breadcrumbs
            max_breadcrumbs=50,

            # Debug mode (only for development)
            debug=environment == "development",

            # Before send hook for filtering
            before_send=before_send_hook,

            # Before breadcrumb hook for filtering
            before_breadcrumb=before_breadcrumb_hook,
        )

        logger.info(
            "sentry_initialized",
            environment=environment,
            release=release_version,
            traces_sample_rate=_get_traces_sample_rate(environment)
        )

        return True

    except Exception as e:
        logger.error(
            "sentry_init_failed",
            error=str(e),
            message="Failed to initialize Sentry. Error tracking disabled."
        )
        return False


def _get_traces_sample_rate(environment: str) -> float:
    """Get traces sample rate based on environment"""
    rates = {
        "production": 0.1,   # 10% in prod (reduce cost)
        "staging": 0.5,      # 50% in staging
        "development": 1.0   # 100% in dev
    }
    return rates.get(environment, 0.1)


def _get_profiles_sample_rate(environment: str) -> float:
    """Get profiling sample rate based on environment"""
    rates = {
        "production": 0.05,  # 5% in prod
        "staging": 0.2,      # 20% in staging
        "development": 1.0   # 100% in dev
    }
    return rates.get(environment, 0.05)


def before_send_hook(event: dict, hint: dict) -> Optional[dict]:
    """
    Filter events before sending to Sentry

    Args:
        event: Sentry event dict
        hint: Additional context

    Returns:
        Modified event or None to drop event
    """
    # Drop specific exceptions that are not errors
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]

        # Ignore common non-error exceptions
        ignored_exceptions = [
            "asyncio.CancelledError",
            "starlette.exceptions.HTTPException",
        ]

        exception_name = f"{exc_type.__module__}.{exc_type.__name__}"
        if exception_name in ignored_exceptions:
            return None

        # Ignore specific HTTP status codes
        if hasattr(exc_value, "status_code"):
            ignored_status_codes = [404, 429]  # Not Found, Rate Limited
            if exc_value.status_code in ignored_status_codes:
                return None

    # Filter out sensitive data from request
    if "request" in event:
        request_data = event["request"]

        # Remove auth headers
        if "headers" in request_data:
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                if header in request_data["headers"]:
                    request_data["headers"][header] = "[Filtered]"

        # Remove sensitive query params
        if "query_string" in request_data:
            sensitive_params = ["api_key", "token", "password"]
            # Simple filtering (would need proper parsing for production)
            for param in sensitive_params:
                if param in request_data["query_string"]:
                    request_data["query_string"] = "[Filtered]"

    # Add custom tags
    event.setdefault("tags", {})
    event["tags"]["service"] = "disruptiq-backend"

    return event


def before_breadcrumb_hook(crumb: dict, hint: dict) -> Optional[dict]:
    """
    Filter breadcrumbs before adding to event

    Args:
        crumb: Breadcrumb dict
        hint: Additional context

    Returns:
        Modified breadcrumb or None to drop
    """
    # Drop database query breadcrumbs containing sensitive data
    if crumb.get("category") == "query":
        message = crumb.get("message", "")
        if any(keyword in message.lower() for keyword in ["password", "token", "secret"]):
            crumb["message"] = "[Sensitive SQL Query]"

    # Filter HTTP request breadcrumbs
    if crumb.get("category") == "httplib":
        data = crumb.get("data", {})
        url = data.get("url", "")

        # Remove API keys from URLs
        if "api_key=" in url:
            data["url"] = url.split("api_key=")[0] + "api_key=[FILTERED]"

    return crumb


def capture_exception(error: Exception, context: Optional[dict] = None):
    """
    Capture an exception with optional context

    Args:
        error: Exception to capture
        context: Additional context dict
    """
    if not SENTRY_AVAILABLE:
        logger.error("exception_not_captured_sentry_unavailable", error=str(error))
        return

    with sentry_sdk.push_scope() as scope:
        # Add custom context
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", context: Optional[dict] = None):
    """
    Capture a message with optional context

    Args:
        message: Message to capture
        level: Severity level (info, warning, error)
        context: Additional context dict
    """
    if not SENTRY_AVAILABLE:
        logger.log(level, message, context=context)
        return

    with sentry_sdk.push_scope() as scope:
        # Add custom context
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: Optional[str] = None, email: Optional[str] = None, **kwargs):
    """
    Set user context for error tracking

    Args:
        user_id: User ID
        email: User email (will be filtered for PII)
        **kwargs: Additional user attributes
    """
    if not SENTRY_AVAILABLE:
        return

    user_data = {}

    if user_id:
        user_data["id"] = user_id

    # Don't send actual email for privacy
    if email:
        user_data["email_domain"] = email.split("@")[-1] if "@" in email else None

    user_data.update(kwargs)

    sentry_sdk.set_user(user_data)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", data: Optional[dict] = None):
    """
    Add a breadcrumb for debugging

    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Severity level
        data: Additional data
    """
    if not SENTRY_AVAILABLE:
        return

    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {}
    )


def start_transaction(name: str, op: str = "function") -> Optional["sentry_sdk.tracing.Transaction"]:
    """
    Start a performance transaction

    Args:
        name: Transaction name
        op: Operation type (function, http.request, db.query, etc.)

    Returns:
        Transaction context manager or None
    """
    if not SENTRY_AVAILABLE:
        return None

    return sentry_sdk.start_transaction(name=name, op=op)


# Health check helper
def is_sentry_enabled() -> bool:
    """Check if Sentry is enabled and initialized"""
    return SENTRY_AVAILABLE and os.getenv("SENTRY_DSN") is not None
