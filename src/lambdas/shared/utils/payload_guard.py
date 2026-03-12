"""Response payload size guard.

API Gateway has a 6MB response payload limit for synchronous invocations.
This utility detects oversized responses before returning them, preventing
opaque 502 errors from API Gateway.

References:
    FR-046: Detect 6MB payload limit before returning
"""

import logging

logger = logging.getLogger(__name__)

# API Gateway payload limit: 6MB (6,291,456 bytes)
MAX_PAYLOAD_BYTES = 6_291_456


def check_response_size(body_str: str) -> str | None:
    """Check if a response body exceeds the API Gateway payload limit.

    Args:
        body_str: Serialized response body string.

    Returns:
        None if the body is within limits.
        Error message string if the body exceeds limits.
    """
    body_size = len(body_str.encode("utf-8"))
    if body_size > MAX_PAYLOAD_BYTES:
        logger.error(
            "Response payload exceeds 6MB limit",
            extra={
                "body_size_bytes": body_size,
                "limit_bytes": MAX_PAYLOAD_BYTES,
            },
        )
        return (
            f"Response payload ({body_size:,} bytes) exceeds "
            f"API Gateway 6MB limit ({MAX_PAYLOAD_BYTES:,} bytes)"
        )
    return None
