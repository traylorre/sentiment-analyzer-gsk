"""Minimal response models for frontend - prevents data leakage.

Security Notes:
    - These models define ONLY what the frontend needs
    - Never expose internal IDs (cognito_sub, internal counters)
    - Mask PII (emails show j***@example.com)
    - Use relative times (expires_in_seconds) not absolute timestamps
    - refresh_token is NEVER in response body (HttpOnly cookie only)

For On-Call Engineers:
    If frontend reports missing fields, verify they're actually needed.
    Adding fields here requires security review.
"""

from datetime import UTC, datetime

from pydantic import BaseModel


def mask_email(email: str | None) -> str | None:
    """Mask email for frontend display: john@example.com -> j***@example.com"""
    if not email:
        return None
    try:
        local, domain = email.split("@")
        if len(local) <= 1:
            return f"*@{domain}"
        return f"{local[0]}***@{domain}"
    except ValueError:
        return "***"


def seconds_until(dt: datetime | None) -> int | None:
    """Convert datetime to seconds from now."""
    if not dt:
        return None
    now = datetime.now(UTC)
    # Handle naive datetimes
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = dt - now
    return max(0, int(delta.total_seconds()))


# =============================================================================
# Auth Response Models - Minimal frontend exposure
# =============================================================================


class UserMeResponse(BaseModel):
    """Minimal /api/v2/auth/me response - only what frontend needs."""

    auth_type: str  # anonymous, email, google, github
    email_masked: str | None = None  # j***@example.com
    configs_count: int
    max_configs: int = 2
    session_expires_in_seconds: int | None = None


class SessionValidResponse(BaseModel):
    """Minimal session validation response."""

    valid: bool = True
    auth_type: str
    expires_in_seconds: int


class SessionInvalidResponse(BaseModel):
    """Session invalid response."""

    valid: bool = False
    error: str
    message: str


class AuthTokensResponse(BaseModel):
    """Auth tokens response - NO refresh_token (that's HttpOnly cookie)."""

    id_token: str
    access_token: str
    expires_in: int = 3600
    # NOTE: refresh_token is set as HttpOnly cookie, never in body


class MagicLinkVerifiedResponse(BaseModel):
    """Magic link verified - minimal response."""

    status: str = "verified"
    auth_type: str
    email_masked: str | None = None
    tokens: AuthTokensResponse | None = None
    merged_anonymous_data: bool = False


class OAuthSuccessResponse(BaseModel):
    """OAuth success - minimal response."""

    status: str = "authenticated"
    auth_type: str
    email_masked: str | None = None
    tokens: AuthTokensResponse | None = None
    merged_anonymous_data: bool = False
    is_new_user: bool = False


class OAuthConflictResponse(BaseModel):
    """OAuth conflict - asks user to link accounts."""

    status: str = "conflict"
    conflict: bool = True
    existing_provider: str
    email_masked: str  # Show masked email they're trying to use
    message: str


class SessionInfoMinimalResponse(BaseModel):
    """Minimal session info for frontend."""

    auth_type: str
    email_masked: str | None = None
    expires_in_seconds: int
    linked_providers: list[str]


# =============================================================================
# Notification Response Models - Minimal frontend exposure
# =============================================================================


class NotificationMinimalResponse(BaseModel):
    """Notification in list view - no email, no tracking details."""

    notification_id: str
    alert_id: str
    ticker: str
    alert_type: str
    triggered_value: float
    subject: str
    sent_at: str  # ISO format is OK for display
    status: str  # pending, sent, failed
    deep_link: str


class NotificationDetailResponse(BaseModel):
    """Single notification detail - includes body preview."""

    notification_id: str
    alert_id: str
    ticker: str
    alert_type: str
    triggered_value: float
    threshold_value: float | None = None
    threshold_direction: str | None = None
    subject: str
    body_preview: str | None = None
    sent_at: str
    status: str
    deep_link: str
    # No email field - not needed for frontend
    # No tracking info - that's analytics, not for user display


class NotificationListMinimalResponse(BaseModel):
    """Notification list - paginated."""

    notifications: list[NotificationMinimalResponse]
    total: int
    limit: int
    offset: int


class NotificationPrefsMinimalResponse(BaseModel):
    """Notification preferences - no internal flags."""

    email_notifications_enabled: bool
    daily_digest_enabled: bool
    digest_time: str
    timezone: str
    # No email field - frontend knows user's email from /me
    # No email_verified - handle in separate flow


# =============================================================================
# Configuration Response Models
# =============================================================================


class ConfigMinimalResponse(BaseModel):
    """Configuration for list view."""

    config_id: str
    name: str
    tickers: list[str]
    created_at: str
    # No internal fields like user_id


class ConfigDetailResponse(BaseModel):
    """Configuration detail view."""

    config_id: str
    name: str
    tickers: list[dict]  # {symbol, added_at}
    timeframe: str
    extended_hours: bool
    created_at: str
    updated_at: str | None = None
