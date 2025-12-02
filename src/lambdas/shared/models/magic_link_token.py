"""MagicLinkToken model with DynamoDB keys for Feature 006."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MagicLinkToken(BaseModel):
    """Magic link authentication token."""

    token_id: str = Field(..., description="UUID")
    email: EmailStr
    signature: str  # HMAC-SHA256

    created_at: datetime
    expires_at: datetime  # +1 hour
    used: bool = False

    # Link to anonymous user to merge
    anonymous_user_id: str | None = None

    # Feature 014: Atomic verification tracking (FR-004, FR-005, FR-006)
    used_at: datetime | None = Field(None, description="Exact time of verification")
    used_by_ip: str | None = Field(None, description="IP address that verified (audit)")

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"TOKEN#{self.token_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return "MAGIC_LINK"

    def is_valid(self) -> bool:
        """Check if token is still valid."""
        return not self.used and datetime.utcnow() < self.expires_at

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        # Calculate TTL for automatic DynamoDB cleanup (expires_at + 1 day buffer)
        ttl = int(self.expires_at.timestamp()) + 86400  # 1 day after expiry

        item = {
            "PK": self.pk,
            "SK": self.sk,
            "token_id": self.token_id,
            "email": self.email,
            "signature": self.signature,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "used": self.used,
            "ttl": ttl,
            "entity_type": "MAGIC_LINK_TOKEN",
        }
        if self.anonymous_user_id:
            item["anonymous_user_id"] = self.anonymous_user_id

        # Feature 014: Atomic verification tracking
        if self.used_at is not None:
            item["used_at"] = self.used_at.isoformat()
        if self.used_by_ip is not None:
            item["used_by_ip"] = self.used_by_ip

        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "MagicLinkToken":
        """Create MagicLinkToken from DynamoDB item."""
        # Parse optional datetime fields
        used_at = None
        if item.get("used_at"):
            used_at = datetime.fromisoformat(item["used_at"])

        return cls(
            token_id=item["token_id"],
            email=item["email"],
            signature=item["signature"],
            created_at=datetime.fromisoformat(item["created_at"]),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            used=item.get("used", False),
            anonymous_user_id=item.get("anonymous_user_id"),
            # Feature 014 fields
            used_at=used_at,
            used_by_ip=item.get("used_by_ip"),
        )


# Session limits
SESSION_LIMITS = {
    "anonymous_retention_days": 30,  # localStorage only
    "authenticated_retention_days": 90,
    "session_duration_days": 30,
    "magic_link_expiry_hours": 1,
}
