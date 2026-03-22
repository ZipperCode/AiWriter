"""Structured logging configuration using structlog."""
import contextvars
import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for storing request ID
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def add_request_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to add request_id from context to log events.

    Args:
        logger: The structlog logger instance
        method_name: The name of the method called on the logger
        event_dict: The event dictionary to be logged

    Returns:
        The event dictionary with request_id added if available
    """
    request_id = request_id_var.get()
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


def setup_logging(json_output: bool = True, log_level: str = "INFO") -> None:
    """Configure structlog with the specified settings.

    Args:
        json_output: If True, use JSON output format; otherwise use console format
        log_level: The minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if json_output:
        # JSON output for production
        processors = [
            add_request_id,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console output for development
        processors = [
            add_request_id,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            int(getattr(structlog.processors, log_level, 20))
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a bound structlog logger instance.

    Args:
        name: The name of the logger (usually __name__)

    Returns:
        A structlog bound logger with the module name bound
    """
    return structlog.get_logger(name)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to manage request IDs for structured logging.

    Assigns a unique request ID to each request:
    - Uses X-Request-ID header if provided
    - Generates a UUID if not provided
    - Stores the request ID in a context variable for use in logging
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process the request and assign a request ID.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response
        """
        # Get request ID from header or generate a new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Set the request ID in context variable
        token = request_id_var.set(request_id)

        try:
            # Process the request
            response = await call_next(request)
            # Add the request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Reset context variable
            request_id_var.reset(token)
