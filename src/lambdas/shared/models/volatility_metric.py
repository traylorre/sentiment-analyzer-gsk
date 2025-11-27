"""VolatilityMetric model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OHLCCandle(BaseModel):
    """Single OHLC candle."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class VolatilityMetric(BaseModel):
    """ATR volatility calculation for a ticker."""

    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    timestamp: datetime
    period: int = Field(14, description="ATR period in days")

    # ATR values
    atr_value: float
    atr_percent: float  # ATR as % of current price
    previous_atr: float | None = None

    # Trend indicator
    trend: Literal["increasing", "decreasing", "stable"]

    # Source candles used
    candle_count: int
    includes_extended_hours: bool

    @property
    def trend_arrow(self) -> str:
        """Visual trend indicator."""
        return {"increasing": "↑", "decreasing": "↓", "stable": "→"}[self.trend]

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"TICKER#{self.ticker}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"ATR#{self.timestamp.isoformat()}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "period": self.period,
            "atr_value": str(self.atr_value),
            "atr_percent": str(self.atr_percent),
            "trend": self.trend,
            "candle_count": self.candle_count,
            "includes_extended_hours": self.includes_extended_hours,
            "entity_type": "VOLATILITY_METRIC",
        }
        if self.previous_atr is not None:
            item["previous_atr"] = str(self.previous_atr)
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "VolatilityMetric":
        """Create VolatilityMetric from DynamoDB item."""
        previous_atr = None
        if item.get("previous_atr"):
            previous_atr = float(item["previous_atr"])

        return cls(
            ticker=item["ticker"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            period=item.get("period", 14),
            atr_value=float(item["atr_value"]),
            atr_percent=float(item["atr_percent"]),
            previous_atr=previous_atr,
            trend=item["trend"],
            candle_count=item["candle_count"],
            includes_extended_hours=item.get("includes_extended_hours", False),
        )
