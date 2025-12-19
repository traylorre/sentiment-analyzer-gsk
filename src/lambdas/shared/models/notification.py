"""Notification model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from src.lambdas.shared.models.status_utils import (
    DISABLED,
    ENABLED,
    get_status_from_item,
)


class Notification(BaseModel):
    """Sent notification record."""

    notification_id: str = Field(..., description="UUID")
    user_id: str
    alert_id: str

    # Delivery
    email: EmailStr
    subject: str
    sent_at: datetime
    status: Literal["pending", "sent", "failed", "bounced"]

    # Tracking
    sendgrid_message_id: str | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None

    # Content
    ticker: str
    alert_type: str
    triggered_value: float
    deep_link: str  # Link back to dashboard config

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return self.sent_at.isoformat()

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "alert_id": self.alert_id,
            "email": self.email,
            "subject": self.subject,
            "sent_at": self.sent_at.isoformat(),
            "status": self.status,
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "triggered_value": str(self.triggered_value),
            "deep_link": self.deep_link,
            "entity_type": "NOTIFICATION",
        }
        if self.sendgrid_message_id:
            item["sendgrid_message_id"] = self.sendgrid_message_id
        if self.opened_at:
            item["opened_at"] = self.opened_at.isoformat()
        if self.clicked_at:
            item["clicked_at"] = self.clicked_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Notification":
        """Create Notification from DynamoDB item."""
        opened_at = None
        clicked_at = None
        if item.get("opened_at"):
            opened_at = datetime.fromisoformat(item["opened_at"])
        if item.get("clicked_at"):
            clicked_at = datetime.fromisoformat(item["clicked_at"])

        return cls(
            notification_id=item["notification_id"],
            user_id=item["user_id"],
            alert_id=item["alert_id"],
            email=item["email"],
            subject=item["subject"],
            sent_at=datetime.fromisoformat(item["sent_at"]),
            status=item["status"],
            sendgrid_message_id=item.get("sendgrid_message_id"),
            opened_at=opened_at,
            clicked_at=clicked_at,
            ticker=item["ticker"],
            alert_type=item["alert_type"],
            triggered_value=float(item["triggered_value"]),
            deep_link=item["deep_link"],
        )


class DigestSettings(BaseModel):
    """User's daily digest email preferences."""

    user_id: str
    enabled: bool = False  # Legacy, use status instead
    status: str = DISABLED  # GSI-compatible status: "enabled" or "disabled" (defaults to disabled)
    time: str = "09:00"  # 24-hour format HH:MM
    timezone: str = "America/New_York"
    include_all_configs: bool = True
    config_ids: list[str] = Field(default_factory=list)

    # Scheduling
    next_scheduled: datetime | None = None
    last_sent: datetime | None = None

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return "DIGEST_SETTINGS"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "user_id": self.user_id,
            "enabled": self.enabled,
            "status": self.status,
            "time": self.time,
            "timezone": self.timezone,
            "include_all_configs": self.include_all_configs,
            "config_ids": self.config_ids,
            "entity_type": "DIGEST_SETTINGS",
        }
        if self.next_scheduled:
            item["next_scheduled"] = self.next_scheduled.isoformat()
        if self.last_sent:
            item["last_sent"] = self.last_sent.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "DigestSettings":
        """Create DigestSettings from DynamoDB item."""
        next_scheduled = None
        last_sent = None
        if item.get("next_scheduled"):
            next_scheduled = datetime.fromisoformat(item["next_scheduled"])
        if item.get("last_sent"):
            last_sent = datetime.fromisoformat(item["last_sent"])

        # Get status with backward compatibility for boolean field
        status = get_status_from_item(item, "DIGEST_SETTINGS")
        enabled = status == ENABLED

        return cls(
            user_id=item["user_id"],
            enabled=enabled,
            status=status,
            time=item.get("time", "09:00"),
            timezone=item.get("timezone", "America/New_York"),
            include_all_configs=item.get("include_all_configs", True),
            config_ids=item.get("config_ids", []),
            next_scheduled=next_scheduled,
            last_sent=last_sent,
        )
