"""Event helper utilities for API Gateway Proxy Integration events.

Provides case-insensitive header lookup and null-safe parameter extraction
for Lambda handlers operating on raw API Gateway event dicts.

References:
    FR-043: null queryStringParameters/pathParameters → empty dict
    FR-061: Case-insensitive header lookup
    R7: Header case normalization
"""


def get_header(event: dict, name: str, default: str | None = None) -> str | None:
    """Get a header value with case-insensitive lookup.

    API Gateway normalizes all headers to lowercase in the event dict.
    This utility ensures consistent access regardless of how callers
    specify the header name.

    Args:
        event: API Gateway Proxy Integration event dict.
        name: Header name (any case).
        default: Value to return if header is not present.

    Returns:
        Header value or default.
    """
    headers = event.get("headers") or {}
    return headers.get(name.lower(), default)


def get_query_params(event: dict) -> dict[str, str]:
    """Get query string parameters, returning empty dict on None.

    API Gateway sends null (Python None) for queryStringParameters
    when no query string is present.

    Args:
        event: API Gateway Proxy Integration event dict.

    Returns:
        Query parameters dict, never None.
    """
    return event.get("queryStringParameters") or {}


def get_path_params(event: dict) -> dict[str, str]:
    """Get path parameters, returning empty dict on None.

    API Gateway sends null (Python None) for pathParameters
    when no path parameters are defined.

    Args:
        event: API Gateway Proxy Integration event dict.

    Returns:
        Path parameters dict, never None.
    """
    return event.get("pathParameters") or {}
