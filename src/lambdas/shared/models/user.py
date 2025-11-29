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
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "User":
        """Create User from DynamoDB item."""
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
        )


class UserCreate(BaseModel):
    """Anonymous user creation request."""

    timezone: str | None = "America/New_York"


class UserUpgrade(BaseModel):
    """Upgrade anonymous to authenticated user."""

    email: EmailStr | None = None
    cognito_sub: str | None = None
    auth_type: Literal["email", "google", "github"]
