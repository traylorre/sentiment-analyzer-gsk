"""WebhookEvent model for Stripe webhook idempotency tracking.

Feature: 1191 - Mid-Session Tier Upgrade
"""

from datetime import datetime

from pydantic import BaseModel, Field


class WebhookEvent(BaseModel):
    """Tracks processed Stripe webhook events for idempotency.

    Uses single-table design pattern with PK/SK: WEBHOOK#{event_id} / WEBHOOK#{event_id}
    """

    event_id: str = Field(..., description="Stripe event.id for idempotency")
    event_type: str = Field(..., description="e.g., customer.subscription.created")
    user_id: str = Field(..., description="Associated user ID")
    subscription_id: str | None = Field(None, description="Stripe subscription ID")
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    ttl: int | None = Field(None, description="DynamoDB TTL for auto-deletion")

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"WEBHOOK#{self.event_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"WEBHOOK#{self.event_id}"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "processed_at": self.processed_at.isoformat(),
            "entity_type": "webhook_event",
        }
        if self.subscription_id:
            item["subscription_id"] = self.subscription_id
        if self.ttl:
            item["ttl"] = self.ttl
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "WebhookEvent":
        """Parse DynamoDB item to WebhookEvent model."""
        return cls(
            event_id=item["event_id"],
            event_type=item["event_type"],
            user_id=item["user_id"],
            subscription_id=item.get("subscription_id"),
            processed_at=datetime.fromisoformat(item["processed_at"]),
            ttl=item.get("ttl"),
        )
