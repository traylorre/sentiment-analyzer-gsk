"""User model with DynamoDB keys for Feature 006.

Feature 1162: Added ProviderMetadata class and federation fields.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

# Type aliases for federation
ProviderType = Literal["email", "google", "github"]
RoleType = Literal["anonymous", "free", "paid", "operator"]
VerificationType = Literal["none", "pending", "verified"]


class ProviderMetadata(BaseModel):
    """Per-provider OAuth data for federated authentication.

    Feature 1162: Stores provider-specific metadata when a user links
    an authentication provider (email, Google, GitHub).
    """

    sub: str | None = Field(
        None, description="OAuth subject claim (provider's user ID)"
    )
    email: str | None = Field(None, description="Email address from this provider")
    avatar: str | None = Field(None, description="Avatar URL from provider")
    linked_at: datetime = Field(..., description="When provider was linked to account")
    verified_at: datetime | None = Field(
        None, description="For email provider: when email was verified"
    )


class User(BaseModel):
    """Dashboard user - anonymous or authenticated."""

    # Primary identifiers
    user_id: str = Field(..., description="UUID, generated on first visit")
    email: EmailStr | None = Field(None, description="Set after auth")
    cognito_sub: str | None = Field(None, description="Cognito user pool sub")

    # Authentication state (DEPRECATED - use role + linked_providers instead)
    auth_type: Literal["anonymous", "email", "google", "github"] = Field(
        default="anonymous",
        description="DEPRECATED: Use role and linked_providers instead.",
    )
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

    # Feature 1186: Revocation ID for atomic token rotation (A14)
    revocation_id: int = Field(
        default=0,
        description="Increments on password change or force revocation. "
        "Tokens with stale rev claim are rejected.",
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
        default=False,
        description="DEPRECATED: Use role == 'operator' instead. Administrative flag.",
    )

    # Feature 1162: Federation fields for multi-provider auth
    role: RoleType = Field(
        default="anonymous", description="User authorization tier (replaces auth_type)"
    )
    verification: VerificationType = Field(
        default="none", description="Email verification state"
    )
    pending_email: str | None = Field(None, description="Email awaiting verification")
    primary_email: str | None = Field(
        None,
        description="Verified canonical email",
        serialization_alias="primary_email",
    )
    linked_providers: list[ProviderType] = Field(
        default_factory=list, description="List of linked auth providers"
    )
    provider_metadata: dict[str, ProviderMetadata] = Field(
        default_factory=dict, description="Metadata per provider"
    )
    last_provider_used: ProviderType | None = Field(
        None, description="Most recent auth provider (for avatar selection)"
    )
    role_assigned_at: datetime | None = Field(
        None, description="When role was last changed"
    )
    role_assigned_by: str | None = Field(
        None, description="Who changed the role (stripe_webhook or admin:{user_id})"
    )

    @model_validator(mode="after")
    def validate_role_verification_state(self) -> "User":
        """Enforce role-verification state machine invariants.

        Feature 1163: Validates cross-field constraints per spec-v2.md matrix:
        - anonymous:none     → Valid
        - anonymous:pending  → Valid
        - anonymous:verified → Auto-upgrade to free:verified
        - free/paid/operator → Must have verification="verified"
        """
        # Rule 1 & 2: anonymous + verified → auto-upgrade to free
        if self.role == "anonymous" and self.verification == "verified":
            object.__setattr__(self, "role", "free")

        # Rule 3: non-anonymous requires verified
        if self.role != "anonymous" and self.verification != "verified":
            raise ValueError(
                f"Invalid state: {self.role} role requires verified status, "
                f"got verification={self.verification}"
            )

        return self

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

        # Feature 1186: Revocation ID for atomic token rotation (A14)
        item["revocation_id"] = self.revocation_id

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

        # Feature 1162: Federation fields
        item["role"] = self.role
        item["verification"] = self.verification
        if self.pending_email is not None:
            item["pending_email"] = self.pending_email
        if self.primary_email is not None:
            item["primary_email"] = self.primary_email
        item["linked_providers"] = self.linked_providers
        # Serialize provider_metadata as dict of dicts
        item["provider_metadata"] = {
            k: v.model_dump() for k, v in self.provider_metadata.items()
        }
        if self.last_provider_used is not None:
            item["last_provider_used"] = self.last_provider_used
        if self.role_assigned_at is not None:
            item["role_assigned_at"] = self.role_assigned_at.isoformat()
        if self.role_assigned_by is not None:
            item["role_assigned_by"] = self.role_assigned_by

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

        # Feature 1162: Parse federation datetime fields
        role_assigned_at = None
        if item.get("role_assigned_at"):
            role_assigned_at = datetime.fromisoformat(item["role_assigned_at"])

        # Feature 1162: Parse provider_metadata from dict of dicts
        provider_metadata_raw = item.get("provider_metadata", {})
        provider_metadata = {}
        for provider_key, metadata_dict in provider_metadata_raw.items():
            # Convert linked_at/verified_at from ISO strings to datetime
            if "linked_at" in metadata_dict and isinstance(
                metadata_dict["linked_at"], str
            ):
                metadata_dict["linked_at"] = datetime.fromisoformat(
                    metadata_dict["linked_at"]
                )
            if metadata_dict.get("verified_at") and isinstance(
                metadata_dict["verified_at"], str
            ):
                metadata_dict["verified_at"] = datetime.fromisoformat(
                    metadata_dict["verified_at"]
                )
            provider_metadata[provider_key] = ProviderMetadata(**metadata_dict)

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
            # Feature 1186: Revocation ID for atomic token rotation (A14)
            revocation_id=item.get("revocation_id", 0),
            merged_to=item.get("merged_to"),
            merged_at=merged_at,
            # Feature 1151: RBAC fields with backward-compatible defaults
            subscription_active=item.get("subscription_active", False),
            subscription_expires_at=subscription_expires_at,
            is_operator=item.get("is_operator", False),
            # Feature 1162: Federation fields with backward-compatible defaults
            role=item.get("role", "anonymous"),
            verification=item.get("verification", "none"),
            pending_email=item.get("pending_email"),
            primary_email=item.get("primary_email"),
            linked_providers=item.get("linked_providers", []),
            provider_metadata=provider_metadata,
            last_provider_used=item.get("last_provider_used"),
            role_assigned_at=role_assigned_at,
            role_assigned_by=item.get("role_assigned_by"),
        )


class UserCreate(BaseModel):
    """Anonymous user creation request."""

    timezone: str | None = "America/New_York"


class UserUpgrade(BaseModel):
    """Upgrade anonymous to authenticated user."""

    email: EmailStr | None = None
    cognito_sub: str | None = None
    auth_type: Literal["email", "google", "github"]
