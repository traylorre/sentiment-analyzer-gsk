"""
Time-series data models.

Canonical References:
- [CS-002] AWS Blog: Choosing the Right DynamoDB Partition Key
- [CS-004] Alex DeBrie: The DynamoDB Book (Chapter 9)
- [CS-011] Netflix Tech Blog: Streaming Time-Series Data
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Resolution(str, Enum):
    """
    Supported time resolutions for sentiment aggregation.

    Canonical: [CS-009] "Standard time-series granularities"
    """

    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    TEN_MINUTES = "10m"
    ONE_HOUR = "1h"
    THREE_HOURS = "3h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    TWENTY_FOUR_HOURS = "24h"

    @property
    def duration_seconds(self) -> int:
        """Return the duration of this resolution in seconds."""
        mapping = {
            "1m": 60,
            "5m": 300,
            "10m": 600,
            "1h": 3600,
            "3h": 10800,
            "6h": 21600,
            "12h": 43200,
            "24h": 86400,
        }
        return mapping[self.value]

    @property
    def ttl_seconds(self) -> int:
        """
        Return the TTL for this resolution in seconds.

        Canonical: [CS-013, CS-014] Resolution-dependent TTL
        - 1m: 6 hours
        - 5m: 12 hours
        - 10m: 24 hours
        - 1h: 7 days
        - 3h: 14 days
        - 6h: 30 days
        - 12h: 60 days
        - 24h: 90 days
        """
        mapping = {
            "1m": 6 * 3600,
            "5m": 12 * 3600,
            "10m": 24 * 3600,
            "1h": 7 * 86400,
            "3h": 14 * 86400,
            "6h": 30 * 86400,
            "12h": 60 * 86400,
            "24h": 90 * 86400,
        }
        return mapping[self.value]


class SentimentScore(BaseModel):
    """
    A single sentiment score from an analyzed article.

    Used as input to aggregation functions.
    """

    value: float = Field(ge=-1.0, le=1.0, description="Sentiment score [-1, 1]")
    timestamp: datetime = Field(description="When the article was analyzed")
    label: str | None = Field(
        default=None, description="Sentiment label (positive/neutral/negative)"
    )
    ticker: str | None = Field(default=None, description="Stock ticker symbol")
    source: str | None = Field(default=None, description="Data source (tiingo/finnhub)")


class OHLCBucket(BaseModel):
    """
    OHLC aggregation result for a time bucket.

    Canonical: [CS-011] "OHLC effective for any bounded metric where extrema matter"
    [CS-012] "Min/max/open/close captures distribution shape efficiently"
    """

    open: float = Field(description="First sentiment score in bucket")
    high: float = Field(description="Maximum sentiment score in bucket")
    low: float = Field(description="Minimum sentiment score in bucket")
    close: float = Field(description="Last sentiment score in bucket")
    count: int = Field(description="Number of scores in bucket")
    sum: float = Field(description="Sum of scores (for avg calculation)")
    avg: float = Field(description="Average sentiment score")
    label_counts: dict[str, int] = Field(
        default_factory=dict, description="Count by sentiment label"
    )


class SentimentBucket(BaseModel):
    """
    A time-bounded aggregation of sentiment data.

    Canonical: [CS-001] Write fanout pre-aggregation pattern
    """

    ticker: str
    resolution: Resolution
    timestamp: datetime = Field(description="Bucket start time (aligned to resolution)")
    open: float = Field(description="First sentiment score in bucket")
    high: float = Field(description="Maximum sentiment score in bucket")
    low: float = Field(description="Minimum sentiment score in bucket")
    close: float = Field(description="Last sentiment score in bucket")
    count: int = Field(description="Number of articles in bucket")
    sum: float = Field(description="Sum of scores")
    avg: float = Field(description="Average sentiment score")
    label_counts: dict[str, int] = Field(
        default_factory=dict, description="Distribution by label"
    )
    sources: list[str] = Field(default_factory=list, description="Unique data sources")
    is_partial: bool = Field(default=False, description="True for incomplete bucket")


class PartialBucket(SentimentBucket):
    """
    An incomplete sentiment bucket representing the current in-progress time period.

    Canonical: [CS-011] "Partial aggregates with progress indicators"
    """

    is_partial: bool = Field(default=True)
    progress_pct: float = Field(
        ge=0.0, le=100.0, description="Percentage through bucket period"
    )
    next_update_at: datetime | None = Field(
        default=None, description="When bucket will be complete"
    )


class TimeseriesKey(BaseModel):
    """
    DynamoDB key for time-series data.

    Canonical: [CS-002] "Use composite keys with delimiter for hierarchical access"
    [CS-004] "ticker#resolution is standard for multi-dimensional time-series"

    Key Pattern:
    - PK: {ticker}#{resolution} (e.g., "AAPL#5m")
    - SK: ISO8601 bucket timestamp (e.g., "2025-12-21T10:35:00Z")
    """

    ticker: str
    resolution: Resolution
    bucket_timestamp: datetime | None = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate ticker format."""
        if not v:
            raise ValueError("Ticker cannot be empty")
        if "#" in v:
            raise ValueError("Ticker cannot contain # delimiter")
        return v

    @property
    def pk(self) -> str:
        """Generate partition key: {ticker}#{resolution}."""
        return f"{self.ticker}#{self.resolution.value}"

    @property
    def sk(self) -> str:
        """Generate sort key: ISO8601 bucket timestamp."""
        if self.bucket_timestamp is None:
            raise ValueError("bucket_timestamp required for sort key")
        return self.bucket_timestamp.isoformat()

    def to_dynamodb_key(self) -> dict[str, Any]:
        """Convert to DynamoDB key format."""
        return {
            "PK": {"S": self.pk},
            "SK": {"S": self.sk},
        }

    @classmethod
    def from_dynamodb(cls, pk: str, sk: str) -> "TimeseriesKey":
        """Reconstruct key from DynamoDB strings."""
        parts = pk.split("#")
        if len(parts) != 2:
            raise ValueError(
                f"PK must match pattern {{ticker}}#{{resolution}}, got: {pk}"
            )

        ticker, resolution_str = parts
        bucket_timestamp = datetime.fromisoformat(sk.replace("Z", "+00:00"))

        return cls(
            ticker=ticker,
            resolution=Resolution(resolution_str),
            bucket_timestamp=bucket_timestamp,
        )
