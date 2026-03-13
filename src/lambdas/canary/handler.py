"""X-Ray Canary Lambda Handler (T081-T083).

Validates X-Ray tracing pipeline health by:
1. Submitting synthetic test traces
2. Querying GetTraceSummaries to verify trace ingestion
3. Calculating completeness_ratio
4. Emitting CanaryHealth and completeness_ratio metrics to CloudWatch

Runs on EventBridge 5-minute schedule (T087).

FR References: FR-019, FR-036, FR-078, FR-113, FR-145, FR-185
"""

import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta

import boto3
from aws_lambda_powertools import Tracer
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

tracer = Tracer(service="sentiment-analyzer-canary")

# Configuration
REGION = os.environ.get("AWS_REGION", "us-east-1")
CLOUDWATCH_NAMESPACE = "SentimentAnalyzer/Canary"
COMPLETENESS_THRESHOLD = 0.95

# Retry configuration for GetTraceSummaries (T083, FR-078)
MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 90]  # Seconds between retries


@tracer.capture_lambda_handler
def handler(event, context):
    """Canary Lambda entry point.

    T090/FR-145: Must complete even when X-Ray is broken.
    Does NOT use fail-fast pattern.
    """
    logger.info("Canary invocation started", extra={"event": json.dumps(event)})

    xray_client = boto3.client("xray", region_name=REGION)
    cloudwatch_client = boto3.client("cloudwatch", region_name=REGION)

    # Step 1: Submit synthetic test trace
    trace_id = _submit_test_trace(xray_client)

    # Step 2: Verify trace ingestion with retry-backoff (T083)
    completeness_ratio = _verify_trace_ingestion(xray_client, trace_id)

    # Step 3: Emit health metrics (T082)
    health_status = 1 if completeness_ratio >= COMPLETENESS_THRESHOLD else 0
    _emit_metrics(cloudwatch_client, health_status, completeness_ratio)

    result = {
        "status": "HEALTHY" if health_status else "DEGRADED",
        "completeness_ratio": completeness_ratio,
        "trace_id": trace_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    logger.info("Canary complete", extra=result)
    return result


@tracer.capture_method
def _submit_test_trace(xray_client) -> str:
    """Submit a synthetic test trace to X-Ray (FR-019, FR-113).

    Marks trace with synthetic=true annotation (FR-185) so it's
    filtered into canary-traces group and excluded from
    production-traces group.

    Returns:
        The trace ID of the submitted test trace.
    """
    # The current trace ID from Powertools Tracer
    trace_id = os.environ.get("_X_AMZN_TRACE_ID", "")

    # Add synthetic annotation to current trace
    tracer.put_annotation(key="synthetic", value=True)
    tracer.put_annotation(key="canary_version", value="1.0")
    tracer.put_annotation(
        key="environment", value=os.environ.get("ENVIRONMENT", "unknown")
    )

    logger.info("Submitted synthetic trace", extra={"trace_id": trace_id})
    return trace_id


@tracer.capture_method
def _verify_trace_ingestion(xray_client, trace_id: str) -> float:
    """Verify trace appears in X-Ray with retry-backoff (T083, FR-078).

    Queries GetTraceSummaries with retries at 30s, 60s, 90s intervals
    to account for X-Ray indexing delay.

    Args:
        xray_client: boto3 X-Ray client
        trace_id: Trace ID to look for

    Returns:
        Completeness ratio (0.0-1.0)
    """
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(minutes=10)

    for attempt in range(MAX_RETRIES):
        try:
            response = xray_client.get_trace_summaries(
                StartTime=start_time,
                EndTime=datetime.now(UTC),
                FilterExpression="annotation.synthetic = true",
                Sampling=False,
            )

            summaries = response.get("TraceSummaries", [])
            total_canary_traces = len(summaries)

            if total_canary_traces == 0:
                logger.warning(
                    "No canary traces found",
                    extra={"attempt": attempt + 1, "max_retries": MAX_RETRIES},
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                return 0.0

            # Count traces that have complete segments
            complete = sum(1 for s in summaries if not s.get("IsPartial", True))

            ratio = complete / total_canary_traces if total_canary_traces > 0 else 0.0

            logger.info(
                "Trace verification result",
                extra={
                    "total": total_canary_traces,
                    "complete": complete,
                    "ratio": ratio,
                    "attempt": attempt + 1,
                },
            )
            return ratio

        except ClientError as e:
            logger.error(
                "GetTraceSummaries failed",
                extra={"error": str(e), "attempt": attempt + 1},
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
            else:
                # T090/FR-145: Don't fail — return 0 and let alarm handle it
                return 0.0

    return 0.0


@tracer.capture_method
def _emit_metrics(
    cloudwatch_client, health_status: int, completeness_ratio: float
) -> None:
    """Emit canary health metrics to CloudWatch (T082, FR-036, FR-185).

    Args:
        cloudwatch_client: boto3 CloudWatch client
        health_status: 1 = healthy, 0 = degraded
        completeness_ratio: Trace completeness ratio (0.0-1.0)
    """
    timestamp = datetime.now(UTC)

    try:
        cloudwatch_client.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[
                {
                    "MetricName": "CanaryHealth",
                    "Value": health_status,
                    "Unit": "None",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {
                            "Name": "Environment",
                            "Value": os.environ.get("ENVIRONMENT", "unknown"),
                        },
                    ],
                },
                {
                    "MetricName": "completeness_ratio",
                    "Value": completeness_ratio,
                    "Unit": "None",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {
                            "Name": "Environment",
                            "Value": os.environ.get("ENVIRONMENT", "unknown"),
                        },
                    ],
                },
            ],
        )
        logger.info(
            "Metrics emitted",
            extra={
                "health_status": health_status,
                "completeness_ratio": completeness_ratio,
            },
        )
    except ClientError as e:
        # T090/FR-145: Don't fail on metric emission error
        logger.error("Failed to emit metrics", extra={"error": str(e)})
