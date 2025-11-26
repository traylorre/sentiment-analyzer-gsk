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
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple

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


# =============================================================================
# Dual-Source Sentiment Aggregation (T065)
# =============================================================================
#
# Feature 006 requires combining sentiment from multiple sources:
# - Tiingo: News-based sentiment derived from article analysis
# - Finnhub: Market sentiment from their API
# - Our Model: DistilBERT ML inference on article text
#
# The aggregation strategy weighs sources by reliability:
# - Finnhub: 40% weight (real-time market data)
# - Our Model: 35% weight (ML-based, text analysis)
# - Tiingo: 25% weight (news volume/recency heuristics)
# =============================================================================


class SentimentSource(str, Enum):
    """Available sentiment data sources."""

    TIINGO = "tiingo"
    FINNHUB = "finnhub"
    OUR_MODEL = "our_model"


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class SourceSentimentScore:
    """Sentiment score from a single source."""

    source: SentimentSource
    score: float  # -1.0 to 1.0
    label: SentimentLabel
    confidence: float  # 0.0 to 1.0
    timestamp: dt
    metadata: dict | None = None


class AggregatedSentiment(NamedTuple):
    """Aggregated sentiment from multiple sources."""

    score: float  # -1.0 to 1.0
    label: SentimentLabel
    confidence: float  # 0.0 to 1.0
    sources: dict[SentimentSource, SourceSentimentScore]
    agreement_score: float  # How much sources agree (0.0 to 1.0)


# Aggregation weights (must sum to 1.0)
SOURCE_WEIGHTS = {
    SentimentSource.FINNHUB: 0.40,  # Market sentiment API
    SentimentSource.OUR_MODEL: 0.35,  # ML model
    SentimentSource.TIINGO: 0.25,  # News volume heuristics
}

# Thresholds for label classification
POSITIVE_THRESHOLD = 0.33
NEGATIVE_THRESHOLD = -0.33


def aggregate_sentiment(
    source_scores: list[SourceSentimentScore],
    weights: dict[SentimentSource, float] | None = None,
) -> AggregatedSentiment:
    """
    Aggregate sentiment from multiple sources using weighted average.

    Args:
        source_scores: List of sentiment scores from different sources
        weights: Optional custom weights (default: SOURCE_WEIGHTS)

    Returns:
        AggregatedSentiment with combined score, label, and confidence

    Example:
        >>> scores = [
        ...     SourceSentimentScore(SentimentSource.FINNHUB, 0.5, SentimentLabel.POSITIVE, 0.9, dt.now()),
        ...     SourceSentimentScore(SentimentSource.OUR_MODEL, 0.3, SentimentLabel.NEUTRAL, 0.8, dt.now()),
        ... ]
        >>> result = aggregate_sentiment(scores)
        >>> result.score > 0.0
        True
    """
    if not source_scores:
        return AggregatedSentiment(
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.0,
            sources={},
            agreement_score=0.0,
        )

    weights = weights or SOURCE_WEIGHTS

    # Build source map
    sources = {s.source: s for s in source_scores}

    # Calculate weighted average score
    total_weight = 0.0
    weighted_score = 0.0

    for source, score_data in sources.items():
        weight = weights.get(source, 0.1)  # Default weight for unknown sources
        weighted_score += score_data.score * weight * score_data.confidence
        total_weight += weight * score_data.confidence

    if total_weight > 0:
        final_score = weighted_score / total_weight
    else:
        final_score = 0.0

    # Clamp to [-1, 1]
    final_score = max(-1.0, min(1.0, final_score))

    # Calculate agreement score (how close are all sources to the average)
    if len(sources) > 1:
        variance = sum((s.score - final_score) ** 2 for s in sources.values()) / len(
            sources
        )
        # Convert variance to agreement (low variance = high agreement)
        # Max variance is 4 (from -1 to 1), so divide by 4 for normalization
        agreement_score = max(0.0, 1.0 - (variance / 2.0))
    else:
        agreement_score = 1.0  # Single source always agrees with itself

    # Determine label
    final_label = _score_to_label_enum(final_score)

    # Calculate overall confidence (weighted average of source confidences * agreement)
    avg_confidence = sum(s.confidence for s in sources.values()) / len(sources)
    final_confidence = avg_confidence * agreement_score

    return AggregatedSentiment(
        score=round(final_score, 4),
        label=final_label,
        confidence=round(final_confidence, 4),
        sources=sources,
        agreement_score=round(agreement_score, 4),
    )


def analyze_text_sentiment(text: str) -> SourceSentimentScore:
    """
    Analyze text using our ML model and return as SourceSentimentScore.

    This is a wrapper around analyze_sentiment() for the aggregation pipeline.

    Args:
        text: Text to analyze

    Returns:
        SourceSentimentScore from our ML model
    """
    sentiment, score = analyze_sentiment(text)

    # Map string label to enum
    if sentiment == "positive":
        label = SentimentLabel.POSITIVE
    elif sentiment == "negative":
        label = SentimentLabel.NEGATIVE
    else:
        label = SentimentLabel.NEUTRAL

    # DistilBERT outputs confidence as score (closer to 1.0 = more confident)
    confidence = score if score >= 0.5 else 0.5 + (0.5 - score)

    return SourceSentimentScore(
        source=SentimentSource.OUR_MODEL,
        score=_label_to_score(sentiment, score),
        label=label,
        confidence=confidence,
        timestamp=dt.now(UTC),
        metadata={"model_version": "distilbert-v1.0", "text_length": len(text)},
    )


def create_finnhub_score(
    sentiment_score: float,
    bullish_percent: float,
    bearish_percent: float,
    timestamp: dt | None = None,
) -> SourceSentimentScore:
    """
    Create SourceSentimentScore from Finnhub API response.

    Args:
        sentiment_score: Finnhub sentiment score (-1 to 1)
        bullish_percent: Percentage bullish (0-1)
        bearish_percent: Percentage bearish (0-1)
        timestamp: When data was fetched

    Returns:
        SourceSentimentScore for aggregation
    """
    label = _score_to_label_enum(sentiment_score)

    # Confidence based on how decisive the market sentiment is
    # High bullish OR high bearish = high confidence
    # 50/50 split = low confidence
    spread = abs(bullish_percent - bearish_percent)
    confidence = 0.5 + (spread * 0.5)  # Maps 0-1 spread to 0.5-1.0 confidence

    return SourceSentimentScore(
        source=SentimentSource.FINNHUB,
        score=sentiment_score,
        label=label,
        confidence=confidence,
        timestamp=timestamp or dt.now(UTC),
        metadata={
            "bullish_percent": bullish_percent,
            "bearish_percent": bearish_percent,
        },
    )


def create_tiingo_score(
    positive_count: int,
    negative_count: int,
    total_articles: int,
    timestamp: dt | None = None,
) -> SourceSentimentScore:
    """
    Create SourceSentimentScore from Tiingo news data.

    Uses simple heuristics based on news article keyword analysis.

    Args:
        positive_count: Number of positive-indicating articles
        negative_count: Number of negative-indicating articles
        total_articles: Total number of articles analyzed
        timestamp: When data was fetched

    Returns:
        SourceSentimentScore for aggregation
    """
    if total_articles == 0:
        return SourceSentimentScore(
            source=SentimentSource.TIINGO,
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.0,
            timestamp=timestamp or dt.now(UTC),
            metadata={"article_count": 0},
        )

    # Score based on positive/negative ratio
    score = (positive_count - negative_count) / total_articles
    score = max(-1.0, min(1.0, score))

    label = _score_to_label_enum(score)

    # Confidence based on:
    # 1. Number of articles (more articles = higher confidence)
    # 2. Decisiveness (higher absolute score = higher confidence)
    article_confidence = min(1.0, total_articles / 20)  # 20+ articles = max confidence
    decisiveness_confidence = abs(score)
    confidence = 0.5 + (article_confidence * 0.25) + (decisiveness_confidence * 0.25)

    return SourceSentimentScore(
        source=SentimentSource.TIINGO,
        score=round(score, 4),
        label=label,
        confidence=round(confidence, 4),
        timestamp=timestamp or dt.now(UTC),
        metadata={
            "article_count": total_articles,
            "positive_count": positive_count,
            "negative_count": negative_count,
        },
    )


def _score_to_label_enum(score: float) -> SentimentLabel:
    """Convert numeric score to SentimentLabel enum."""
    if score >= POSITIVE_THRESHOLD:
        return SentimentLabel.POSITIVE
    elif score <= NEGATIVE_THRESHOLD:
        return SentimentLabel.NEGATIVE
    else:
        return SentimentLabel.NEUTRAL


def _label_to_score(sentiment: str, confidence: float) -> float:
    """
    Convert sentiment label and confidence to a score in [-1, 1].

    Args:
        sentiment: 'positive', 'negative', or 'neutral'
        confidence: Model confidence (0 to 1)

    Returns:
        Score in [-1, 1] range
    """
    if sentiment == "positive":
        return confidence  # 0.6 confidence = 0.6 score
    elif sentiment == "negative":
        return -confidence  # 0.6 confidence = -0.6 score
    else:
        # Neutral gets a small score based on which side it leans
        return 0.0  # Truly neutral


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
