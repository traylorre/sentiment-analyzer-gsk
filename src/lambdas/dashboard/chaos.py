"""
Chaos Testing Module -- External Actor Architecture
=====================================================

Manages chaos experiments by degrading infrastructure through external AWS API
calls. Lambda handlers contain zero chaos awareness; all fault injection is
performed by modifying Lambda configuration, IAM policies, or EventBridge rules.

Feature 1237: Refactored from embedded DynamoDB-flag approach to external actor.

Experiment Lifecycle:
    1. Create experiment (POST /chaos/experiments) -- audit log entry
    2. Start experiment (POST /chaos/experiments/{id}/start) -- external API calls
    3. Monitor experiment (GET /chaos/experiments/{id})
    4. Stop experiment (POST /chaos/experiments/{id}/stop) -- restore from SSM snapshot
    5. View history (GET /chaos/experiments)

Supported Scenarios:
    - ingestion_failure: Set Lambda concurrency to 0 (throttles all invocations)
    - dynamodb_throttle: Attach deny-write IAM policy to Lambda execution roles
    - lambda_cold_start: Reduce Lambda memory to 128MB (force cold starts)
    - trigger_failure: Disable EventBridge ingestion schedule rule
    - api_timeout: Reduce Lambda timeout to 1s (or custom value)

Safety Mechanisms:
    - Environment gating (preprod/dev/test only)
    - SSM kill switch prevents injection when triggered
    - SSM snapshots preserve pre-chaos config for restoration
    - Time limits (5-300 seconds)
"""

import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

logger = logging.getLogger(__name__)

# Configuration
CHAOS_TABLE = os.environ.get("CHAOS_EXPERIMENTS_TABLE", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Safety: Only allow chaos testing in preprod/dev/test
ALLOWED_ENVIRONMENTS = ["preprod", "dev", "test"]

# AWS clients (lazy-loaded to avoid region errors during test imports)
_dynamodb = None
_lambda_client = None
_ssm_client = None
_iam_client = None


def _get_dynamodb():
    """Lazy-load DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_lambda_client():
    """Lazy-load Lambda client."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def _get_ssm_client():
    """Lazy-load SSM client."""
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


def _get_iam_client():
    """Lazy-load IAM client."""
    global _iam_client
    if _iam_client is None:
        _iam_client = boto3.client("iam")
    return _iam_client


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


# ===================================================================
# CRUD Operations (DynamoDB audit log -- unchanged)
# ===================================================================


def create_experiment(
    scenario_type: str,
    blast_radius: int,
    duration_seconds: int,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new chaos experiment.

    Args:
        scenario_type: Type of chaos scenario (dynamodb_throttle|ingestion_failure|lambda_cold_start)
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
    valid_scenarios = [
        "dynamodb_throttle",
        "ingestion_failure",
        "lambda_cold_start",
        "trigger_failure",
        "api_timeout",
    ]
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
    created_at = datetime.now(UTC).isoformat() + "Z"
    ttl_timestamp = int((datetime.now(UTC) + timedelta(days=7)).timestamp())

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
                "experiment_id": sanitize_for_log(experiment_id),
                "scenario_type": sanitize_for_log(scenario_type),
                "blast_radius": sanitize_for_log(str(blast_radius)),
                "duration_seconds": sanitize_for_log(str(duration_seconds)),
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
            ":updated_at": datetime.now(UTC).isoformat() + "Z",
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
# External Chaos Operations (Feature 1237)
# ===================================================================


def _check_kill_switch() -> str:
    """
    Check kill switch state. Returns 'disarmed', 'armed', or 'triggered'.

    FAIL-CLOSED: If SSM is unreachable, raises ChaosError to block injection.
    This prevents chaos operations when we cannot verify safety state.
    """
    ssm = _get_ssm_client()
    try:
        response = ssm.get_parameter(Name=f"/chaos/{ENVIRONMENT}/kill-switch")
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return "disarmed"  # No kill switch parameter = first-time setup, proceed
    except Exception as e:
        # FAIL-CLOSED: if SSM is down, block injection
        raise ChaosError(
            "Cannot verify kill switch (SSM unavailable) — blocking injection "
            f"for safety: {e}"
        ) from e


def _enforce_kill_switch():
    """Check SSM kill switch. Raises ChaosError if triggered or unverifiable."""
    kill_switch = _check_kill_switch()
    if kill_switch == "triggered":
        raise ChaosError(
            "Kill switch is triggered — all chaos operations blocked. "
            "Resolve before starting new experiments."
        )


def _check_gate() -> str:
    """Check chaos gate state from SSM.

    Returns:
        "armed" - gate open, proceed with real infrastructure changes
        "disarmed" - gate closed, record signals but skip infrastructure changes (dry-run)

    Raises:
        ChaosError: if gate is "triggered" (emergency stop) or SSM unreachable (fail-closed)
    """
    ssm = _get_ssm_client()
    try:
        param = ssm.get_parameter(Name=f"/chaos/{ENVIRONMENT}/kill-switch")
        value = param["Parameter"]["Value"]
        if value == "triggered":
            raise ChaosError("Kill switch triggered — all chaos operations blocked")
        return value  # "armed" or "disarmed"
    except ChaosError:
        raise
    except ssm.exceptions.ParameterNotFound:
        return "disarmed"  # Default safe state
    except Exception as e:
        raise ChaosError(
            f"Cannot verify chaos gate (SSM unavailable) — blocking for safety: {e}"
        ) from e


def _capture_baseline(env: str) -> dict[str, Any]:
    """Capture current system health metrics as baseline.

    Checks key dependencies to detect concurrent issues.
    Returns dict with health status of each dependency.
    """
    baseline: dict[str, Any] = {
        "captured_at": datetime.now(UTC).isoformat() + "Z",
        "dependencies": {},
    }

    # Check DynamoDB health
    try:
        dynamodb = boto3.client("dynamodb")
        dynamodb.describe_table(TableName=f"{env}-users")
        baseline["dependencies"]["dynamodb"] = {
            "status": "healthy",
            "latency_ms": 0,
        }
    except Exception as e:
        baseline["dependencies"]["dynamodb"] = {
            "status": "degraded",
            "error": str(e),
        }

    # Check SSM health
    try:
        ssm = _get_ssm_client()
        ssm.get_parameter(Name=f"/chaos/{env}/kill-switch")
        baseline["dependencies"]["ssm"] = {"status": "healthy"}
    except Exception as e:
        baseline["dependencies"]["ssm"] = {
            "status": "degraded",
            "error": str(e),
        }

    # Check CloudWatch health (can we read metrics?)
    try:
        cw = boto3.client("cloudwatch")
        cw.describe_alarms(AlarmNames=[f"{env}-critical-composite"], MaxRecords=1)
        baseline["dependencies"]["cloudwatch"] = {"status": "healthy"}
    except Exception as e:
        baseline["dependencies"]["cloudwatch"] = {
            "status": "degraded",
            "error": str(e),
        }

    # Check Lambda health (can we read configs?)
    try:
        lam = _get_lambda_client()
        lam.get_function(FunctionName=f"{env}-sentiment-ingestion")
        baseline["dependencies"]["lambda"] = {"status": "healthy"}
    except Exception as e:
        baseline["dependencies"]["lambda"] = {
            "status": "degraded",
            "error": str(e),
        }

    # Flag if ANY dependency is degraded
    degraded = [
        k for k, v in baseline["dependencies"].items() if v["status"] != "healthy"
    ]
    baseline["all_healthy"] = len(degraded) == 0
    baseline["degraded_services"] = degraded

    if degraded:
        baseline["warning"] = (
            f"CONCURRENT ISSUE DETECTED: {', '.join(degraded)} degraded BEFORE "
            "chaos injection. Results may be unreliable — cannot distinguish "
            "chaos-induced failures from pre-existing ones."
        )

    return baseline


def _capture_post_chaos_health(env: str, baseline: dict[str, Any]) -> dict[str, Any]:
    """Capture post-chaos health and compare with baseline.

    Detects:
    - Recovery: things that were degraded and recovered
    - New issues: things healthy at baseline but degraded now
    - Persistent: things degraded both before and after (concurrent issue, not chaos-related)
    """
    current = _capture_baseline(env)
    comparison: dict[str, Any] = {
        "captured_at": current["captured_at"],
        "recovered": [],
        "new_issues": [],
        "persistent_issues": [],
        "all_healthy": current["all_healthy"],
    }

    baseline_degraded = set(baseline.get("degraded_services", []))
    current_degraded = set(current.get("degraded_services", []))

    comparison["recovered"] = list(baseline_degraded - current_degraded)
    comparison["new_issues"] = list(current_degraded - baseline_degraded)
    comparison["persistent_issues"] = list(baseline_degraded & current_degraded)

    if comparison["persistent_issues"]:
        comparison["warning"] = (
            f"PERSISTENT ISSUES: {', '.join(comparison['persistent_issues'])} were degraded "
            "before AND after chaos. These are NOT chaos-related — investigate independently."
        )

    if comparison["new_issues"]:
        comparison["warning"] = (
            f"NEW ISSUES POST-CHAOS: {', '.join(comparison['new_issues'])} became degraded "
            "during chaos. May be chaos-induced OR coincidental outage."
        )

    return comparison


def _set_kill_switch(value: str) -> None:
    """Set kill switch to given value."""
    try:
        _get_ssm_client().put_parameter(
            Name=f"/chaos/{ENVIRONMENT}/kill-switch",
            Value=value,
            Type="String",
            Overwrite=True,
        )
    except ClientError as e:
        logger.error("Failed to set kill switch", extra={"error": str(e)})


def _snapshot_to_ssm(scenario_type: str, function_name: str) -> None:
    """Save current Lambda config to SSM before degrading."""
    try:
        config = _get_lambda_client().get_function_configuration(
            FunctionName=function_name
        )

        # Get reserved concurrency
        try:
            conc = _get_lambda_client().get_function_concurrency(
                FunctionName=function_name
            )
            reserved = conc.get("ReservedConcurrentExecutions", "NONE")
        except ClientError:
            reserved = "NONE"

        snapshot = {
            "FunctionName": config["FunctionName"],
            "FunctionArn": config["FunctionArn"],
            "MemorySize": config["MemorySize"],
            "Timeout": config["Timeout"],
            "ReservedConcurrency": str(reserved),
            "SnapshotTimestamp": datetime.now(UTC).isoformat() + "Z",
            "Scenario": scenario_type,
        }

        # Map scenario_type to SSM-safe key
        ssm_key = scenario_type.replace("_", "-")
        _get_ssm_client().put_parameter(
            Name=f"/chaos/{ENVIRONMENT}/snapshot/{ssm_key}",
            Value=json.dumps(snapshot),
            Type="String",
            Overwrite=True,
        )

        logger.info(
            "Config snapshot saved to SSM",
            extra={"scenario": scenario_type, "function": function_name},
        )

    except ClientError as e:
        raise ChaosError(f"Failed to snapshot config: {e}") from e


def _restore_from_ssm(scenario_type: str) -> dict[str, Any]:
    """Read SSM snapshot and restore config."""
    ssm_key = scenario_type.replace("_", "-")
    param_name = f"/chaos/{ENVIRONMENT}/snapshot/{ssm_key}"

    try:
        response = _get_ssm_client().get_parameter(Name=param_name)
        snapshot = json.loads(response["Parameter"]["Value"])
    except ClientError as e:
        raise ChaosError(f"Failed to read snapshot for {scenario_type}: {e}") from e

    # Restore based on scenario
    if scenario_type == "ingestion_failure":
        _restore_concurrency(snapshot)
    elif scenario_type == "dynamodb_throttle":
        _restore_dynamodb_access()
    elif scenario_type == "lambda_cold_start":
        _restore_memory(snapshot)
    elif scenario_type == "trigger_failure":
        _restore_eventbridge_rule()
    elif scenario_type == "api_timeout":
        _restore_timeout(snapshot)

    # Delete snapshot after successful restore
    try:
        _get_ssm_client().delete_parameter(Name=param_name)
    except ClientError:
        pass

    return snapshot


def _restore_concurrency(snapshot: dict[str, Any]) -> None:
    """Restore Lambda concurrency from snapshot."""
    func_name = snapshot["FunctionName"]
    concurrency = snapshot.get("ReservedConcurrency", "NONE")

    if concurrency == "NONE":
        try:
            _get_lambda_client().delete_function_concurrency(FunctionName=func_name)
        except ClientError:
            pass
    else:
        _get_lambda_client().put_function_concurrency(
            FunctionName=func_name,
            ReservedConcurrentExecutions=int(concurrency),
        )


def _restore_dynamodb_access() -> None:
    """Detach deny-write policy from Lambda execution roles."""
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    policy_arn = (
        f"arn:aws:iam::{account_id}:policy/{ENVIRONMENT}-chaos-deny-dynamodb-write"
    )

    roles = [
        f"{ENVIRONMENT}-ingestion-lambda-role",
        f"{ENVIRONMENT}-analysis-lambda-role",
    ]

    for role in roles:
        try:
            _get_iam_client().detach_role_policy(RoleName=role, PolicyArn=policy_arn)
        except ClientError:
            pass  # Policy may not be attached


def _restore_memory(snapshot: dict[str, Any]) -> None:
    """Restore Lambda memory from snapshot."""
    _get_lambda_client().update_function_configuration(
        FunctionName=snapshot["FunctionName"],
        MemorySize=int(snapshot["MemorySize"]),
    )


def _restore_eventbridge_rule() -> None:
    """Re-enable EventBridge ingestion schedule rule."""
    rule_name = f"{ENVIRONMENT}-sentiment-ingestion-schedule"
    events_client = boto3.client("events")
    events_client.enable_rule(Name=rule_name)


def _restore_timeout(snapshot: dict[str, Any]) -> None:
    """Restore Lambda timeout from snapshot."""
    _get_lambda_client().update_function_configuration(
        FunctionName=snapshot["FunctionName"],
        Timeout=int(snapshot["Timeout"]),
    )


# ===================================================================
# Start/Stop (External Actor Implementation)
# ===================================================================


def start_experiment(experiment_id: str) -> dict[str, Any]:
    """
    Start a chaos experiment using external AWS API calls.

    Instead of setting DynamoDB flags that Lambdas check, this directly
    degrades infrastructure: sets concurrency to 0, attaches deny policies,
    or reduces memory. Lambda handlers are completely unaware.

    Gate pattern (Feature 1238):
        - "armed": proceed with real infrastructure changes
        - "disarmed": record signals but skip infrastructure changes (dry-run)
        - "triggered": raise ChaosError (emergency stop)

    Args:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment dict

    Raises:
        ChaosError: If experiment fails to start
    """
    check_environment_allowed()

    # Check gate state (fail-closed: blocks if SSM unreachable or triggered)
    gate = _check_gate()
    dry_run = gate != "armed"

    # Get experiment details
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise ChaosError(f"Experiment not found: {experiment_id}")

    if experiment["status"] != "pending":
        raise ChaosError(
            f"Experiment must be in 'pending' status to start, "
            f"got: {experiment['status']}"
        )

    scenario_type = experiment["scenario_type"]

    try:
        # Capture baseline health BEFORE any chaos injection
        baseline = _capture_baseline(ENVIRONMENT)
        if baseline.get("degraded_services"):
            logger.warning(
                "Pre-chaos dependency degradation detected",
                extra={"degraded": baseline["degraded_services"]},
            )

        if scenario_type == "ingestion_failure":
            # Ingestion Lambda is EventBridge-triggered (scheduled), NOT Function URL.
            # Setting concurrency=0 works correctly for EventBridge-triggered Lambdas:
            # EventBridge will receive throttle errors and route to DLQ.
            func_name = f"{ENVIRONMENT}-sentiment-ingestion"
            if not dry_run:
                _snapshot_to_ssm(scenario_type, func_name)
                _get_lambda_client().put_function_concurrency(
                    FunctionName=func_name,
                    ReservedConcurrentExecutions=0,
                )
            results = {
                "started_at": datetime.now(UTC).isoformat() + "Z",
                "injection_method": "concurrency_zero",
                "function_name": func_name,
                "dry_run": dry_run,
                "gate_state": gate,
                "baseline": baseline,
            }

        elif scenario_type == "dynamodb_throttle":
            func_name = f"{ENVIRONMENT}-sentiment-ingestion"
            account_id = boto3.client("sts").get_caller_identity()["Account"]
            policy_arn = (
                f"arn:aws:iam::{account_id}:policy/"
                f"{ENVIRONMENT}-chaos-deny-dynamodb-write"
            )
            roles = [
                f"{ENVIRONMENT}-ingestion-lambda-role",
                f"{ENVIRONMENT}-analysis-lambda-role",
            ]
            if not dry_run:
                _snapshot_to_ssm(scenario_type, func_name)
                for role in roles:
                    _get_iam_client().attach_role_policy(
                        RoleName=role, PolicyArn=policy_arn
                    )
                # IAM policy propagation takes up to 60 seconds. Sleep briefly to
                # increase probability of consistent behavior on first invocation.
                time.sleep(5)
            results = {
                "started_at": datetime.now(UTC).isoformat() + "Z",
                "injection_method": "attach_deny_policy",
                "policy": policy_arn,
                "roles": roles,
                "dry_run": dry_run,
                "gate_state": gate,
                "baseline": baseline,
            }

        elif scenario_type == "lambda_cold_start":
            func_name = f"{ENVIRONMENT}-sentiment-analysis"
            if not dry_run:
                _snapshot_to_ssm(scenario_type, func_name)
                _get_lambda_client().update_function_configuration(
                    FunctionName=func_name,
                    MemorySize=128,
                )
            results = {
                "started_at": datetime.now(UTC).isoformat() + "Z",
                "injection_method": "set_memory_128",
                "function_name": func_name,
                "dry_run": dry_run,
                "gate_state": gate,
                "baseline": baseline,
            }

        elif scenario_type == "trigger_failure":
            rule_name = f"{ENVIRONMENT}-sentiment-ingestion-schedule"
            func_name = f"{ENVIRONMENT}-sentiment-ingestion"
            if not dry_run:
                # Snapshot current state and disable rule
                events_client = boto3.client("events")
                events_client.describe_rule(Name=rule_name)  # Verify rule exists
                events_client.disable_rule(Name=rule_name)
                _snapshot_to_ssm(scenario_type, func_name)
            results = {
                "started_at": datetime.now(UTC).isoformat() + "Z",
                "injection_method": "eventbridge_disable",
                "rule_name": rule_name,
                "dry_run": dry_run,
                "gate_state": gate,
                "baseline": baseline,
            }

        elif scenario_type == "api_timeout":
            func_name = (
                f"{ENVIRONMENT}-sentiment-"
                f"{experiment.get('parameters', {}).get('target', 'ingestion')}"
            )
            timeout = int(experiment.get("parameters", {}).get("timeout", 1))
            if not dry_run:
                lambda_client = _get_lambda_client()
                _snapshot_to_ssm(scenario_type, func_name)
                lambda_client.update_function_configuration(
                    FunctionName=func_name, Timeout=timeout
                )
            results = {
                "started_at": datetime.now(UTC).isoformat() + "Z",
                "injection_method": "timeout_reduction",
                "function_name": func_name,
                "timeout": timeout,
                "dry_run": dry_run,
                "gate_state": gate,
                "baseline": baseline,
            }

        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

        # Set kill switch to armed (only if not dry-run)
        if not dry_run:
            _set_kill_switch("armed")

        # Update audit log
        update_experiment_status(experiment_id, "running", results)

        # Return updated experiment
        return get_experiment(experiment_id) or experiment

    except Exception as e:
        # Mark experiment as failed
        update_experiment_status(
            experiment_id,
            "failed",
            {"error": str(e), "failed_at": datetime.now(UTC).isoformat() + "Z"},
        )
        raise


def stop_experiment(experiment_id: str) -> dict[str, Any]:
    """
    Stop a running chaos experiment by restoring from SSM snapshot.

    Reads the pre-chaos configuration from SSM and restores the original
    Lambda configuration, IAM policies, or EventBridge rules.

    Post-chaos health comparison (Feature 1238):
        Captures current health and compares with baseline to detect
        recovery, new issues, and persistent (pre-existing) problems.

    Args:
        experiment_id: Experiment UUID

    Returns:
        Updated experiment dict

    Raises:
        ChaosError: If experiment fails to stop
    """
    check_environment_allowed()

    # Re-check kill switch at stop time (fail-closed: blocks if SSM unreachable)
    _enforce_kill_switch()

    # Get experiment details
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise ChaosError(f"Experiment not found: {experiment_id}")

    if experiment["status"] != "running":
        raise ChaosError(
            f"Experiment must be in 'running' status to stop, "
            f"got: {experiment['status']}"
        )

    scenario_type = experiment["scenario_type"]
    was_dry_run = experiment.get("results", {}).get("dry_run", False)

    try:
        # Only restore from SSM if this was NOT a dry-run
        snapshot = {}
        if not was_dry_run:
            snapshot = _restore_from_ssm(scenario_type)

        # Set kill switch to disarmed
        _set_kill_switch("disarmed")

        # Update audit log with post-chaos health comparison
        results = experiment.get("results", {})
        results["stopped_at"] = datetime.now(UTC).isoformat() + "Z"
        results["restore_method"] = (
            "ssm_snapshot" if not was_dry_run else "dry_run_no_restore"
        )
        results["restored_config"] = {
            "MemorySize": snapshot.get("MemorySize"),
            "Timeout": snapshot.get("Timeout"),
            "ReservedConcurrency": snapshot.get("ReservedConcurrency"),
        }

        # Capture post-chaos health and compare with baseline
        baseline = results.get("baseline", {})
        results["post_chaos_health"] = _capture_post_chaos_health(ENVIRONMENT, baseline)

        update_experiment_status(experiment_id, "stopped", results)

        # Return updated experiment
        return get_experiment(experiment_id) or experiment

    except Exception as e:
        # Mark experiment as failed
        update_experiment_status(
            experiment_id,
            "failed",
            {"error": str(e), "failed_at": datetime.now(UTC).isoformat() + "Z"},
        )
        raise


def get_experiment_report(experiment_id: str) -> dict[str, Any]:
    """Generate a comprehensive chaos experiment report.

    Returns structured report with:
    - Experiment metadata (scenario, duration, dry_run)
    - Baseline health (pre-chaos)
    - Post-chaos health comparison
    - Verdict (clean / compromised / inconclusive)
    """
    experiment = get_experiment(experiment_id)
    if not experiment:
        raise ChaosError(f"Experiment not found: {experiment_id}")

    results = experiment.get("results", {})
    baseline = results.get("baseline", {})
    post_chaos = results.get("post_chaos_health", {})

    report: dict[str, Any] = {
        "experiment_id": experiment_id,
        "scenario": experiment["scenario_type"],
        "status": experiment["status"],
        "dry_run": results.get("dry_run", False),
        "duration_seconds": experiment.get("duration_seconds", 0),
        "started_at": results.get("started_at"),
        "stopped_at": results.get("stopped_at"),
        "baseline": baseline,
        "post_chaos": post_chaos,
    }

    # Determine verdict
    if baseline.get("degraded_services"):
        report["verdict"] = "COMPROMISED"
        report["verdict_reason"] = (
            f"Pre-existing degradation in {baseline['degraded_services']} — "
            "results unreliable, cannot isolate chaos effects"
        )
    elif post_chaos.get("persistent_issues"):
        report["verdict"] = "COMPROMISED"
        report["verdict_reason"] = (
            f"Persistent issues in {post_chaos['persistent_issues']} — "
            "pre-existing problem, not chaos-related"
        )
    elif results.get("dry_run"):
        report["verdict"] = "DRY_RUN_CLEAN"
        report["verdict_reason"] = (
            "Gate was disarmed — framework signaling verified, no infrastructure changes"
        )
    elif post_chaos.get("all_healthy"):
        report["verdict"] = "CLEAN"
        report["verdict_reason"] = "System recovered to healthy state after chaos"
    elif post_chaos.get("new_issues"):
        report["verdict"] = "RECOVERY_INCOMPLETE"
        report["verdict_reason"] = f"New issues after chaos: {post_chaos['new_issues']}"
    else:
        report["verdict"] = "INCONCLUSIVE"
        report["verdict_reason"] = "Insufficient data for verdict"

    return report
