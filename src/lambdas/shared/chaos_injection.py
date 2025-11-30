"""
Chaos Injection Helper
======================

Helper module for detecting active chaos experiments and coordinating
chaos injection across Lambda functions.

Phase 3: API Failure Simulation
--------------------------------
Allows ingestion Lambda to detect when api_failure experiment is active
and skip Tiingo/Finnhub API calls gracefully.

Phase 4: Lambda Cold Start Delays
----------------------------------
Allows any Lambda to inject configurable delays at handler entry to simulate
cold start performance degradation.

Safety Design:
--------------
- Fail-safe: Returns False/0 on any errors (never blocks normal operation)
- Environment-aware: Only checks chaos state in preprod/dev/test
- Read-only: Only queries DynamoDB, never modifies state
"""

import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Cache boto3 clients (Lambda container reuse)
_dynamodb_client: Any | None = None


def _get_dynamodb() -> Any:
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
        scenario_type: Type of chaos scenario (e.g., "api_failure", "dynamodb_throttle")

    Returns:
        True if active experiment found, False otherwise

    Safety:
        - Returns False if chaos table not configured (production safety)
        - Returns False if not in preprod/dev/test environment
        - Returns False on any errors (fail-safe)
        - Logs warnings when chaos is active for visibility

    Example:
        >>> if is_chaos_active("api_failure"):
        ...     logger.warning("Skipping Tiingo/Finnhub due to active chaos experiment")
        ...     return empty_result
    """
    # Read environment variables at call time for testability
    environment = os.environ.get("ENVIRONMENT", "dev")
    chaos_table = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")

    # Production safety: Never check chaos state in prod
    if environment not in ["preprod", "dev", "test"]:
        return False

    # If chaos table not configured, no chaos testing available
    if not chaos_table:
        return False

    try:
        table = _get_dynamodb().Table(chaos_table)

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
                    "environment": environment,
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


def get_chaos_delay_ms(scenario_type: str) -> int:
    """
    Get delay in milliseconds for chaos experiment.

    Args:
        scenario_type: Type of chaos scenario (e.g., "lambda_cold_start")

    Returns:
        Delay in milliseconds, or 0 if no active experiment

    Safety:
        - Returns 0 on any errors (fail-safe)
        - Only checks in preprod/dev/test environments
        - Never blocks Lambda execution

    Example:
        >>> delay_ms = get_chaos_delay_ms("lambda_cold_start")
        >>> if delay_ms > 0:
        ...     time.sleep(delay_ms / 1000.0)
    """
    # Read environment variables at call time for testability
    environment = os.environ.get("ENVIRONMENT", "dev")
    chaos_table = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")

    # Production safety: Never inject delays in prod
    if environment not in ["preprod", "dev", "test"]:
        return 0

    # If chaos table not configured, no chaos testing available
    if not chaos_table:
        return 0

    try:
        table = _get_dynamodb().Table(chaos_table)

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

        if not response.get("Items"):
            return 0

        experiment = response["Items"][0]
        delay_ms = experiment.get("results", {}).get("delay_ms", 0)

        if delay_ms > 0:
            logger.info(
                f"Chaos delay injection active: {delay_ms}ms",
                extra={
                    "scenario_type": scenario_type,
                    "delay_ms": delay_ms,
                    "environment": environment,
                },
            )

        return int(delay_ms)

    except ClientError as e:
        # Fail-safe: On DynamoDB errors, assume no delay
        logger.error(
            "Failed to get chaos delay",
            extra={"scenario_type": scenario_type, "error": str(e)},
        )
        return 0

    except Exception as e:
        # Fail-safe: On any unexpected errors, assume no delay
        logger.error(
            "Unexpected error getting chaos delay",
            extra={"scenario_type": scenario_type, "error": str(e)},
        )
        return 0
