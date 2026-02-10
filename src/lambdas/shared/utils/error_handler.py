"""Top-level error handler for Lambda handlers (FR-023, FR-024, FR-039).

Wraps handler functions in try/except to produce structured error responses.
Converts Pydantic ValidationError to 422, and all other exceptions to 500
with full traceback logging. No fallbacks — fail fast with structured errors.

Usage:
    from src.lambdas.shared.utils.error_handler import handle_request

    def lambda_handler(event, context):
        return handle_request(_handle, event, context)

    def _handle(event, context):
        # Business logic here
        ...
"""

import logging
import traceback

from pydantic import ValidationError

from src.lambdas.shared.utils.response_builder import (
    error_response,
    validation_error_response,
)

logger = logging.getLogger(__name__)


def handle_request(handler_fn, event: dict, context) -> dict:
    """Execute a handler function with structured error handling.

    Catches and converts exceptions to API Gateway Proxy Integration
    response dicts. Logs full tracebacks for 500 errors.

    Args:
        handler_fn: The handler function to execute. Must accept (event, context)
            and return an API Gateway Proxy Integration response dict.
        event: API Gateway Proxy Integration event dict.
        context: Lambda context object.

    Returns:
        API Gateway Proxy Integration response dict. On success, returns
        whatever handler_fn returns. On error, returns a structured error
        response with appropriate status code.
    """
    try:
        return handler_fn(event, context)
    except ValidationError as exc:
        logger.warning(
            "Validation error",
            extra={
                "path": event.get("path", "unknown"),
                "method": event.get("httpMethod", "unknown"),
                "error_count": len(exc.errors()),
            },
        )
        return validation_error_response(exc)
    except Exception as exc:
        logger.error(
            "Unhandled exception in handler",
            extra={
                "path": event.get("path", "unknown"),
                "method": event.get("httpMethod", "unknown"),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        return error_response(500, "Internal server error")
