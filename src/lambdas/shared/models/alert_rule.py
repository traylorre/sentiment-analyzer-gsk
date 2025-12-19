"""AlertRule model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.lambdas.shared.models.status_utils import (
    ENABLED,
    get_status_from_item,
)


class AlertRule(BaseModel):
    """User-defined alert rule for a ticker."""

    alert_id: str = Field(..., description="UUID")
    user_id: str
    config_id: str  # Associated configuration
    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")

    # Alert type
    alert_type: Literal["sentiment_threshold", "volatility_threshold"]

    # Threshold settings
    threshold_value: float
    threshold_direction: Literal["above", "below"]

    # State
    is_enabled: bool = True  # Legacy, use status instead
    status: str = ENABLED  # GSI-compatible status: "enabled" or "disabled"
    last_triggered_at: datetime | None = None
    trigger_count: int = 0

    # Metadata
    created_at: datetime

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"ALERT#{self.alert_id}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "alert_id": self.alert_id,
            "user_id": self.user_id,
            "config_id": self.config_id,
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "threshold_value": str(self.threshold_value),  # DynamoDB Decimal
            "threshold_direction": self.threshold_direction,
            "is_enabled": self.is_enabled,
            "status": self.status,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at.isoformat(),
            "entity_type": "ALERT_RULE",
        }
        if self.last_triggered_at:
            item["last_triggered_at"] = self.last_triggered_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "AlertRule":
        """Create AlertRule from DynamoDB item."""
        last_triggered = None
        if item.get("last_triggered_at"):
            last_triggered = datetime.fromisoformat(item["last_triggered_at"])

        # Get status with backward compatibility for boolean field
        status = get_status_from_item(item, "ALERT_RULE")
        is_enabled = status == ENABLED

        return cls(
            alert_id=item["alert_id"],
            user_id=item["user_id"],
            config_id=item["config_id"],
            ticker=item["ticker"],
            alert_type=item["alert_type"],
            threshold_value=float(item["threshold_value"]),
            threshold_direction=item["threshold_direction"],
            is_enabled=is_enabled,
            status=status,
            last_triggered_at=last_triggered,
            trigger_count=item.get("trigger_count", 0),
            created_at=datetime.fromisoformat(item["created_at"]),
        )


class AlertRuleCreate(BaseModel):
    """Create new alert rule request."""

    config_id: str
    ticker: str
    alert_type: Literal["sentiment_threshold", "volatility_threshold"]
    threshold_value: float
    threshold_direction: Literal["above", "below"]


class AlertEvaluation(BaseModel):
    """Result of evaluating an alert rule."""

    alert_id: str
    triggered: bool
    current_value: float
    threshold_value: float
    message: str


# Alert limits
ALERT_LIMITS = {
    "max_alerts_per_config": 10,
    "max_emails_per_day": 10,
    "sentiment_threshold_range": (-1.0, 1.0),
    "volatility_threshold_range": (0.0, 100.0),  # Percent
}
