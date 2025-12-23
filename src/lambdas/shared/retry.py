"""Retry utilities for transient AWS failures.

Feature 1032: Config API Stability
Provides retry decorators for DynamoDB and S3 operations.

For On-Call Engineers:
    - Retries are for TRANSIENT failures only (throttling, timeouts)
    - Validation errors and permissions errors are NOT retried
    - Each retry is logged with attempt number
    - Max 3 retries with exponential backoff (0.5s, 1s, 2s)
"""

import logging

from botocore.exceptions import ClientError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# DynamoDB error codes that are retryable (transient)
DYNAMODB_RETRYABLE_ERRORS = {
    "ProvisionedThroughputExceededException",
    "ThrottlingException",
    "InternalServerError",
    "ServiceUnavailable",
    "RequestLimitExceeded",
}

# S3 error codes that are retryable (transient)
S3_RETRYABLE_ERRORS = {
    "SlowDown",
    "InternalError",
    "ServiceUnavailable",
    "RequestTimeout",
    "RequestTimeTooSkewed",
}


def _is_dynamodb_retryable(exception: BaseException) -> bool:
    """Check if DynamoDB exception is retryable."""
    if not isinstance(exception, ClientError):
        return False
    error_code = exception.response.get("Error", {}).get("Code", "")
    return error_code in DYNAMODB_RETRYABLE_ERRORS


def _is_s3_retryable(exception: BaseException) -> bool:
    """Check if S3 exception is retryable."""
    if not isinstance(exception, ClientError):
        return False
    error_code = exception.response.get("Error", {}).get("Code", "")
    return error_code in S3_RETRYABLE_ERRORS


# Pre-configured retry decorator for DynamoDB operations
dynamodb_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception(_is_dynamodb_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Pre-configured retry decorator for S3 operations
s3_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception(_is_s3_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
