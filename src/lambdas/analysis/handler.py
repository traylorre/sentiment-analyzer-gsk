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
    - Model downloaded from S3 to /tmp/model (no Lambda layer)
    - Conditional updates prevent duplicate processing
    - No secrets in this Lambda (model is public)
"""

import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Tracer

from src.lambdas.shared.logging_config import configure_lambda_logging

configure_lambda_logging()

tracer = Tracer(service="sentiment-analyzer-analysis")

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
from src.lib.timeseries import FanoutWriteError, SentimentScore, accumulate_fanout
from src.lib.timeseries.signed import label_to_signed

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main Lambda handler for sentiment analysis.

    Triggered by SNS messages from ingestion Lambda.

    Args:
        event: SNS event with Records array (or warmup event with {"warmup": true})
        context: Lambda context (contains aws_request_id)

    Returns:
        Response with status and analysis results

    On-Call Note:
        If this handler fails repeatedly, check:
        1. Model is loaded correctly (cold start)
        2. DynamoDB item exists with status=pending
        3. SNS message format matches contract
    """
    # Feature 142: Warmup support - short-circuit for warmup invocations
    # This is especially important for Analysis Lambda which loads ML model on cold start
    if event.get("warmup"):
        log_structured("INFO", "Warmup invocation - returning early")
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"status": "warmed", "message": "Lambda container initialized"}
            ),
        }

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
        # Feature 1009: Extract tickers for time-series fanout
        matched_tickers = message.get("matched_tickers", [])
        # Feature 001-signed-fanout: provider names for bucket source tracking
        provider_sources = message.get("sources", [])

        log_structured(
            "INFO",
            "Analysis started",
            request_id=request_id,
            source_id=source_id,
            ticker_count=len(matched_tickers),
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

        # Feature 1009: Write fanout to time-series table for real-time streaming
        # Canonical: [CS-001] "Pre-aggregate at write time for known query patterns"
        # Canonical: [CS-003] "Write amplification acceptable when reads >> writes"
        if updated and matched_tickers:
            _write_timeseries_fanout(
                tickers=matched_tickers,
                score=score,
                sentiment=sentiment,
                timestamp=timestamp,
                sources=provider_sources,
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
                # Fix(152): Add confidence field to match contract tests
                # Contract expects sentiment, score, confidence per tests/property/conftest.py
                "confidence": round(score, 4),
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
        # Unexpected error - log environment context for debugging
        # Fix(151): Add DATABASE_TABLE to error logs for debugging 500 errors
        database_table = os.environ.get("DATABASE_TABLE", "<NOT_SET>")
        logger.error(
            f"Unexpected error: {e}",
            exc_info=True,
            extra={
                "database_table": database_table,
                "request_id": request_id,
            },
        )
        emit_metric("AnalysisErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Internal error",
                "code": "INTERNAL_ERROR",
                "details": str(e),
            },
        }


@tracer.capture_method
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
        score: Unsigned model confidence 0.0-1.0, stored unchanged (FR-008);
            the signed mapping happens only at the timeseries fanout hop
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
        # Fix(151): Log DATABASE_TABLE for debugging DynamoDB errors
        database_table = os.environ.get("DATABASE_TABLE", "<NOT_SET>")
        logger.error(
            f"Failed to update item: {e}",
            extra={
                "source_id": source_id,
                "database_table": database_table,
                "error": str(e),
            },
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


# Global DynamoDB client for time-series writes (Lambda global scope caching [CS-005])
_dynamodb_client: Any = None


def _get_dynamodb_client() -> Any:
    """Get DynamoDB client with Lambda global scope caching.

    Canonical: [CS-005] "Initialize SDK clients outside of the handler function"
    Canonical: [CS-006] "Reuse connections across invocations"
    """
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


# FR-010 timestamp bounds: reject, don't clamp (research D3)
FANOUT_MAX_FUTURE = timedelta(minutes=5)
FANOUT_MAX_AGE = timedelta(days=30)


@tracer.capture_method
def _write_timeseries_fanout(
    tickers: list[str],
    score: float,
    sentiment: str,
    timestamp: str,
    sources: list[str],
) -> None:
    """Accumulate the signed contribution into time-series buckets for all
    matched tickers.

    Feature 001-signed-fanout: signed values via label_to_signed, accumulating
    buckets via accumulate_fanout, provider names from the SNS sources field.

    Args:
        tickers: List of ticker symbols this sentiment applies to
        score: Unsigned model confidence; signed at this hop
        sentiment: Sentiment label (positive/negative/neutral)
        timestamp: ISO8601 timestamp of the original article
        sources: Provider names from the SNS message (tiingo/finnhub)

    Note:
        Failures are logged but don't fail the Lambda - time-series is
        supplementary to the primary sentiment-items table update.
    """
    timeseries_table = os.environ.get("TIMESERIES_TABLE")
    if not timeseries_table:
        # TIMESERIES_TABLE not configured - skip fanout silently
        return

    try:
        # Parse timestamp to datetime
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError) as e:
        logger.warning(
            "Invalid timestamp for fanout, skipping",
            extra={"timestamp": timestamp, "error": str(e)},
        )
        return

    # FR-010: article timestamps outside [now - 30d, now + 5min] skip fanout
    # only; the per-article record has already stored. No raw text logged.
    now = datetime.now(UTC)
    if ts > now + FANOUT_MAX_FUTURE or ts < now - FANOUT_MAX_AGE:
        logger.warning(
            "Article timestamp outside fanout bounds, skipping fanout",
            extra={
                "tickers": tickers,
                "timestamp_age_seconds": (now - ts).total_seconds(),
            },
        )
        emit_metric("TimeseriesFanoutRejectedTimestamp", 1)
        return

    provider = sources[0] if sources else None
    dynamodb = _get_dynamodb_client()
    fanout_count = 0
    fanout_errors = 0

    for ticker in tickers:
        try:
            sentiment_score = SentimentScore(
                ticker=ticker.upper(),
                value=label_to_signed(sentiment, score),
                timestamp=ts,
                label=sentiment,
                source=provider,
            )
            accumulate_fanout(dynamodb, timeseries_table, sentiment_score)
            fanout_count += 1
        except FanoutWriteError as e:
            # FR-009: one structured record carrying the repair coordinates;
            # repair is the targeted backfill (quickstart.md runbook)
            fanout_errors += 1
            log_structured(
                "ERROR",
                "Time-series fanout failed after retries",
                ticker=e.ticker,
                resolution=e.resolution,
                window=e.window,
                error_class=e.error_class,
            )
        except Exception as e:
            fanout_errors += 1
            logger.warning(
                "Time-series fanout failed for ticker",
                extra={
                    "ticker": ticker,
                    "error": str(e),
                    "table": timeseries_table,
                },
            )

    if fanout_count > 0:
        emit_metric("TimeseriesFanoutCount", fanout_count)
        log_structured(
            "INFO",
            "Time-series fanout complete",
            tickers_written=fanout_count,
            tickers_failed=fanout_errors,
        )

    if fanout_errors > 0:
        emit_metric("TimeseriesFanoutErrors", fanout_errors)
