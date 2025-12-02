"""
Metrics Lambda Handler
======================

EventBridge-triggered Lambda that monitors for stuck items and emits
CloudWatch metrics for operational alerting.

For On-Call Engineers:
    This Lambda runs every 1 minute via EventBridge scheduler.

    Purpose:
    - Detects items stuck in 'pending' status for > 5 minutes
    - Emits CloudWatch metric 'StuckItems' to SentimentAnalyzer namespace
    - Enables alarming on processing pipeline health

    Common issues:
    - High StuckItems count: Check Analysis Lambda logs for errors
    - Zero metrics: Verify EventBridge schedule is enabled

    Quick commands:
    # Check recent invocations
    aws logs tail /aws/lambda/${environment}-sentiment-metrics --since 1h

    # Check stuck items metric
    aws cloudwatch get-metric-statistics \
      --namespace SentimentAnalyzer \
      --metric-name StuckItems \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 300 --statistics Maximum

    See ON_CALL_SOP.md for detailed runbooks.

For Developers:
    Handler workflow:
    1. Query by_status GSI for pending items older than 5 minutes
    2. Count stuck items
    3. Emit CloudWatch metric

Security Notes:
    - Read-only access to by_status GSI only
    - No external API calls
    - Minimal IAM permissions (Query + PutMetricData)
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from src.lib.metrics import emit_metric, log_structured

# Configuration
STUCK_THRESHOLD_MINUTES = 5
METRIC_NAMESPACE = "SentimentAnalyzer"
METRIC_NAME = "StuckItems"


def get_stuck_items_count(
    table_name: str, threshold_minutes: int = STUCK_THRESHOLD_MINUTES
) -> int:
    """
    Query by_status GSI for pending items older than threshold.

    Args:
        table_name: DynamoDB table name
        threshold_minutes: Minutes after which pending items are considered stuck

    Returns:
        Count of stuck items
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    # Calculate threshold timestamp
    threshold_time = datetime.now(UTC) - timedelta(minutes=threshold_minutes)
    threshold_iso = threshold_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    log_structured(
        "info",
        "Querying for stuck items",
        threshold_time=threshold_iso,
        threshold_minutes=threshold_minutes,
    )

    # Query by_status GSI for pending items older than threshold
    response = table.query(
        IndexName="by_status",
        KeyConditionExpression=Key("status").eq("pending")
        & Key("timestamp").lt(threshold_iso),
        Select="COUNT",  # Only get count, not items (cost optimization)
        Limit=1000,  # Cap query size
    )

    stuck_count = response.get("Count", 0)

    log_structured(
        "info",
        "Stuck items query complete",
        stuck_count=stuck_count,
        scanned_count=response.get("ScannedCount", 0),
    )

    return stuck_count


def emit_stuck_items_metric(count: int, environment: str) -> None:
    """
    Emit StuckItems metric to CloudWatch.

    Args:
        count: Number of stuck items
        environment: Environment name (dev, preprod, prod)
    """
    emit_metric(
        metric_name=METRIC_NAME,
        value=count,
        unit="Count",
        dimensions={"Environment": environment},
        namespace=METRIC_NAMESPACE,
    )

    log_structured(
        "info",
        "Emitted StuckItems metric",
        metric_name=METRIC_NAME,
        value=count,
        environment=environment,
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for metrics collection.

    Triggered by EventBridge every 1 minute.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Response with stuck items count
    """
    start_time = datetime.now(UTC)

    log_structured(
        "info",
        "Metrics Lambda invoked",
        event_source=event.get("source", "unknown"),
        request_id=getattr(context, "aws_request_id", "local"),
    )

    # Get configuration from environment
    table_name = os.environ.get("DYNAMODB_TABLE")
    environment = os.environ.get("ENVIRONMENT", "dev")

    if not table_name:
        log_structured("error", "DYNAMODB_TABLE environment variable not set")
        return {
            "statusCode": 500,
            "body": "Configuration error: DYNAMODB_TABLE not set",
        }

    try:
        # Query for stuck items
        stuck_count = get_stuck_items_count(table_name)

        # Emit metric
        emit_stuck_items_metric(stuck_count, environment)

        # Calculate duration
        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        log_structured(
            "info",
            "Metrics collection complete",
            stuck_count=stuck_count,
            duration_ms=round(duration_ms, 2),
        )

        return {
            "statusCode": 200,
            "body": {
                "stuck_items": stuck_count,
                "threshold_minutes": STUCK_THRESHOLD_MINUTES,
                "environment": environment,
                "duration_ms": round(duration_ms, 2),
            },
        }

    except Exception as e:
        log_structured(
            "error",
            "Metrics collection failed",
            error=str(e),
            error_type=type(e).__name__,
        )

        # Still try to emit a metric indicating failure
        try:
            emit_metric(
                metric_name="MetricsLambdaErrors",
                value=1,
                unit="Count",
                dimensions={"Environment": environment},
                namespace=METRIC_NAMESPACE,
            )
        except Exception as metric_err:
            # Log but don't fail - primary error already handled above
            log_structured(
                "warning", "Failed to emit error metric", error=str(metric_err)
            )

        return {
            "statusCode": 500,
            "body": f"Error: {e!s}",
        }
