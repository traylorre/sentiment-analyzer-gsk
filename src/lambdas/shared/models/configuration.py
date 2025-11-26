"""Configuration model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Ticker(BaseModel):
    """Stock ticker with validation metadata."""

    symbol: str = Field(..., max_length=10, pattern=r"^[A-Z]{1,5}$")
    name: str | None = None
    exchange: Literal["NYSE", "NASDAQ", "AMEX"]
    added_at: datetime


class Configuration(BaseModel):
    """User's saved configuration (max 2 per user)."""

    config_id: str = Field(..., description="UUID")
    user_id: str
    name: str = Field(..., max_length=50, description="e.g., 'Tech Giants'")

    # Ticker settings (max 5)
    tickers: list[Ticker] = Field(..., max_length=5)

    # Timeframe (1-365 days, limited by Finnhub 1-year free tier)
    timeframe_days: int = Field(7, ge=1, le=365)

    # ATR settings
    include_extended_hours: bool = False
    atr_period: int = Field(14, ge=5, le=50)

    # Metadata
    created_at: datetime
    updated_at: datetime
    is_active: bool = True  # For soft delete

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"CONFIG#{self.config_id}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": self.pk,
            "SK": self.sk,
            "config_id": self.config_id,
            "user_id": self.user_id,
            "name": self.name,
            "tickers": [t.model_dump() for t in self.tickers],
            "timeframe_days": self.timeframe_days,
            "include_extended_hours": self.include_extended_hours,
            "atr_period": self.atr_period,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "entity_type": "CONFIGURATION",
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Configuration":
        """Create Configuration from DynamoDB item."""
        tickers = []
        for t in item.get("tickers", []):
            tickers.append(
                Ticker(
                    symbol=t["symbol"],
                    name=t.get("name"),
                    exchange=t["exchange"],
                    added_at=datetime.fromisoformat(t["added_at"]),
                )
            )

        return cls(
            config_id=item["config_id"],
            user_id=item["user_id"],
            name=item["name"],
            tickers=tickers,
            timeframe_days=item.get("timeframe_days", 7),
            include_extended_hours=item.get("include_extended_hours", False),
            atr_period=item.get("atr_period", 14),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            is_active=item.get("is_active", True),
        )


class ConfigurationCreate(BaseModel):
    """Create new configuration request."""

    name: str = Field(..., max_length=50)
    tickers: list[str] = Field(..., max_length=5)
    timeframe_days: int = Field(7, ge=1, le=365)
    include_extended_hours: bool = False


class ConfigurationUpdate(BaseModel):
    """Update existing configuration request."""

    name: str | None = Field(None, max_length=50)
    tickers: list[str] | None = Field(None, max_length=5)
    timeframe_days: int | None = Field(None, ge=1, le=365)
    include_extended_hours: bool | None = None


# Configuration limits
CONFIG_LIMITS = {
    "max_configs_per_user": 2,
    "max_tickers_per_config": 5,
    "min_timeframe_days": 1,
    "max_timeframe_days": 365,
    "name_max_length": 50,
}
