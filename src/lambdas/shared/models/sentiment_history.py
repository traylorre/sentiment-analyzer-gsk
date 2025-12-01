"""Sentiment history models for Price-Sentiment Overlay feature."""

from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SentimentSourceType = Literal["tiingo", "finnhub", "our_model", "aggregated"]


class SentimentPoint(BaseModel):
    """Sentiment score for a specific date and source."""

    date: date_type = Field(..., description="Date of sentiment measurement")
    score: float = Field(
        ..., ge=-1.0, le=1.0, description="Sentiment score (-1.0 to 1.0)"
    )
    source: SentimentSourceType = Field(..., description="Sentiment source")
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Model confidence (if applicable)"
    )
    label: Literal["positive", "neutral", "negative"] | None = Field(
        None, description="Sentiment classification"
    )


class SentimentHistoryResponse(BaseModel):
    """Response model for historical sentiment data endpoint."""

    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$", description="Stock symbol")
    source: SentimentSourceType = Field(..., description="Selected sentiment source")
    history: list[SentimentPoint] = Field(
        ..., description="Array of sentiment points, oldest first"
    )
    start_date: date_type = Field(..., description="First data point date")
    end_date: date_type = Field(..., description="Last data point date")
    count: int = Field(..., ge=0, description="Number of points returned")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "AAPL",
                "source": "aggregated",
                "history": [
                    {
                        "date": "2024-11-29",
                        "score": 0.65,
                        "source": "aggregated",
                        "confidence": 0.85,
                        "label": "positive",
                    }
                ],
                "start_date": "2024-11-01",
                "end_date": "2024-11-29",
                "count": 29,
            }
        }
    )
