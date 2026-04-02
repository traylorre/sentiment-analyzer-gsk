"""
Chaos Auto-Restore Lambda Handler
==================================

SNS-triggered Lambda that automatically restores chaos-injected configurations
when the critical composite CloudWatch alarm fires.

This is the automated andon cord. When chaos injection causes error rates to
exceed alarm thresholds, this Lambda:
1. Reads all SSM snapshots under /chaos/{env}/snapshot/
2. Restores each Lambda's original configuration
3. Detaches any deny-write IAM policies
4. Re-enables any disabled EventBridge rules
5. Sets the kill switch to "disarmed"

Safety:
    - Idempotent: safe to invoke multiple times
    - Fail-safe: continues restoring remaining scenarios on individual failures
    - Minimal dependencies: only boto3 (no heavy libraries)
    - Leaves kill switch as "triggered" on partial failure for manual investigation
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENVIRONMENT = os.environ["ENVIRONMENT"]
AWS_REGION = os.environ.get("CLOUD_REGION") or os.environ.get("AWS_REGION", "us-east-1")

# Lazy-loaded clients
_ssm_client = None
_lambda_client = None
_iam_client = None
_events_client = None
_cloudwatch_client = None


def _get_ssm():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm", region_name=AWS_REGION)
    return _ssm_client


def _get_lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    return _lambda_client


def _get_iam():
    global _iam_client
    if _iam_client is None:
        _iam_client = boto3.client("iam", region_name=AWS_REGION)
    return _iam_client


def _get_events():
    global _events_client
    if _events_client is None:
        _events_client = boto3.client("events", region_name=AWS_REGION)
    return _events_client


def _get_cloudwatch():
    global _cloudwatch_client
    if _cloudwatch_client is None:
        _cloudwatch_client = boto3.client("cloudwatch", region_name=AWS_REGION)
    return _cloudwatch_client


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Auto-restore Lambda handler.

    Triggered by SNS when the critical composite CloudWatch alarm fires.

    Args:
        event: SNS event with alarm notification
        context: Lambda context

    Returns:
        Restore results summary
    """
    logger.info(
        "Auto-restore triggered",
        extra={"event_source": "sns_alarm", "environment": ENVIRONMENT},
    )

    # Set kill switch to "triggered" to prevent new injections during restore
    _set_kill_switch("triggered")

    # List all active snapshots
    snapshots = _list_snapshots()
    if not snapshots:
        logger.info("No active chaos snapshots found -- nothing to restore")
        _set_kill_switch("disarmed")
        return {
            "statusCode": 200,
            "body": {"restored": 0, "message": "No active chaos"},
        }

    results = []
    errors = []

    for snapshot in snapshots:
        scenario = _extract_scenario_name(snapshot["Name"])
        try:
            snapshot_data = json.loads(snapshot["Value"])
            _restore_scenario(scenario, snapshot_data)
            _delete_snapshot(snapshot["Name"])
            results.append({"scenario": scenario, "status": "restored"})
            logger.info("Restored scenario", extra={"scenario": scenario})
        except Exception as e:
            errors.append({"scenario": scenario, "error": str(e)})
            logger.error(
                "Failed to restore scenario",
                extra={"scenario": scenario, "error": str(e)},
            )

    # Emit metric
    _emit_restore_metric(len(results))

    # Set kill switch based on results
    if errors:
        # Leave as "triggered" for manual investigation
        logger.warning(
            "Partial restore -- kill switch remains 'triggered'",
            extra={"restored": len(results), "errors": len(errors)},
        )
    else:
        _set_kill_switch("disarmed")
        logger.info(
            "Full restore complete -- kill switch set to 'disarmed'",
            extra={"restored": len(results)},
        )

    return {
        "statusCode": 200,
        "body": {
            "restored": len(results),
            "errors": len(errors),
            "results": results,
            "error_details": errors,
        },
    }


def _set_kill_switch(value: str) -> None:
    """Set the chaos kill switch SSM parameter."""
    try:
        _get_ssm().put_parameter(
            Name=f"/chaos/{ENVIRONMENT}/kill-switch",
            Value=value,
            Type="String",
            Overwrite=True,
        )
    except ClientError as e:
        logger.error("Failed to set kill switch", extra={"error": str(e)})


def _list_snapshots() -> list[dict[str, Any]]:
    """List all SSM snapshot parameters for the current environment."""
    try:
        response = _get_ssm().get_parameters_by_path(
            Path=f"/chaos/{ENVIRONMENT}/snapshot/",
            Recursive=False,
        )
        return response.get("Parameters", [])
    except ClientError as e:
        logger.error("Failed to list snapshots", extra={"error": str(e)})
        return []


def _extract_scenario_name(param_name: str) -> str:
    """Extract scenario name from SSM parameter path."""
    # /chaos/{env}/snapshot/{scenario} -> scenario
    parts = param_name.split("/")
    return parts[-1] if parts else "unknown"


def _delete_snapshot(param_name: str) -> None:
    """Delete an SSM snapshot parameter."""
    try:
        _get_ssm().delete_parameter(Name=param_name)
    except ClientError:
        pass  # Best effort


def _restore_scenario(scenario: str, snapshot: dict[str, Any]) -> None:
    """Restore a single chaos scenario from its snapshot."""
    if scenario == "ingestion-failure":
        _restore_concurrency(snapshot)
    elif scenario == "dynamodb-throttle":
        _restore_dynamodb_access()
    elif scenario == "cold-start":
        _restore_memory(snapshot)
    elif scenario == "trigger-failure":
        _restore_eventbridge_rule()
    elif scenario == "api-timeout":
        _restore_timeout(snapshot)
    else:
        logger.warning("Unknown scenario", extra={"scenario": scenario})


def _restore_concurrency(snapshot: dict[str, Any]) -> None:
    """Restore Lambda concurrency from snapshot."""
    func_name = snapshot["FunctionName"]
    concurrency = snapshot.get("ReservedConcurrency", "NONE")

    if concurrency == "NONE":
        _get_lambda().delete_function_concurrency(FunctionName=func_name)
    else:
        _get_lambda().put_function_concurrency(
            FunctionName=func_name,
            ReservedConcurrentExecutions=int(concurrency),
        )


def _restore_dynamodb_access() -> None:
    """Detach deny-write policy from Lambda roles."""
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
            _get_iam().detach_role_policy(RoleName=role, PolicyArn=policy_arn)
        except ClientError:
            pass  # Policy may not be attached


def _restore_memory(snapshot: dict[str, Any]) -> None:
    """Restore Lambda memory from snapshot."""
    _get_lambda().update_function_configuration(
        FunctionName=snapshot["FunctionName"],
        MemorySize=int(snapshot["MemorySize"]),
    )


def _restore_eventbridge_rule() -> None:
    """Re-enable the ingestion schedule EventBridge rule."""
    rule_name = f"{ENVIRONMENT}-sentiment-ingestion-schedule"
    _get_events().enable_rule(Name=rule_name)


def _restore_timeout(snapshot: dict[str, Any]) -> None:
    """Restore Lambda timeout from snapshot."""
    _get_lambda().update_function_configuration(
        FunctionName=snapshot["FunctionName"],
        Timeout=int(snapshot["Timeout"]),
    )


def _emit_restore_metric(count: int) -> None:
    """Emit ChaosAutoRestore CloudWatch metric."""
    try:
        _get_cloudwatch().put_metric_data(
            Namespace="SentimentAnalyzer",
            MetricData=[
                {
                    "MetricName": "ChaosAutoRestore",
                    "Value": count,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Environment", "Value": ENVIRONMENT},
                    ],
                }
            ],
        )
    except ClientError as e:
        logger.warning("Failed to emit metric", extra={"error": str(e)})
