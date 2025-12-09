"""NewsItem model for market data ingestion.

Central entity for collected news articles with embedded sentiment.
Schema defined in specs/072-market-data-ingestion/contracts/news-item.schema.json
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SentimentScore(BaseModel):
    """Embedded sentiment analysis result.

    Confidence score enables downstream filtering by data quality.
    """

    score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score (-1 to +1)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in score (0 to 1)"
    )
    label: Literal["positive", "neutral", "negative"] = Field(
        ..., description="Derived sentiment label"
    )

    @classmethod
    def from_score(cls, score: float, confidence: float) -> "SentimentScore":
        """Create SentimentScore with auto-derived label.

        Args:
            score: Sentiment score between -1.0 and 1.0
            confidence: Confidence score between 0.0 and 1.0

        Returns:
            SentimentScore with derived label
        """
        if score <= -0.33:
            label: Literal["positive", "neutral", "negative"] = "negative"
        elif score >= 0.33:
            label = "positive"
        else:
            label = "neutral"
        return cls(score=score, confidence=confidence, label=label)


class NewsItem(BaseModel):
    """Market news article with embedded sentiment.

    DynamoDB schema:
        PK: NEWS#{dedup_key}
        SK: {source}#{ingested_at_iso}
        entity_type: NEWS_ITEM
    """

    dedup_key: str = Field(
        ..., min_length=32, max_length=32, description="SHA256[:32] deduplication key"
    )
    source: Literal["tiingo", "finnhub"] = Field(
        ..., description="Data source identifier"
    )
    headline: str = Field(
        ..., min_length=1, max_length=500, description="Article title"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Article summary/body"
    )
    url: str | None = Field(default=None, description="Link to full article")
    published_at: datetime = Field(..., description="Original publication timestamp")
    ingested_at: datetime = Field(..., description="When we collected this item")
    tickers: list[str] = Field(
        default_factory=list, description="Related stock symbols"
    )
    tags: list[str] = Field(default_factory=list, description="Category tags")
    source_name: str | None = Field(
        default=None, description="Publisher name (e.g., Reuters)"
    )
    sentiment: SentimentScore | None = Field(
        default=None, description="Embedded sentiment analysis"
    )

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"NEWS#{self.dedup_key}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"{self.source}#{self.ingested_at.isoformat()}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item: dict = {
            "PK": self.pk,
            "SK": self.sk,
            "dedup_key": self.dedup_key,
            "source": self.source,
            "headline": self.headline,
            "published_at": self.published_at.isoformat(),
            "ingested_at": self.ingested_at.isoformat(),
            "tickers": self.tickers,
            "tags": self.tags,
            "entity_type": "NEWS_ITEM",
        }
        if self.description:
            item["description"] = self.description
        if self.url:
            item["url"] = self.url
        if self.source_name:
            item["source_name"] = self.source_name
        if self.sentiment:
            item["sentiment_score"] = str(self.sentiment.score)
            item["sentiment_confidence"] = str(self.sentiment.confidence)
            item["sentiment_label"] = self.sentiment.label
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "NewsItem":
        """Create NewsItem from DynamoDB item."""
        sentiment = None
        if "sentiment_score" in item:
            sentiment = SentimentScore(
                score=float(item["sentiment_score"]),
                confidence=float(item["sentiment_confidence"]),
                label=item["sentiment_label"],
            )

        return cls(
            dedup_key=item["dedup_key"],
            source=item["source"],
            headline=item["headline"],
            description=item.get("description"),
            url=item.get("url"),
            published_at=datetime.fromisoformat(item["published_at"]),
            ingested_at=datetime.fromisoformat(item["ingested_at"]),
            tickers=item.get("tickers", []),
            tags=item.get("tags", []),
            source_name=item.get("source_name"),
            sentiment=sentiment,
        )
