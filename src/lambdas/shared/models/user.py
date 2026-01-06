"""User model with DynamoDB keys for Feature 006."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Dashboard user - anonymous or authenticated."""

    # Primary identifiers
    user_id: str = Field(..., description="UUID, generated on first visit")
    email: EmailStr | None = Field(None, description="Set after auth")
    cognito_sub: str | None = Field(None, description="Cognito user pool sub")

    # Authentication state
    auth_type: Literal["anonymous", "email", "google", "github"] = "anonymous"
    created_at: datetime
    last_active_at: datetime
    session_expires_at: datetime  # 30 days, refreshed on activity

    # Preferences
    timezone: str = "America/New_York"
    email_notifications_enabled: bool = True
    daily_email_count: int = 0  # Reset daily, max 10

    # Feature 014: Entity type for GSI (required for email-index GSI sort key)
    entity_type: str = Field(default="USER", description="Entity type for GSI queries")

    # Feature 014: Session revocation fields (FR-016, FR-017)
    revoked: bool = Field(
        default=False, description="Whether session has been revoked server-side"
    )
    revoked_at: datetime | None = Field(None, description="When session was revoked")
    revoked_reason: str | None = Field(
        None, description="Reason for revocation (incident ID, admin action)"
    )

    # Feature 014: Merge tracking fields (FR-013, FR-014, FR-015)
    merged_to: str | None = Field(
        None, description="Target user ID if this account was merged"
    )
    merged_at: datetime | None = Field(None, description="When merge occurred")

    # Feature 1151: RBAC fields for get_roles_for_user()
    subscription_active: bool = Field(
        default=False, description="Whether user has active paid subscription"
    )
    subscription_expires_at: datetime | None = Field(
        None,
        description="When subscription expires (None = no expiry or not subscribed)",
    )
    is_operator: bool = Field(
        default=False, description="Administrative flag for operator access"
    )

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return "PROFILE"

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format.

        Note: email and cognito_sub are excluded when None because they are
        GSI key attributes, and DynamoDB GSI keys cannot be NULL type.
        """
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "user_id": self.user_id,
            "auth_type": self.auth_type,
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat(),
            "session_expires_at": self.session_expires_at.isoformat(),
            "timezone": self.timezone,
            "email_notifications_enabled": self.email_notifications_enabled,
            "daily_email_count": self.daily_email_count,
            "entity_type": "USER",
        }
        # Only include GSI key attributes if they have values
        # DynamoDB GSI keys cannot be NULL type
        if self.email is not None:
            item["email"] = self.email
        if self.cognito_sub is not None:
            item["cognito_sub"] = self.cognito_sub

        # Feature 014: Session revocation fields
        item["revoked"] = self.revoked
        if self.revoked_at is not None:
            item["revoked_at"] = self.revoked_at.isoformat()
        if self.revoked_reason is not None:
            item["revoked_reason"] = self.revoked_reason

        # Feature 014: Merge tracking fields
        if self.merged_to is not None:
            item["merged_to"] = self.merged_to
        if self.merged_at is not None:
            item["merged_at"] = self.merged_at.isoformat()

        # Feature 1151: RBAC fields
        item["subscription_active"] = self.subscription_active
        item["is_operator"] = self.is_operator
        if self.subscription_expires_at is not None:
            item["subscription_expires_at"] = self.subscription_expires_at.isoformat()

        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "User":
        """Create User from DynamoDB item."""
        # Parse optional datetime fields
        revoked_at = None
        if item.get("revoked_at"):
            revoked_at = datetime.fromisoformat(item["revoked_at"])

        merged_at = None
        if item.get("merged_at"):
            merged_at = datetime.fromisoformat(item["merged_at"])

        # Feature 1151: Parse subscription_expires_at
        subscription_expires_at = None
        if item.get("subscription_expires_at"):
            subscription_expires_at = datetime.fromisoformat(
                item["subscription_expires_at"]
            )

        return cls(
            user_id=item["user_id"],
            email=item.get("email"),
            cognito_sub=item.get("cognito_sub"),
            auth_type=item.get("auth_type", "anonymous"),
            created_at=datetime.fromisoformat(item["created_at"]),
            last_active_at=datetime.fromisoformat(item["last_active_at"]),
            session_expires_at=datetime.fromisoformat(item["session_expires_at"]),
            timezone=item.get("timezone", "America/New_York"),
            email_notifications_enabled=item.get("email_notifications_enabled", True),
            daily_email_count=item.get("daily_email_count", 0),
            entity_type=item.get("entity_type", "USER"),
            # Feature 014 fields
            revoked=item.get("revoked", False),
            revoked_at=revoked_at,
            revoked_reason=item.get("revoked_reason"),
            merged_to=item.get("merged_to"),
            merged_at=merged_at,
            # Feature 1151: RBAC fields with backward-compatible defaults
            subscription_active=item.get("subscription_active", False),
            subscription_expires_at=subscription_expires_at,
            is_operator=item.get("is_operator", False),
        )


class UserCreate(BaseModel):
    """Anonymous user creation request."""

    timezone: str | None = "America/New_York"


class UserUpgrade(BaseModel):
    """Upgrade anonymous to authenticated user."""

    email: EmailStr | None = None
    cognito_sub: str | None = None
    auth_type: Literal["email", "google", "github"]
