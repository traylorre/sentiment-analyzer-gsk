"""
Standardized Error Response Helper
==================================

Provides consistent error response formatting across all Lambda functions.

For On-Call Engineers:
    Error codes and their meanings:
    - RATE_LIMIT_EXCEEDED: External API throttling (NewsAPI, etc.)
    - VALIDATION_ERROR: Input validation failure
    - NOT_FOUND: Resource not found
    - SECRET_ERROR: Secrets Manager failure
    - DATABASE_ERROR: DynamoDB operation failure
    - INTERNAL_ERROR: Unexpected server error
    - UNAUTHORIZED: Authentication failure
    - MODEL_ERROR: Sentiment model failure

    Search logs by error code:
    aws logs filter-log-events \
      --log-group-name /aws/lambda/dev-sentiment-ingestion \
      --filter-pattern "RATE_LIMIT_EXCEEDED"

    See ON_CALL_SOP.md for specific error handling procedures.

For Developers:
    - Use error_response() for all API error responses
    - Include request_id from Lambda context for correlation
    - Use appropriate error code from ErrorCode enum
    - Add details dict for debugging info (not exposed to users)

Security Notes:
    - Never expose internal error details to end users
    - Log full details server-side, return sanitized response
    - request_id enables correlation without exposing internals
"""

import json
import logging
from enum import Enum
from typing import Any

# Structured logging
logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """
    Standardized error codes for machine-readable error handling.

    Use these codes consistently across all Lambda functions.

    On-Call Note:
        These codes appear in logs and can be used for filtering:
        filter @message like /RATE_LIMIT_EXCEEDED/
    """

    # External API errors
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Input/validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"

    # Infrastructure errors
    SECRET_ERROR = "SECRET_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Authentication/authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Internal errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


def error_response(
    status_code: int,
    message: str,
    code: str | ErrorCode,
    request_id: str,
    details: dict[str, Any] | None = None,
    log_error: bool = True,
) -> dict[str, Any]:
    """
    Create a standardized error response for Lambda API responses.

    Response format matches plan.md "Standardized Error Response Schema":
    {
        "statusCode": 500,
        "body": {
            "error": "Human readable message",
            "code": "MACHINE_READABLE_CODE",
            "details": {},
            "request_id": "lambda-request-id-123"
        }
    }

    Args:
        status_code: HTTP status code (400, 401, 404, 500, etc.)
        message: Human-readable error message
        code: Machine-readable error code (from ErrorCode enum)
        request_id: Lambda request ID for correlation
        details: Additional details for debugging (logged, optionally returned)
        log_error: Whether to log the error (default True)

    Returns:
        Lambda-compatible response dict with statusCode and JSON body

    Example:
        >>> from aws_lambda_powertools.utilities.typing import LambdaContext
        >>> def handler(event, context: LambdaContext):
        ...     try:
        ...         # ... processing
        ...     except ValidationError as e:
        ...         return error_response(
        ...             400,
        ...             "Invalid input",
        ...             ErrorCode.VALIDATION_ERROR,
        ...             context.aws_request_id,
        ...             details={"field": str(e)},
        ...         )

    On-Call Note:
        All errors are logged with full details. Use request_id to find
        the corresponding log entry for debugging.
    """
    # Convert ErrorCode enum to string if needed
    error_code = code.value if isinstance(code, ErrorCode) else code

    # Build response body
    body = {
        "error": message,
        "code": error_code,
        "request_id": request_id,
    }

    # Include details if provided (for debugging)
    if details:
        body["details"] = details

    # Log the error
    if log_error:
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        logger.log(
            log_level,
            message,
            extra={
                "status_code": status_code,
                "error_code": error_code,
                "request_id": request_id,
                "details": details,
            },
        )

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
        },
        "body": json.dumps(body),
    }


def validation_error(
    message: str,
    request_id: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a 400 validation error response.

    Convenience function for the most common error type.

    Args:
        message: Error message
        request_id: Lambda request ID
        field: Specific field that failed validation
        details: Additional details

    Returns:
        Lambda error response dict

    Example:
        >>> return validation_error(
        ...     "Invalid score value",
        ...     context.aws_request_id,
        ...     field="score",
        ... )
    """
    error_details = details or {}
    if field:
        error_details["field"] = field

    return error_response(
        400,
        message,
        ErrorCode.VALIDATION_ERROR,
        request_id,
        details=error_details if error_details else None,
    )


def not_found_error(
    message: str,
    request_id: str,
    resource: str | None = None,
) -> dict[str, Any]:
    """
    Create a 404 not found error response.

    Args:
        message: Error message
        request_id: Lambda request ID
        resource: Resource identifier that wasn't found

    Returns:
        Lambda error response dict
    """
    details = {"resource": resource} if resource else None

    return error_response(
        404,
        message,
        ErrorCode.NOT_FOUND,
        request_id,
        details=details,
    )


def unauthorized_error(
    request_id: str,
    message: str = "Authentication required",
) -> dict[str, Any]:
    """
    Create a 401 unauthorized error response.

    Args:
        request_id: Lambda request ID
        message: Error message

    Returns:
        Lambda error response dict

    On-Call Note:
        This usually means invalid or missing API key.
        Check dashboard API key in Secrets Manager.
    """
    return error_response(
        401,
        message,
        ErrorCode.UNAUTHORIZED,
        request_id,
    )


def rate_limit_error(
    request_id: str,
    service: str = "external API",
    retry_after: int | None = None,
) -> dict[str, Any]:
    """
    Create a 429 rate limit error response.

    Args:
        request_id: Lambda request ID
        service: Service that rate limited us
        retry_after: Seconds until retry is allowed

    Returns:
        Lambda error response dict

    On-Call Note:
        See SC-07 in ON_CALL_SOP.md for NewsAPI rate limit handling.
    """
    details = {"service": service}
    if retry_after:
        details["retry_after_seconds"] = retry_after

    response = error_response(
        429,
        f"Rate limited by {service}",
        ErrorCode.RATE_LIMIT_EXCEEDED,
        request_id,
        details=details,
    )

    # Add Retry-After header if provided
    if retry_after:
        response["headers"]["Retry-After"] = str(retry_after)

    return response


def internal_error(
    request_id: str,
    message: str = "Internal server error",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a 500 internal server error response.

    Use for unexpected errors. Full details are logged but not returned.

    Args:
        request_id: Lambda request ID
        message: Error message (generic for security)
        details: Details for logging only

    Returns:
        Lambda error response dict

    Security Note:
        Never expose internal error details to end users.
        Details are logged server-side only.
    """
    # Log full details
    if details:
        logger.error(
            f"Internal error details: {details}",
            extra={"request_id": request_id},
        )

    # Return sanitized response (no details)
    return error_response(
        500,
        message,
        ErrorCode.INTERNAL_ERROR,
        request_id,
        details=None,  # Don't expose internals
        log_error=False,  # Already logged above
    )


def database_error(
    request_id: str,
    operation: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a 500 database error response.

    Args:
        request_id: Lambda request ID
        operation: Database operation that failed
        details: Error details for logging

    Returns:
        Lambda error response dict

    On-Call Note:
        Check DynamoDB CloudWatch metrics and alarms.
        See SC-01, SC-02 in ON_CALL_SOP.md.
    """
    return error_response(
        500,
        f"Database operation failed: {operation}",
        ErrorCode.DATABASE_ERROR,
        request_id,
        details=details,
    )


def secret_error(
    request_id: str,
    secret_id: str,
) -> dict[str, Any]:
    """
    Create a 500 secret retrieval error response.

    Args:
        request_id: Lambda request ID
        secret_id: Secret that failed to load (only name, not value)

    Returns:
        Lambda error response dict

    On-Call Note:
        Check Secrets Manager access:
        aws secretsmanager describe-secret --secret-id <id>
        See SC-03, SC-05 in ON_CALL_SOP.md.
    """
    return error_response(
        500,
        "Failed to retrieve configuration",
        ErrorCode.SECRET_ERROR,
        request_id,
        details={"secret_id": secret_id},
    )


def model_error(
    request_id: str,
    message: str = "Sentiment analysis failed",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a 500 model error response.

    Args:
        request_id: Lambda request ID
        message: Error message
        details: Error details for logging

    Returns:
        Lambda error response dict

    On-Call Note:
        Check Analysis Lambda logs for model loading issues.
        Verify Lambda layer is correctly attached.
        See SC-04 in ON_CALL_SOP.md.
    """
    return error_response(
        500,
        message,
        ErrorCode.MODEL_ERROR,
        request_id,
        details=details,
    )
