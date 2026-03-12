"""Response builder utilities for Powertools-based Lambda handlers.

Provides standardized response construction using orjson for serialization.
Returns Powertools Response objects compatible with APIGatewayRestResolver
route handlers and middleware.

References:
    FR-005: All dashboard responses use proxy integration dicts
    FR-009: 422 validation errors in standard format
    FR-011: orjson for JSON serialization
"""

import orjson
from aws_lambda_powertools.event_handler import Response
from pydantic import ValidationError


def json_response(
    status_code: int,
    body: dict | list,
    headers: dict[str, str] | None = None,
) -> Response:
    """Build a JSON response as a Powertools Response object.

    Args:
        status_code: HTTP status code.
        body: Response body (will be serialized with orjson).
        headers: Additional response headers.

    Returns:
        Powertools Response object.
    """
    return Response(
        status_code=status_code,
        content_type="application/json",
        body=orjson.dumps(body).decode(),
        headers=headers or {},
    )


def error_response(status_code: int, detail: str) -> Response:
    """Build an error response with a detail message.

    Args:
        status_code: HTTP error status code.
        detail: Human-readable error message.

    Returns:
        Powertools Response object.
    """
    return json_response(status_code, {"detail": detail})


def validation_error_response(exc: ValidationError) -> Response:
    """Build a 422 validation error response in standard format.

    Produces: {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
    This format follows the standard Pydantic ValidationError structure,
    ensuring frontend compatibility.

    Args:
        exc: Pydantic ValidationError instance.

    Returns:
        Powertools Response object with 422 status.
    """
    return json_response(422, {"detail": exc.errors()})
