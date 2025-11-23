"""
Sentiment Analysis Module
=========================

DistilBERT-based sentiment inference with model caching.

For On-Call Engineers:
    Model loading issues:
    - If cold start > 5s: Check memory allocation (should be 1024MB)
    - If model not found: Verify /opt/model exists in Lambda layer
    - If inference errors: Check CloudWatch logs for OOM errors

    Quick commands:
    # Check model load time
    aws logs filter-log-events \
      --log-group-name /aws/lambda/${environment}-sentiment-analysis \
      --filter-pattern "Model loaded"

    # Check inference latency
    aws cloudwatch get-metric-statistics \
      --namespace SentimentAnalyzer \
      --metric-name InferenceLatencyMs \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 300 --statistics Average

    See SC-04 and SC-06 in ON_CALL_SOP.md for analysis issues.

For Developers:
    - Model is cached in global variable for Lambda container reuse
    - Use analyze_sentiment() for inference
    - Neutral threshold: score < 0.6 (model uncertainty)
    - Text is truncated to 512 tokens (DistilBERT limit)

Security Notes:
    - Model loaded from Lambda layer (/opt/model)
    - No user input in model path (prevent path traversal)
    - Text input is truncated, not sanitized (model handles encoding)
"""

import logging
import os
import tarfile
import time
from pathlib import Path
from typing import Any

# Structured logging
logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL_S3_BUCKET = os.environ.get(
    "MODEL_S3_BUCKET", "sentiment-analyzer-models-218795110243"
)
DEFAULT_MODEL_S3_KEY = "distilbert/v1.0.0/model.tar.gz"
LOCAL_MODEL_PATH = (
    "/tmp/model"  # noqa: S108 - Lambda /tmp storage (configurable up to 10GB)
)
MAX_TEXT_LENGTH = 512  # DistilBERT token limit
NEUTRAL_THRESHOLD = 0.6  # Below this confidence → neutral

# Global variable for model caching
# On-Call Note: This persists across warm Lambda invocations
_sentiment_pipeline: Any = None
_model_load_time_ms: float = 0


def _download_model_from_s3() -> None:
    """
    Download ML model from S3 to Lambda /tmp storage.

    Only downloads if model doesn't already exist locally (Lambda container reuse).
    Model is extracted from tar.gz to /tmp/model for transformers to load.

    On-Call Note:
        If downloads are slow:
        1. Check S3 bucket is in same region as Lambda (us-east-1)
        2. Check Lambda has s3:GetObject permission
        3. Download time ~3-5s for 250MB model (acceptable cold start)
    """
    import boto3

    model_path = Path(LOCAL_MODEL_PATH)

    # Check if model already exists (warm Lambda container)
    if model_path.exists() and (model_path / "config.json").exists():
        logger.info(
            "Model already exists in /tmp (warm container)",
            extra={"model_path": str(model_path)},
        )
        return

    logger.info(
        f"Downloading model from S3: s3://{DEFAULT_MODEL_S3_BUCKET}/{DEFAULT_MODEL_S3_KEY}"
    )

    try:
        # Download model tar.gz from S3
        s3_client = boto3.client("s3")
        tar_path = "/tmp/model.tar.gz"  # noqa: S108 - Lambda /tmp storage

        download_start = time.perf_counter()
        s3_client.download_file(
            Bucket=DEFAULT_MODEL_S3_BUCKET, Key=DEFAULT_MODEL_S3_KEY, Filename=tar_path
        )
        download_time_ms = (time.perf_counter() - download_start) * 1000

        logger.info(
            "Model downloaded from S3",
            extra={"download_time_ms": round(download_time_ms, 2)},
        )

        # Extract tar.gz to /tmp/model
        extract_start = time.perf_counter()
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path="/tmp")  # noqa: S108 - Lambda /tmp storage
        extract_time_ms = (time.perf_counter() - extract_start) * 1000

        logger.info(
            "Model extracted successfully",
            extra={
                "extract_time_ms": round(extract_time_ms, 2),
                "total_time_ms": round(download_time_ms + extract_time_ms, 2),
            },
        )

        # Clean up tar.gz to save /tmp space
        Path(tar_path).unlink()

    except Exception as e:
        logger.error(
            f"Failed to download model from S3: {e}",
            extra={
                "bucket": DEFAULT_MODEL_S3_BUCKET,
                "key": DEFAULT_MODEL_S3_KEY,
                "error": str(e),
            },
        )
        raise ModelLoadError(f"Failed to download model from S3: {e}") from e


def load_model(model_path: str | None = None) -> Any:
    """
    Load HuggingFace DistilBERT sentiment model with S3 lazy loading and caching.

    Model loading strategy:
    1. Check global cache (warm Lambda container) → Return immediately
    2. Check /tmp/model exists → Load from disk
    3. Download from S3 → Extract → Load

    Args:
        model_path: Path to model directory (default: /tmp/model from S3)

    Returns:
        HuggingFace pipeline for sentiment analysis

    Raises:
        ModelLoadError: If model cannot be downloaded or loaded

    On-Call Note:
        Cold start times:
        - Warm container (cached): 0ms (instant)
        - Warm /tmp (model on disk): ~1-2s (load only)
        - Cold /tmp (S3 download): ~5-7s (download + extract + load)

        If cold starts >10s:
        1. Check Lambda memory (should be 1024MB+)
        2. Check S3 bucket region matches Lambda
        3. Check /tmp storage size (should be 3GB)
    """
    global _sentiment_pipeline, _model_load_time_ms

    # Return cached model if available (warm Lambda container)
    if _sentiment_pipeline is not None:
        logger.debug("Using cached sentiment pipeline")
        return _sentiment_pipeline

    # Determine model path
    path = model_path or os.environ.get("MODEL_PATH", LOCAL_MODEL_PATH)

    logger.info(f"Loading sentiment model from {path}")
    start_time = time.perf_counter()

    try:
        # Download model from S3 if not in /tmp (only on cold start)
        _download_model_from_s3()

        # Import here to avoid cold start penalty if model is cached
        from transformers import pipeline

        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=path,
            tokenizer=path,
            framework="pt",  # PyTorch
            device=-1,  # CPU (Lambda doesn't have GPU)
        )

        _model_load_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Model loaded successfully",
            extra={
                "model_path": path,
                "load_time_ms": round(_model_load_time_ms, 2),
            },
        )

        return _sentiment_pipeline

    except Exception as e:
        logger.error(
            f"Failed to load model: {e}",
            extra={"model_path": path, "error": str(e)},
        )
        raise ModelLoadError(f"Failed to load model from {path}: {e}") from e


def analyze_sentiment(text: str) -> tuple[str, float]:
    """
    Run sentiment inference on text.

    Args:
        text: Text to analyze (will be truncated to 512 chars)

    Returns:
        Tuple of (sentiment, score):
        - sentiment: 'positive', 'negative', or 'neutral'
        - score: confidence 0.0-1.0

    Raises:
        ModelLoadError: If model is not loaded
        InferenceError: If inference fails

    Examples:
        >>> sentiment, score = analyze_sentiment("This product is amazing!")
        >>> sentiment
        'positive'
        >>> score > 0.8
        True

        >>> sentiment, score = analyze_sentiment("The weather is okay.")
        >>> sentiment
        'neutral'  # Low confidence

    On-Call Note:
        If many items are classified as neutral:
        1. Check if text_for_analysis is empty
        2. Verify model is correct version
        3. Review CloudWatch metric NeutralSentimentCount
    """
    # Load model (cached)
    pipeline_instance = load_model()

    # Truncate text to model limit
    # On-Call Note: Very long text is truncated, not split
    truncated_text = text[:MAX_TEXT_LENGTH] if text else ""

    if not truncated_text:
        logger.warning("Empty text for analysis, returning neutral")
        return "neutral", 0.5

    try:
        # Run inference
        # DistilBERT returns: [{'label': 'POSITIVE'|'NEGATIVE', 'score': 0.95}]
        result = pipeline_instance(truncated_text)[0]

        label = result["label"].lower()
        score = result["score"]

        # Map to three-way classification
        # On-Call Note: Low confidence → neutral (model is uncertain)
        if score < NEUTRAL_THRESHOLD:
            sentiment = "neutral"
        else:
            sentiment = label  # 'positive' or 'negative'

        logger.debug(
            "Sentiment analysis complete",
            extra={
                "raw_label": label,
                "score": round(score, 4),
                "mapped_sentiment": sentiment,
                "text_length": len(truncated_text),
            },
        )

        return sentiment, score

    except Exception as e:
        logger.error(
            f"Inference failed: {e}",
            extra={"text_length": len(truncated_text), "error": str(e)},
        )
        raise InferenceError(f"Sentiment inference failed: {e}") from e


def get_model_load_time_ms() -> float:
    """
    Get the time taken to load the model.

    Returns:
        Load time in milliseconds, or 0 if model not loaded yet

    On-Call Note:
        Use this metric for cold start monitoring.
        Target: <2500ms for 1024MB Lambda.
    """
    return _model_load_time_ms


def is_model_loaded() -> bool:
    """
    Check if the model is currently loaded.

    Returns:
        True if model is cached, False otherwise
    """
    return _sentiment_pipeline is not None


def clear_model_cache() -> None:
    """
    Clear the cached model.

    Use for testing or forced model reload.
    In production, this should rarely be needed.
    """
    global _sentiment_pipeline, _model_load_time_ms
    _sentiment_pipeline = None
    _model_load_time_ms = 0
    logger.debug("Model cache cleared")


# Custom exceptions
class SentimentError(Exception):
    """Base exception for sentiment analysis errors."""

    pass


class ModelLoadError(SentimentError):
    """Raised when model cannot be loaded."""

    pass


class InferenceError(SentimentError):
    """Raised when inference fails."""

    pass
