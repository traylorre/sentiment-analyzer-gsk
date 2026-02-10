"""API Gateway event validation.

Validates that incoming events match the expected API Gateway Proxy
Integration format before processing.

References:
    FR-045: Validate event matches API Gateway Proxy format
"""

import logging

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"httpMethod", "path", "requestContext"}


class InvalidEventError(Exception):
    """Raised when an event does not match the API Gateway Proxy format."""


def validate_apigw_event(event: dict) -> None:
    """Validate that an event is an API Gateway Proxy Integration event.

    Checks for required keys that distinguish API Gateway events from
    other Lambda invocation sources (SNS, SQS, EventBridge, etc.).

    Args:
        event: Lambda event dict.

    Raises:
        InvalidEventError: If the event is missing required keys.
    """
    if not isinstance(event, dict):
        raise InvalidEventError(f"Event must be a dict, got {type(event).__name__}")

    missing = REQUIRED_KEYS - event.keys()
    if missing:
        raise InvalidEventError(
            f"Event missing required API Gateway keys: {sorted(missing)}"
        )
