"""OHLC response models for Price-Sentiment Overlay feature."""

from datetime import date as date_type
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.lambdas.shared.models.volatility_metric import OHLCCandle


class TimeRange(str, Enum):
    """Predefined time ranges for chart display."""

    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    ONE_YEAR = "1Y"


# Mapping of TimeRange to days
TIME_RANGE_DAYS: dict[TimeRange, int] = {
    TimeRange.ONE_WEEK: 7,
    TimeRange.ONE_MONTH: 30,
    TimeRange.THREE_MONTHS: 90,
    TimeRange.SIX_MONTHS: 180,
    TimeRange.ONE_YEAR: 365,
}


class PriceCandle(BaseModel):
    """Single day's OHLC price data for API response.

    Extends OHLCCandle with date formatting for JSON serialization.
    """

    date: date_type = Field(..., description="Trading day date")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int | None = Field(None, ge=0, description="Trading volume")

    @classmethod
    def from_ohlc_candle(cls, candle: OHLCCandle) -> "PriceCandle":
        """Convert from internal OHLCCandle model."""
        return cls(
            date=candle.date.date()
            if isinstance(candle.date, datetime)
            else candle.date,  # type: ignore[arg-type]
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
        )


class OHLCResponse(BaseModel):
    """Response model for OHLC price data endpoint."""

    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$", description="Stock symbol")
    candles: list[PriceCandle] = Field(
        ..., description="Array of OHLC candles, oldest first"
    )
    time_range: str = Field(
        ..., description="Time range used (1W, 1M, 3M, 6M, 1Y, or custom)"
    )
    start_date: date_type = Field(..., description="First candle date")
    end_date: date_type = Field(..., description="Last candle date")
    count: int = Field(..., ge=0, description="Number of candles returned")
    source: Literal["tiingo", "finnhub"] = Field(..., description="Data source used")
    cache_expires_at: datetime = Field(
        ..., description="When cached data expires (next market open)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "AAPL",
                "candles": [
                    {
                        "date": "2024-11-29",
                        "open": 237.45,
                        "high": 239.12,
                        "low": 236.80,
                        "close": 238.67,
                        "volume": 45678900,
                    }
                ],
                "time_range": "1M",
                "start_date": "2024-11-01",
                "end_date": "2024-11-29",
                "count": 21,
                "source": "tiingo",
                "cache_expires_at": "2024-12-02T14:30:00Z",
            }
        }
    )
