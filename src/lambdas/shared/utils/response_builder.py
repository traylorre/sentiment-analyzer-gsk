"""Response builder utilities for API Gateway Proxy Integration responses.

Provides standardized response construction using orjson for serialization.
Produces responses in the exact API Gateway Proxy Integration format:
    {"statusCode": int, "headers": dict, "body": str, "isBase64Encoded": bool}

References:
    FR-005: All dashboard responses use proxy integration dicts
    FR-009: 422 validation errors in FastAPI-parity format
    FR-011: orjson for JSON serialization
"""

import orjson
from pydantic import ValidationError


def json_response(
    status_code: int,
    body: dict | list,
    headers: dict[str, str] | None = None,
) -> dict:
    """Build a JSON API Gateway Proxy Integration response.

    Args:
        status_code: HTTP status code.
        body: Response body (will be serialized with orjson).
        headers: Additional response headers.

    Returns:
        API Gateway Proxy Integration response dict.
    """
    response_headers = {"Content-Type": "application/json"}
    if headers:
        response_headers.update(headers)
    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": orjson.dumps(body).decode(),
        "isBase64Encoded": False,
    }


def error_response(status_code: int, detail: str) -> dict:
    """Build an error response with a detail message.

    Args:
        status_code: HTTP error status code.
        detail: Human-readable error message.

    Returns:
        API Gateway Proxy Integration response dict.
    """
    return json_response(status_code, {"detail": detail})


def validation_error_response(exc: ValidationError) -> dict:
    """Build a 422 validation error response in FastAPI-parity format.

    Produces: {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
    This format is byte-identical to FastAPI's automatic 422 responses,
    ensuring frontend compatibility.

    Args:
        exc: Pydantic ValidationError instance.

    Returns:
        API Gateway Proxy Integration response dict with 422 status.
    """
    return json_response(422, {"detail": exc.errors()})
