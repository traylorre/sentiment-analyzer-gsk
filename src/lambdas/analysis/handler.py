"""
Analysis Lambda Handler
=======================

SNS-triggered Lambda that runs sentiment inference and updates DynamoDB.

For On-Call Engineers:
    This Lambda is triggered by SNS messages from the ingestion Lambda.

    Common issues:
    - SC-04: High inference latency (>500ms) - Check memory allocation
    - SC-06: Analysis errors - Check DLQ depth, review CloudWatch logs
    - SC-02: DynamoDB update failures - Verify item exists with status=pending

    Quick commands:
    # Check recent invocations
    aws logs tail /aws/lambda/${environment}-sentiment-analysis --since 1h

    # Check inference latency
    aws cloudwatch get-metric-statistics \
      --namespace SentimentAnalyzer \
      --metric-name InferenceLatencyMs \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 300 --statistics Average

    # Check DLQ depth
    aws sqs get-queue-attributes \
      --queue-url ${dlq_url} \
      --attribute-names ApproximateNumberOfMessages

    See ON_CALL_SOP.md for detailed runbooks.

For Developers:
    Handler workflow:
    1. Parse SNS message (source_id, timestamp, text_for_analysis)
    2. Load model (cached in global variable)
    3. Run inference
    4. Update DynamoDB (conditional: status=pending)
    5. Emit CloudWatch metrics

Security Notes:
    - Model loaded from Lambda layer (/opt/model)
    - Conditional updates prevent duplicate processing
    - No secrets in this Lambda (model is public)
"""

import json
import logging
import time
from decimal import Decimal
from typing import Any

from src.lambdas.analysis.sentiment import (
    InferenceError,
    ModelLoadError,
    analyze_sentiment,
    get_model_load_time_ms,
    load_model,
)
from src.lambdas.shared.dynamodb import get_table
from src.lib.metrics import (
    emit_metric,
    emit_metrics_batch,
    log_structured,
)

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main Lambda handler for sentiment analysis.

    Triggered by SNS messages from ingestion Lambda.

    Args:
        event: SNS event with Records array
        context: Lambda context (contains aws_request_id)

    Returns:
        Response with status and analysis results

    On-Call Note:
        If this handler fails repeatedly, check:
        1. Model is loaded correctly (cold start)
        2. DynamoDB item exists with status=pending
        3. SNS message format matches contract
    """
    start_time = time.perf_counter()
    request_id = getattr(context, "aws_request_id", "unknown")

    try:
        # Parse SNS message
        record = event["Records"][0]
        message = json.loads(record["Sns"]["Message"])

        source_id = message["source_id"]
        timestamp = message["timestamp"]
        text = message["text_for_analysis"]
        model_version = message["model_version"]

        log_structured(
            "INFO",
            "Analysis started",
            request_id=request_id,
            source_id=source_id,
        )

        # Load model (cached after first invocation)
        # On-Call Note: Cold start adds 1.7-4.9s for model load
        load_model()

        model_load_time = get_model_load_time_ms()
        if model_load_time > 0:
            emit_metric("ModelLoadTimeMs", model_load_time, unit="Milliseconds")

        # Run inference
        inference_start = time.perf_counter()
        sentiment, score = analyze_sentiment(text)
        inference_time_ms = (time.perf_counter() - inference_start) * 1000

        log_structured(
            "INFO",
            "Inference complete",
            source_id=source_id,
            sentiment=sentiment,
            score=round(score, 4),
            inference_time_ms=round(inference_time_ms, 2),
        )

        # Update DynamoDB with results
        # On-Call Note: Uses conditional update to prevent duplicate processing
        table = get_table()
        updated = _update_item_with_sentiment(
            table=table,
            source_id=source_id,
            timestamp=timestamp,
            sentiment=sentiment,
            score=score,
            model_version=model_version,
        )

        # Calculate total execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Emit metrics
        _emit_analysis_metrics(
            sentiment=sentiment,
            inference_time_ms=inference_time_ms,
            updated=updated,
        )

        log_structured(
            "INFO",
            "Analysis completed",
            source_id=source_id,
            sentiment=sentiment,
            score=round(score, 4),
            model_version=model_version,
            inference_time_ms=round(inference_time_ms, 2),
            execution_time_ms=round(execution_time_ms, 2),
            updated=updated,
        )

        return {
            "statusCode": 200,
            "body": {
                "source_id": source_id,
                "sentiment": sentiment,
                "score": round(score, 4),
                "model_version": model_version,
                "inference_time_ms": round(inference_time_ms, 2),
                "updated": updated,
            },
        }

    except KeyError as e:
        # Missing field in SNS message
        logger.error(f"Invalid SNS message format: missing {e}")
        emit_metric("AnalysisErrors", 1)

        return {
            "statusCode": 400,
            "body": {
                "error": f"Invalid message format: missing {e}",
                "code": "VALIDATION_ERROR",
            },
        }

    except ModelLoadError as e:
        # Model loading failed
        logger.error(f"Model load error: {e}")
        emit_metric("AnalysisErrors", 1)
        emit_metric("ModelLoadErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Failed to load sentiment model",
                "code": "MODEL_ERROR",
                "details": str(e),
            },
        }

    except InferenceError as e:
        # Inference failed
        logger.error(f"Inference error: {e}")
        emit_metric("AnalysisErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Sentiment inference failed",
                "code": "MODEL_ERROR",
                "details": str(e),
            },
        }

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error: {e}", exc_info=True)
        emit_metric("AnalysisErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Internal error",
                "code": "INTERNAL_ERROR",
                "details": str(e),
            },
        }


def _update_item_with_sentiment(
    table: Any,
    source_id: str,
    timestamp: str,
    sentiment: str,
    score: float,
    model_version: str,
) -> bool:
    """
    Update DynamoDB item with sentiment analysis results.

    Uses conditional update to only process items with status=pending.
    This prevents duplicate processing from SNS redelivery.

    Args:
        table: DynamoDB table resource
        source_id: Item partition key
        timestamp: Item sort key
        sentiment: Analysis result (positive/negative/neutral)
        score: Confidence score 0.0-1.0
        model_version: Model version used

    Returns:
        True if item was updated, False if already analyzed

    On-Call Note:
        If this returns False frequently, check:
        1. SNS is redelivering messages (expected behavior)
        2. Multiple Lambdas processing same item (check concurrency)
    """
    try:
        # Update with conditional check
        table.update_item(
            Key={
                "source_id": source_id,
                "timestamp": timestamp,
            },
            UpdateExpression=(
                "SET sentiment = :s, score = :sc, model_version = :mv, "
                "#status = :analyzed"
            ),
            ExpressionAttributeNames={
                "#status": "status",
            },
            ExpressionAttributeValues={
                ":s": sentiment,
                ":sc": Decimal(str(round(score, 4))),
                ":mv": model_version,
                ":analyzed": "analyzed",
                ":pending": "pending",
            },
            ConditionExpression="#status = :pending",
        )

        logger.debug(
            "Item updated with sentiment",
            extra={"source_id": source_id, "sentiment": sentiment},
        )
        return True

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Item already analyzed (duplicate SNS message)
        logger.warning(
            "Item already analyzed, skipping",
            extra={"source_id": source_id},
        )
        emit_metric("DuplicateAnalysisSkipped", 1)
        return False

    except Exception as e:
        logger.error(
            f"Failed to update item: {e}",
            extra={"source_id": source_id, "error": str(e)},
        )
        raise


def _emit_analysis_metrics(
    sentiment: str,
    inference_time_ms: float,
    updated: bool,
) -> None:
    """
    Emit CloudWatch metrics for analysis.

    Args:
        sentiment: Analysis result
        inference_time_ms: Time for inference
        updated: Whether item was updated

    On-Call Note:
        These metrics power CloudWatch alarms:
        - InferenceLatencyMs > 500ms → High latency alarm
        - AnalysisErrors > 5 in 10min → Error rate alarm
    """
    metrics = [
        {"name": "SentimentAnalysisCount", "value": 1, "unit": "Count"},
        {
            "name": "InferenceLatencyMs",
            "value": inference_time_ms,
            "unit": "Milliseconds",
        },
    ]

    # Emit sentiment-specific metric
    sentiment_metric_name = f"{sentiment.capitalize()}SentimentCount"
    metrics.append({"name": sentiment_metric_name, "value": 1, "unit": "Count"})

    # Only count as processed if actually updated
    if updated:
        metrics.append({"name": "ItemsAnalyzed", "value": 1, "unit": "Count"})

    emit_metrics_batch(metrics)
