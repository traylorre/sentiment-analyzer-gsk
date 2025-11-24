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

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

logger = logging.getLogger(__name__)

# Configuration
CHAOS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")
ENVIRONMENT = os.environ["ENVIRONMENT"]
FIS_DYNAMODB_THROTTLE_TEMPLATE = os.environ.get("FIS_DYNAMODB_THROTTLE_TEMPLATE", "")

# Safety: Only allow chaos testing in preprod
ALLOWED_ENVIRONMENTS = ["preprod", "dev", "test"]

# AWS clients (lazy-loaded to avoid region errors during test imports)
_dynamodb = None
_fis_client = None


def _get_dynamodb():
    """Lazy-load DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_fis_client():
    """Lazy-load FIS client."""
    global _fis_client
    if _fis_client is None:
        _fis_client = boto3.client("fis")
    return _fis_client


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
        table = _get_dynamodb().Table(CHAOS_TABLE)
        table.put_item(Item=experiment)

        logger.info(
            "Chaos experiment created",
            extra={
                "experiment_id": experiment_id,
                "scenario_type": sanitize_for_log(scenario_type),
                "blast_radius": blast_radius,
                "duration_seconds": duration_seconds,
            },
        )

        return experiment

    except ClientError as e:
        logger.error(
            "Failed to create chaos experiment",
            extra={
                "scenario_type": sanitize_for_log(scenario_type),
                **get_safe_error_info(e),
            },
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
        table = _get_dynamodb().Table(CHAOS_TABLE)
        response = table.get_item(Key={"experiment_id": experiment_id})

        if "Item" not in response:
            return None

        # Convert Decimal to int/float for JSON serialization
        item = response["Item"]
        return _deserialize_dynamodb_item(item)

    except ClientError as e:
        logger.error(
            "Failed to get chaos experiment",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                **get_safe_error_info(e),
            },
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
        table = _get_dynamodb().Table(CHAOS_TABLE)

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
            extra={
                "status": sanitize_for_log(status) if status else None,
                **get_safe_error_info(e),
            },
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
        table = _get_dynamodb().Table(CHAOS_TABLE)

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
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "status": sanitize_for_log(status),
            },
        )

        return True

    except ClientError as e:
        logger.error(
            "Failed to update chaos experiment",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                "status": sanitize_for_log(status),
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
        table = _get_dynamodb().Table(CHAOS_TABLE)
        table.delete_item(Key={"experiment_id": experiment_id})

        logger.info(
            "Chaos experiment deleted",
            extra={"experiment_id": sanitize_for_log(experiment_id)},
        )

        return True

    except ClientError as e:
        logger.error(
            "Failed to delete chaos experiment",
            extra={
                "experiment_id": sanitize_for_log(experiment_id),
                **get_safe_error_info(e),
            },
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


# ===================================================================
# AWS FIS Integration (Phase 2)
# ===================================================================


def start_fis_experiment(
    experiment_id: str,
    blast_radius: int,
    duration_seconds: int,
) -> str:
    """
    Start an AWS FIS experiment for DynamoDB throttling.

    Args:
        experiment_id: Chaos experiment UUID (for tagging)
        blast_radius: Percentage of requests to affect (10-100)
        duration_seconds: Duration in seconds (5-300)

    Returns:
        FIS experiment ID

    Raises:
        ChaosError: If FIS experiment fails to start
    """
    check_environment_allowed()

    if not FIS_DYNAMODB_THROTTLE_TEMPLATE:
        raise ChaosError("FIS_DYNAMODB_THROTTLE_TEMPLATE environment variable not set")

    # Note: FIS experiment template already defines duration (PT5M).
    # blast_radius and duration_seconds are passed as tags for tracking only.

    try:
        response = _get_fis_client().start_experiment(
            experimentTemplateId=FIS_DYNAMODB_THROTTLE_TEMPLATE,
            tags={
                "chaos_experiment_id": experiment_id,
                "environment": ENVIRONMENT,
                "blast_radius": str(blast_radius),
            },
        )

        fis_experiment_id = response["experiment"]["id"]

        logger.info(
            "FIS experiment started",
            extra={
                "chaos_experiment_id": sanitize_for_log(experiment_id),
                "fis_experiment_id": sanitize_for_log(fis_experiment_id),
                "blast_radius": blast_radius,
                "duration_seconds": duration_seconds,
            },
        )

        return fis_experiment_id

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            "Failed to start FIS experiment",
            extra={
                "chaos_experiment_id": sanitize_for_log(experiment_id),
                "error_code": sanitize_for_log(error_code),
                "error_message": sanitize_for_log(error_msg),
            },
        )

        raise ChaosError(
            f"FIS experiment failed to start: {error_code} - {error_msg}"
        ) from e


def stop_fis_experiment(fis_experiment_id: str) -> bool:
    """
    Stop a running AWS FIS experiment.

    Args:
        fis_experiment_id: FIS experiment ID

    Returns:
        True if stopped successfully

    Raises:
        ChaosError: If FIS experiment fails to stop
    """
    check_environment_allowed()

    try:
        _get_fis_client().stop_experiment(id=fis_experiment_id)

        logger.info(
            "FIS experiment stopped",
            extra={"fis_experiment_id": sanitize_for_log(fis_experiment_id)},
        )

        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            "Failed to stop FIS experiment",
            extra={
                "fis_experiment_id": sanitize_for_log(fis_experiment_id),
                "error_code": sanitize_for_log(error_code),
                "error_message": sanitize_for_log(error_msg),
            },
        )

        raise ChaosError(
            f"FIS experiment failed to stop: {error_code} - {error_msg}"
        ) from e


def get_fis_experiment_status(fis_experiment_id: str) -> dict[str, Any]:
    """
    Get status of an AWS FIS experiment.

    Args:
        fis_experiment_id: FIS experiment ID

    Returns:
        FIS experiment status dict

    Raises:
        ChaosError: If failed to get status
    """
    try:
        response = _get_fis_client().get_experiment(id=fis_experiment_id)
        experiment = response["experiment"]

        return {
            "id": experiment["id"],
            "state": experiment["state"]["status"],
            "reason": experiment["state"].get("reason", ""),
            "created_time": experiment["creationTime"].isoformat(),
            "start_time": experiment.get("startTime", {}).isoformat()
            if experiment.get("startTime")
            else None,
            "end_time": experiment.get("endTime", {}).isoformat()
            if experiment.get("endTime")
            else None,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            "Failed to get FIS experiment status",
            extra={
                "fis_experiment_id": sanitize_for_log(fis_experiment_id),
                "error_code": sanitize_for_log(error_code),
                "error_message": sanitize_for_log(error_msg),
            },
        )

        raise ChaosError(
            f"Failed to get FIS experiment status: {error_code} - {error_msg}"
        ) from e


def start_experiment(experiment_id: str) -> dict[str, Any]:
    """
    Start a chaos experiment.

    Args:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment dict

    Raises:
        ChaosError: If experiment fails to start
    """
    check_environment_allowed()

    # Get experiment details
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise ChaosError(f"Experiment not found: {experiment_id}")

    if experiment["status"] != "pending":
        raise ChaosError(
            f"Experiment must be in 'pending' status to start, got: {experiment['status']}"
        )

    scenario_type = experiment["scenario_type"]
    blast_radius = experiment["blast_radius"]
    duration_seconds = experiment["duration_seconds"]

    try:
        # Route to appropriate chaos implementation
        if scenario_type == "dynamodb_throttle":
            # AWS FIS integration (Phase 2)
            fis_experiment_id = start_fis_experiment(
                experiment_id, blast_radius, duration_seconds
            )

            # Update experiment with FIS experiment ID
            results = {
                "fis_experiment_id": fis_experiment_id,
                "started_at": datetime.utcnow().isoformat() + "Z",
            }
            update_experiment_status(experiment_id, "running", results)

        elif scenario_type == "newsapi_failure":
            # Phase 3: Lambda environment variable injection
            raise ChaosError("newsapi_failure scenario not yet implemented (Phase 3)")

        elif scenario_type == "lambda_cold_start":
            # Phase 4: Lambda delay injection
            raise ChaosError("lambda_cold_start scenario not yet implemented (Phase 4)")

        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

        # Return updated experiment
        return get_experiment(experiment_id) or experiment

    except Exception as e:
        # Mark experiment as failed
        update_experiment_status(
            experiment_id,
            "failed",
            {"error": str(e), "failed_at": datetime.utcnow().isoformat() + "Z"},
        )
        raise


def stop_experiment(experiment_id: str) -> dict[str, Any]:
    """
    Stop a running chaos experiment.

    Args:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment dict

    Raises:
        ChaosError: If experiment fails to stop
    """
    check_environment_allowed()

    # Get experiment details
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise ChaosError(f"Experiment not found: {experiment_id}")

    if experiment["status"] != "running":
        raise ChaosError(
            f"Experiment must be in 'running' status to stop, got: {experiment['status']}"
        )

    scenario_type = experiment["scenario_type"]

    try:
        # Route to appropriate stop implementation
        if scenario_type == "dynamodb_throttle":
            # AWS FIS integration (Phase 2)
            fis_experiment_id = experiment.get("results", {}).get("fis_experiment_id")
            if not fis_experiment_id:
                raise ChaosError("FIS experiment ID not found in experiment results")

            stop_fis_experiment(fis_experiment_id)

            # Update experiment status
            results = experiment.get("results", {})
            results["stopped_at"] = datetime.utcnow().isoformat() + "Z"
            update_experiment_status(experiment_id, "stopped", results)

        elif scenario_type == "newsapi_failure":
            # Phase 3: Revert Lambda environment variable
            raise ChaosError("newsapi_failure scenario not yet implemented (Phase 3)")

        elif scenario_type == "lambda_cold_start":
            # Phase 4: Stop Lambda delay injection
            raise ChaosError("lambda_cold_start scenario not yet implemented (Phase 4)")

        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

        # Return updated experiment
        return get_experiment(experiment_id) or experiment

    except Exception as e:
        # Mark experiment as failed
        update_experiment_status(
            experiment_id,
            "failed",
            {"error": str(e), "failed_at": datetime.utcnow().isoformat() + "Z"},
        )
        raise
