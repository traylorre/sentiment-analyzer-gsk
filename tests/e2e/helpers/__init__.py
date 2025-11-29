# E2E Test Helpers
#
# Utilities for interacting with the preprod environment during E2E tests.
# Includes API client wrappers, auth flow helpers, CloudWatch/X-Ray query
# utilities, and test data cleanup functions.

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api_client import PreprodAPIClient
    from .auth import (
        create_anonymous_session,
        get_oauth_urls,
        refresh_tokens,
        request_magic_link,
        verify_magic_link,
    )
    from .cleanup import cleanup_by_prefix, find_orphaned_test_data
    from .cloudwatch import get_cloudwatch_metrics, query_cloudwatch_logs
    from .xray import get_xray_trace, validate_trace_segments

__all__ = [
    # API Client
    "PreprodAPIClient",
    # Auth helpers
    "create_anonymous_session",
    "request_magic_link",
    "verify_magic_link",
    "get_oauth_urls",
    "refresh_tokens",
    # CloudWatch helpers
    "query_cloudwatch_logs",
    "get_cloudwatch_metrics",
    # X-Ray helpers
    "get_xray_trace",
    "validate_trace_segments",
    # Cleanup helpers
    "cleanup_by_prefix",
    "find_orphaned_test_data",
]
