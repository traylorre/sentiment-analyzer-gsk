"""URL decoding utilities for path parameters.

UNWIRED (repo cleanup inventory, docs/cleanup-pristine/open-questions.md Q12):
this module has ZERO production callers - only tests import it. It implements
X-Ray-spec path-parameter decoding; handlers were never converted to use it. The wiring was never built. Kept in tree as a signpost, not dead weight:
either wire it or formally descope the requirement before deleting.


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
