"""SentimentResult model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SentimentSource(BaseModel):
    """Source metadata for sentiment."""

    model_config = {"populate_by_name": True}

    source_type: Literal["tiingo", "finnhub", "our_model"]
    inference_version: str | None = Field(default=None, alias="model_version")
    fetched_at: datetime


class SentimentResult(BaseModel):
    """Sentiment analysis result for a ticker at a point in time."""

    result_id: str = Field(..., description="UUID")
    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    timestamp: datetime

    # Sentiment scores (-1 to +1)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_label: Literal["positive", "neutral", "negative"]
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Source information
    source: SentimentSource

    # Associated news (optional, for our_model source)
    news_article_ids: list[str] = Field(default_factory=list)

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"TICKER#{self.ticker}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"{self.timestamp.isoformat()}#{self.source.source_type}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": self.pk,
            "SK": self.sk,
            "result_id": self.result_id,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "sentiment_score": str(self.sentiment_score),
            "sentiment_label": self.sentiment_label,
            "confidence": str(self.confidence),
            "source_type": self.source.source_type,
            "model_version": self.source.inference_version,  # DynamoDB attr name
            "fetched_at": self.source.fetched_at.isoformat(),
            "news_article_ids": self.news_article_ids,
            "entity_type": "SENTIMENT_RESULT",
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "SentimentResult":
        """Create SentimentResult from DynamoDB item."""
        source = SentimentSource(
            source_type=item["source_type"],
            inference_version=item.get("model_version"),  # Read from DynamoDB attr
            fetched_at=datetime.fromisoformat(item["fetched_at"]),
        )

        return cls(
            result_id=item["result_id"],
            ticker=item["ticker"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            sentiment_score=float(item["sentiment_score"]),
            sentiment_label=item["sentiment_label"],
            confidence=float(item["confidence"]),
            source=source,
            news_article_ids=item.get("news_article_ids", []),
        )


def sentiment_label_from_score(
    score: float,
) -> Literal["positive", "neutral", "negative"]:
    """Map numeric score to label.

    Args:
        score: Sentiment score between -1.0 and 1.0

    Returns:
        Sentiment label: positive, neutral, or negative
    """
    if score < -0.33:
        return "negative"
    elif score > 0.33:
        return "positive"
    return "neutral"
