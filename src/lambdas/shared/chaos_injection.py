"""
Chaos Injection Helper
======================

Helper module for detecting active chaos experiments and coordinating
chaos injection across Lambda functions.

Phase 3: NewsAPI Failure Simulation
------------------------------------
Allows ingestion Lambda to detect when newsapi_failure experiment is active
and skip NewsAPI calls gracefully.

Safety Design:
--------------
- Fail-safe: Returns False on any errors (never blocks normal operation)
- Environment-aware: Only checks chaos state in preprod/dev/test
- Read-only: Only queries DynamoDB, never modifies state
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Environment detection
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Chaos experiments table (optional - for preprod/dev only)
CHAOS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")

# Cache boto3 clients (Lambda container reuse)
_dynamodb_client: any | None = None


def _get_dynamodb():
    """Get cached DynamoDB resource."""
    global _dynamodb_client
    if _dynamodb_client is None:
        region = os.environ.get("CLOUD_REGION") or os.environ.get("AWS_REGION")
        _dynamodb_client = boto3.resource("dynamodb", region_name=region)
    return _dynamodb_client


def is_chaos_active(scenario_type: str) -> bool:
    """
    Check if a chaos experiment of given type is currently active.

    Args:
        scenario_type: Type of chaos scenario (e.g., "newsapi_failure", "dynamodb_throttle")

    Returns:
        True if active experiment found, False otherwise

    Safety:
        - Returns False if chaos table not configured (production safety)
        - Returns False if not in preprod/dev/test environment
        - Returns False on any errors (fail-safe)
        - Logs warnings when chaos is active for visibility

    Example:
        >>> if is_chaos_active("newsapi_failure"):
        ...     logger.warning("Skipping NewsAPI due to active chaos experiment")
        ...     return empty_result
    """
    # Production safety: Never check chaos state in prod
    if ENVIRONMENT not in ["preprod", "dev", "test"]:
        return False

    # If chaos table not configured, no chaos testing available
    if not CHAOS_TABLE:
        return False

    try:
        table = _get_dynamodb().Table(CHAOS_TABLE)

        # Query by_status GSI for running experiments of this type
        response = table.query(
            IndexName="by_status",
            KeyConditionExpression="status = :status",
            FilterExpression="scenario_type = :scenario_type",
            ExpressionAttributeValues={
                ":status": "running",
                ":scenario_type": scenario_type,
            },
            Limit=1,
        )

        has_active_experiment = len(response.get("Items", [])) > 0

        if has_active_experiment:
            logger.warning(
                "Chaos injection active",
                extra={
                    "scenario_type": scenario_type,
                    "environment": ENVIRONMENT,
                },
            )

        return has_active_experiment

    except ClientError as e:
        # Fail-safe: On DynamoDB errors, assume no chaos active
        logger.error(
            "Failed to check chaos experiment status",
            extra={"scenario_type": scenario_type, "error": str(e)},
        )
        return False

    except Exception as e:
        # Fail-safe: On any unexpected errors, assume no chaos active
        logger.error(
            "Unexpected error checking chaos status",
            extra={"scenario_type": scenario_type, "error": str(e)},
        )
        return False
