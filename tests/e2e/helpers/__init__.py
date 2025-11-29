# E2E Test Helpers
#
# Utilities for interacting with the preprod environment during E2E tests.
# Includes API client wrappers, auth flow helpers, CloudWatch/X-Ray query
# utilities, and test data cleanup functions.

from tests.e2e.helpers.api_client import PreprodAPIClient
from tests.e2e.helpers.auth import (
    AnonymousSession,
    AuthenticatedSession,
    OAuthURLs,
    create_anonymous_session,
    get_oauth_urls,
    refresh_tokens,
    request_magic_link,
    sign_out,
    validate_session,
    verify_magic_link,
)
from tests.e2e.helpers.cleanup import (
    OrphanedTestData,
    cleanup_by_prefix,
    cleanup_orphaned_data,
    cleanup_test_config,
    cleanup_test_user,
    find_orphaned_test_data,
)
from tests.e2e.helpers.cloudwatch import (
    LogEntry,
    MetricDataPoint,
    get_cloudwatch_metrics,
    query_cloudwatch_logs,
    query_logs_by_request_id,
    verify_metric_incremented,
    wait_for_log_entry,
)
from tests.e2e.helpers.xray import (
    Trace,
    TraceSegment,
    get_segment_by_name,
    get_xray_trace,
    parse_trace_id_from_header,
    trace_has_annotation,
    validate_cross_lambda_trace,
    validate_trace_segments,
    wait_for_trace_with_segment,
)

__all__ = [
    # API Client
    "PreprodAPIClient",
    # Auth helpers
    "AnonymousSession",
    "AuthenticatedSession",
    "OAuthURLs",
    "create_anonymous_session",
    "request_magic_link",
    "verify_magic_link",
    "get_oauth_urls",
    "refresh_tokens",
    "sign_out",
    "validate_session",
    # CloudWatch helpers
    "LogEntry",
    "MetricDataPoint",
    "query_cloudwatch_logs",
    "query_logs_by_request_id",
    "get_cloudwatch_metrics",
    "wait_for_log_entry",
    "verify_metric_incremented",
    # X-Ray helpers
    "Trace",
    "TraceSegment",
    "get_xray_trace",
    "get_segment_by_name",
    "parse_trace_id_from_header",
    "trace_has_annotation",
    "validate_trace_segments",
    "validate_cross_lambda_trace",
    "wait_for_trace_with_segment",
    # Cleanup helpers
    "OrphanedTestData",
    "cleanup_by_prefix",
    "cleanup_orphaned_data",
    "cleanup_test_config",
    "cleanup_test_user",
    "find_orphaned_test_data",
]
