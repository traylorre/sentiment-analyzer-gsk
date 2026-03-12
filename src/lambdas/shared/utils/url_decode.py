"""URL decoding utilities for path parameters.

API Gateway passes URL-encoded path parameters (e.g., BRK%2EB for BRK.B).
This module provides consistent decoding.

References:
    FR-044: URL-decode path parameters
"""

import urllib.parse


def decode_path_param(value: str) -> str:
    """Decode a URL-encoded path parameter.

    Args:
        value: URL-encoded string from pathParameters.

    Returns:
        Decoded string (e.g., "BRK%2EB" → "BRK.B").
    """
    return urllib.parse.unquote(value)
