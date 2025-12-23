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


class OHLCResolution(str, Enum):
    """Candlestick time resolution for OHLC data.

    Maps to Finnhub API resolution parameter values.
    Each resolution has an associated max_days limit to prevent
    excessive data retrieval.
    """

    ONE_MINUTE = "1"
    FIVE_MINUTES = "5"
    FIFTEEN_MINUTES = "15"
    THIRTY_MINUTES = "30"
    ONE_HOUR = "60"
    DAILY = "D"

    @property
    def max_days(self) -> int:
        """Maximum time range in days for this resolution.

        Limits are based on Finnhub data availability and
        practical chart display considerations.
        """
        return RESOLUTION_MAX_DAYS[self]


# Mapping of OHLCResolution to maximum allowed days
RESOLUTION_MAX_DAYS: dict[OHLCResolution, int] = {
    OHLCResolution.ONE_MINUTE: 7,
    OHLCResolution.FIVE_MINUTES: 30,
    OHLCResolution.FIFTEEN_MINUTES: 90,
    OHLCResolution.THIRTY_MINUTES: 90,
    OHLCResolution.ONE_HOUR: 180,
    OHLCResolution.DAILY: 365,
}


class PriceCandle(BaseModel):
    """OHLC price data for API response.

    Supports both daily (date) and intraday (datetime) candles.
    Extends OHLCCandle with date formatting for JSON serialization.
    """

    date: date_type | datetime = Field(
        ..., description="Candle timestamp (date for daily, datetime for intraday)"
    )
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int | None = Field(None, ge=0, description="Trading volume")

    @classmethod
    def from_ohlc_candle(
        cls, candle: OHLCCandle, resolution: "OHLCResolution | None" = None
    ) -> "PriceCandle":
        """Convert from internal OHLCCandle model.

        Args:
            candle: The source OHLCCandle to convert
            resolution: If provided and not DAILY, preserves full datetime

        Returns:
            PriceCandle with appropriate date/datetime based on resolution
        """
        # For intraday resolutions, preserve full datetime
        if resolution is not None and resolution != OHLCResolution.DAILY:
            candle_date: date_type | datetime = (
                candle.date if isinstance(candle.date, datetime) else candle.date
            )
        else:
            # For daily, use just the date part
            candle_date = (
                candle.date.date() if isinstance(candle.date, datetime) else candle.date
            )

        return cls(
            date=candle_date,
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
    resolution: str = Field(
        default="D", description="Resolution of returned candles (1, 5, 15, 30, 60, D)"
    )
    resolution_fallback: bool = Field(
        default=False,
        description="True if requested resolution was unavailable and fell back to daily",
    )
    fallback_message: str | None = Field(
        default=None, description="Explanation if fallback occurred"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "AAPL",
                "candles": [
                    {
                        "date": "2024-11-29T14:30:00Z",
                        "open": 237.45,
                        "high": 239.12,
                        "low": 236.80,
                        "close": 238.67,
                        "volume": 45678900,
                    }
                ],
                "time_range": "1W",
                "start_date": "2024-11-22",
                "end_date": "2024-11-29",
                "count": 288,
                "source": "finnhub",
                "cache_expires_at": "2024-12-02T14:30:00Z",
                "resolution": "5",
                "resolution_fallback": False,
                "fallback_message": None,
            }
        }
    )
