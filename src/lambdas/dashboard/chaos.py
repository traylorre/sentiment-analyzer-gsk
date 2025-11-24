"""
Chaos Testing Module
====================

Manages chaos experiments for testing system resilience.

Experiment Lifecycle:
    1. Create experiment (POST /chaos/experiments)
    2. Start experiment (POST /chaos/experiments/{id}/start)
    3. Monitor experiment (GET /chaos/experiments/{id})
    4. Stop experiment (POST /chaos/experiments/{id}/stop)
    5. View history (GET /chaos/experiments)

Safety Mechanisms:
    - Environment gating (preprod only)
    - Time limits (5-300 seconds)
    - Blast radius controls (10-100%)
    - CloudWatch alarm kill switches (Phase 2)
    - Manual emergency stop

Supported Scenarios (Phase 1):
    - dynamodb_throttle: Throttle DynamoDB writes (AWS FIS - Phase 2)
    - newsapi_failure: Simulate NewsAPI unavailability (Phase 3)
    - lambda_cold_start: Inject artificial delay (Phase 4)
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.lambdas.shared.logging_utils import get_safe_error_info

logger = logging.getLogger(__name__)

# Configuration
CHAOS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")
ENVIRONMENT = os.environ["ENVIRONMENT"]

# Safety: Only allow chaos testing in preprod
ALLOWED_ENVIRONMENTS = ["preprod", "dev", "test"]

# DynamoDB client
dynamodb = boto3.resource("dynamodb")


class ChaosError(Exception):
    """Base exception for chaos testing errors."""

    pass


class EnvironmentNotAllowedError(ChaosError):
    """Raised when attempting chaos testing in disallowed environment."""

    pass


def check_environment_allowed():
    """
    Verify chaos testing is allowed in current environment.

    Raises:
        EnvironmentNotAllowedError: If chaos testing not allowed in this environment
    """
    if ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
        raise EnvironmentNotAllowedError(
            f"Chaos testing not allowed in {ENVIRONMENT} environment. "
            f"Allowed environments: {', '.join(ALLOWED_ENVIRONMENTS)}"
        )


def create_experiment(
    scenario_type: str,
    blast_radius: int,
    duration_seconds: int,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new chaos experiment.

    Args:
        scenario_type: Type of chaos scenario (dynamodb_throttle|newsapi_failure|lambda_cold_start)
        blast_radius: Percentage of requests to affect (10-100)
        duration_seconds: Duration in seconds (5-300)
        parameters: Optional scenario-specific parameters

    Returns:
        Created experiment dict

    Raises:
        EnvironmentNotAllowedError: If environment not allowed
        ValueError: If parameters invalid
        ChaosError: If creation fails
    """
    check_environment_allowed()

    # Validate parameters
    valid_scenarios = ["dynamodb_throttle", "newsapi_failure", "lambda_cold_start"]
    if scenario_type not in valid_scenarios:
        raise ValueError(
            f"Invalid scenario_type: {scenario_type}. "
            f"Must be one of: {', '.join(valid_scenarios)}"
        )

    if not 10 <= blast_radius <= 100:
        raise ValueError(f"blast_radius must be 10-100, got: {blast_radius}")

    if not 5 <= duration_seconds <= 300:
        raise ValueError(f"duration_seconds must be 5-300, got: {duration_seconds}")

    # Generate experiment
    experiment_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    ttl_timestamp = int((datetime.utcnow() + timedelta(days=7)).timestamp())

    experiment = {
        "experiment_id": experiment_id,
        "created_at": created_at,
        "status": "pending",
        "scenario_type": scenario_type,
        "blast_radius": blast_radius,
        "duration_seconds": duration_seconds,
        "parameters": parameters or {},
        "results": {},
        "environment": ENVIRONMENT,
        "ttl_timestamp": ttl_timestamp,
    }

    try:
        table = dynamodb.Table(CHAOS_TABLE)
        table.put_item(Item=experiment)

        logger.info(
            "Chaos experiment created",
            extra={
                "experiment_id": experiment_id,
                "scenario_type": scenario_type,
                "blast_radius": blast_radius,
                "duration_seconds": duration_seconds,
            },
        )

        return experiment

    except ClientError as e:
        logger.error(
            "Failed to create chaos experiment",
            extra={"scenario_type": scenario_type, **get_safe_error_info(e)},
        )
        raise ChaosError(f"Failed to create experiment: {e}") from e


def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    """
    Get experiment by ID.

    Args:
        experiment_id: Experiment UUID

    Returns:
        Experiment dict or None if not found
    """
    try:
        table = dynamodb.Table(CHAOS_TABLE)
        response = table.get_item(Key={"experiment_id": experiment_id})

        if "Item" not in response:
            return None

        # Convert Decimal to int/float for JSON serialization
        item = response["Item"]
        return _deserialize_dynamodb_item(item)

    except ClientError as e:
        logger.error(
            "Failed to get chaos experiment",
            extra={"experiment_id": experiment_id, **get_safe_error_info(e)},
        )
        return None


def list_experiments(
    status: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """
    List experiments with optional status filter.

    Args:
        status: Optional status filter (pending|running|completed|failed|stopped)
        limit: Maximum experiments to return (default: 20, max: 100)

    Returns:
        List of experiment dicts
    """
    if limit < 1 or limit > 100:
        raise ValueError(f"limit must be 1-100, got: {limit}")

    try:
        table = dynamodb.Table(CHAOS_TABLE)

        if status:
            # Query by status GSI
            response = table.query(
                IndexName="by_status",
                KeyConditionExpression="status = :status",
                ExpressionAttributeValues={":status": status},
                ScanIndexForward=False,  # Most recent first
                Limit=limit,
            )
        else:
            # Scan entire table (expensive, but OK for small tables)
            response = table.scan(Limit=limit)

        items = response.get("Items", [])
        return [_deserialize_dynamodb_item(item) for item in items]

    except ClientError as e:
        logger.error(
            "Failed to list chaos experiments",
            extra={"status": status, **get_safe_error_info(e)},
        )
        return []


def update_experiment_status(
    experiment_id: str,
    status: str,
    results: dict[str, Any] | None = None,
) -> bool:
    """
    Update experiment status and results.

    Args:
        experiment_id: Experiment UUID
        status: New status (pending|running|completed|failed|stopped)
        results: Optional results dict

    Returns:
        True if updated successfully
    """
    valid_statuses = ["pending", "running", "completed", "failed", "stopped"]
    if status not in valid_statuses:
        raise ValueError(
            f"Invalid status: {status}. Must be one of: {', '.join(valid_statuses)}"
        )

    try:
        table = dynamodb.Table(CHAOS_TABLE)

        update_expr = "SET #status = :status, updated_at = :updated_at"
        expr_attr_names = {"#status": "status"}
        expr_attr_values = {
            ":status": status,
            ":updated_at": datetime.utcnow().isoformat() + "Z",
        }

        if results:
            update_expr += ", results = :results"
            expr_attr_values[":results"] = results

        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )

        logger.info(
            "Chaos experiment status updated",
            extra={"experiment_id": experiment_id, "status": status},
        )

        return True

    except ClientError as e:
        logger.error(
            "Failed to update chaos experiment",
            extra={
                "experiment_id": experiment_id,
                "status": status,
                **get_safe_error_info(e),
            },
        )
        return False


def delete_experiment(experiment_id: str) -> bool:
    """
    Delete experiment by ID.

    Args:
        experiment_id: Experiment UUID

    Returns:
        True if deleted successfully
    """
    try:
        table = dynamodb.Table(CHAOS_TABLE)
        table.delete_item(Key={"experiment_id": experiment_id})

        logger.info(
            "Chaos experiment deleted",
            extra={"experiment_id": experiment_id},
        )

        return True

    except ClientError as e:
        logger.error(
            "Failed to delete chaos experiment",
            extra={"experiment_id": experiment_id, **get_safe_error_info(e)},
        )
        return False


def _deserialize_dynamodb_item(item: dict[str, Any]) -> dict[str, Any]:
    """
    Convert DynamoDB Decimal types to int/float for JSON serialization.

    Args:
        item: DynamoDB item dict

    Returns:
        JSON-serializable dict
    """
    result = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            result[key] = int(value) if value % 1 == 0 else float(value)
        elif isinstance(value, dict):
            result[key] = _deserialize_dynamodb_item(value)
        elif isinstance(value, list):
            result[key] = [
                _deserialize_dynamodb_item(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            result[key] = value
    return result
