"""
Pydantic Validation Schemas
===========================

Data models for validating input/output across the sentiment analysis pipeline.

For On-Call Engineers:
    Validation errors appear as VALIDATION_ERROR in logs with details field
    showing specific field failures. Common issues:
    - Missing required fields (title, url, publishedAt)
    - Invalid sentiment value (must be positive/neutral/negative)
    - Score out of range (must be 0.0-1.0)

    See SC-03, SC-04 in ON_CALL_SOP.md for validation-related incidents.

For Developers:
    - Use SentimentItemCreate for ingestion input validation
    - Use SentimentItemUpdate for analysis output validation
    - Use SentimentItemResponse for dashboard API responses
    - All models include field descriptions for API documentation

Security Notes:
    - All external input must pass through these schemas before processing
    - Snippet is truncated to 200 chars (no full article storage)
    - URL validated as proper format (prevents injection)
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SentimentItemCreate(BaseModel):
    """
    Schema for creating a new sentiment item during ingestion.

    Used by ingestion Lambda to validate NewsAPI articles before storing.

    On-Call Note:
        If validation fails, check the NewsAPI response format.
        Required fields: title, url, publishedAt
    """

    source_id: str = Field(
        ...,
        description="Unique identifier: newsapi#{hash}",
        examples=["newsapi#abc123def456"],
        min_length=1,
        max_length=100,
    )

    timestamp: str = Field(
        ...,
        description="ISO8601 timestamp of article publication",
        examples=["2025-11-17T14:30:00.000Z"],
    )

    title: str = Field(
        ...,
        description="Article title",
        min_length=1,
        max_length=500,
    )

    snippet: str = Field(
        ...,
        description="Truncated article content (max 200 chars)",
        max_length=200,
    )

    url: str = Field(
        ...,
        description="Original article URL",
        examples=["https://example.com/article/123"],
    )

    tag: str = Field(
        ...,
        description="Watch tag that matched this article",
        examples=["AI", "climate", "economy"],
        min_length=1,
        max_length=50,
    )

    status: Literal["pending"] = Field(
        default="pending",
        description="Initial status is always pending",
    )

    ttl_timestamp: int = Field(
        ...,
        description="Unix timestamp for DynamoDB TTL (30 days from ingestion)",
        gt=0,
    )

    # Optional metadata
    author: str | None = Field(
        default=None,
        description="Article author if available",
        max_length=200,
    )

    source_name: str | None = Field(
        default=None,
        description="News source name",
        max_length=200,
    )

    @field_validator("source_id")
    @classmethod
    def validate_source_id_format(cls, v: str) -> str:
        """Validate source_id starts with expected prefix."""
        if not v.startswith("newsapi#"):
            raise ValueError("source_id must start with 'newsapi#'")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        """Validate timestamp is ISO8601 format."""
        try:
            # Parse to validate format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO8601 timestamp: {v}") from e
        return v

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Validate URL has proper format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class SentimentItemUpdate(BaseModel):
    """
    Schema for updating a sentiment item after analysis.

    Used by analysis Lambda to validate inference results before storing.

    On-Call Note:
        If validation fails, check model output format.
        sentiment must be: positive, neutral, or negative
        score must be: 0.0 to 1.0
    """

    sentiment: Literal["positive", "neutral", "negative"] = Field(
        ...,
        description="Sentiment classification result",
    )

    score: float = Field(
        ...,
        description="Confidence score from model (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    model_version: str = Field(
        ...,
        description="Version of sentiment model used",
        examples=["v1.0.0"],
        pattern=r"^v\d+\.\d+\.\d+$",
    )

    status: Literal["analyzed"] = Field(
        default="analyzed",
        description="Status after analysis is always analyzed",
    )

    @field_validator("score")
    @classmethod
    def validate_score_precision(cls, v: float) -> float:
        """Round score to 4 decimal places."""
        return round(v, 4)


class SentimentItemResponse(BaseModel):
    """
    Schema for sentiment item in API responses.

    Used by dashboard Lambda for /api/metrics responses.

    For Developers:
        This is the public-facing schema. It includes all fields
        that are safe to expose to dashboard users.
    """

    source_id: str = Field(
        ...,
        description="Unique identifier",
    )

    timestamp: str = Field(
        ...,
        description="Article publication time",
    )

    title: str = Field(
        ...,
        description="Article title",
    )

    snippet: str = Field(
        ...,
        description="Truncated article content",
    )

    url: str = Field(
        ...,
        description="Link to original article",
    )

    tag: str = Field(
        ...,
        description="Matched watch tag",
    )

    status: Literal["pending", "analyzed"] = Field(
        ...,
        description="Processing status",
    )

    # Analysis results (optional for pending items)
    sentiment: Literal["positive", "neutral", "negative"] | None = Field(
        default=None,
        description="Sentiment classification",
    )

    score: float | None = Field(
        default=None,
        description="Confidence score",
        ge=0.0,
        le=1.0,
    )

    model_version: str | None = Field(
        default=None,
        description="Model version used for analysis",
    )


class SNSAnalysisMessage(BaseModel):
    """
    Schema for SNS message triggering analysis.

    Published by ingestion Lambda, consumed by analysis Lambda.

    On-Call Note:
        If analysis Lambda fails to parse SNS message, check this schema
        matches what ingestion is publishing.
    """

    source_id: str = Field(
        ...,
        description="Item identifier for DynamoDB lookup",
    )

    timestamp: str = Field(
        ...,
        description="Sort key for DynamoDB lookup",
    )

    text_for_analysis: str = Field(
        ...,
        description="Combined title + snippet for sentiment analysis",
        min_length=1,
    )

    correlation_id: str = Field(
        ...,
        description="Tracing ID: {source_id}-{request_id}",
    )


class MetricsResponse(BaseModel):
    """
    Schema for dashboard /api/metrics response.

    Aggregated metrics for the dashboard display.
    """

    total_items: int = Field(
        ...,
        description="Total number of items in database",
        ge=0,
    )

    analyzed_items: int = Field(
        ...,
        description="Number of analyzed items",
        ge=0,
    )

    pending_items: int = Field(
        ...,
        description="Number of pending items",
        ge=0,
    )

    sentiment_distribution: dict[str, int] = Field(
        ...,
        description="Count by sentiment: {positive: N, neutral: N, negative: N}",
    )

    tag_distribution: dict[str, int] = Field(
        ...,
        description="Count by tag",
    )

    recent_items: list[SentimentItemResponse] = Field(
        ...,
        description="Most recent analyzed items",
        max_length=20,
    )

    last_updated: str = Field(
        ...,
        description="ISO8601 timestamp of metrics calculation",
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "MetricsResponse":
        """Validate that counts are consistent."""
        if self.analyzed_items + self.pending_items != self.total_items:
            raise ValueError(
                f"analyzed_items ({self.analyzed_items}) + pending_items "
                f"({self.pending_items}) must equal total_items ({self.total_items})"
            )
        return self


class HealthResponse(BaseModel):
    """
    Schema for dashboard /health endpoint response.

    On-Call Note:
        This endpoint is unauthenticated for monitoring systems.
        Only returns connectivity status, no sensitive data.
    """

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall health status",
    )

    dynamodb: Literal["connected", "disconnected"] = Field(
        ...,
        description="DynamoDB connectivity status",
    )

    timestamp: str = Field(
        ...,
        description="ISO8601 timestamp of health check",
    )

    version: str = Field(
        ...,
        description="Application version",
    )


class ErrorResponse(BaseModel):
    """
    Schema for standardized error responses.

    Used by all Lambdas for consistent error formatting.
    See plan.md "Standardized Error Response Schema" section.
    """

    error: str = Field(
        ...,
        description="Human-readable error message",
    )

    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=[
            "RATE_LIMIT_EXCEEDED",
            "VALIDATION_ERROR",
            "NOT_FOUND",
            "SECRET_ERROR",
            "DATABASE_ERROR",
        ],
    )

    details: dict | None = Field(
        default=None,
        description="Additional error context",
    )

    request_id: str = Field(
        ...,
        description="Lambda request ID for correlation",
    )
