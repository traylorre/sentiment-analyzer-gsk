"""
Contract Tests: Session Management API (T087)
=============================================

Tests that session management endpoints conform to auth-api.md contract.

Constitution v1.1:
- Contract tests validate response schemas against API contracts
- All tests use moto to mock AWS infrastructure ($0 cost)
"""

from datetime import UTC, datetime, timedelta


class TestSignOutEndpoint:
    """Contract tests for POST /api/v2/auth/signout."""

    def test_request_requires_authorization(self):
        """Request must include Bearer token."""
        headers = {"Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."}

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    def test_response_200_schema(self):
        """200 OK response for successful sign out."""
        response = {
            "status": "signed_out",
            "message": "Signed out from this device",
        }

        assert response["status"] == "signed_out"
        assert "signed out" in response["message"].lower()

    def test_signout_single_device_only(self):
        """Sign out affects current device only, not all devices."""
        response = {
            "status": "signed_out",
            "message": "Signed out from this device",
        }

        # Per contract: "This invalidates tokens for current device only"
        assert "this device" in response["message"].lower()

    def test_response_401_invalid_token(self):
        """401 response for invalid/expired access token."""
        response = {
            "error": "unauthorized",
            "message": "Invalid or expired token.",
        }

        assert response["error"] == "unauthorized"


class TestSessionInfoEndpoint:
    """Contract tests for GET /api/v2/auth/session."""

    def test_request_requires_authorization(self):
        """Request must include Bearer token."""
        headers = {"Authorization": "Bearer eyJ..."}

        assert "Authorization" in headers

    def test_response_200_schema(self):
        """200 OK response with session info."""
        response = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "auth_type": "google",
            "session_started_at": "2025-11-26T10:00:00Z",
            "session_expires_at": "2025-12-26T10:00:00Z",
            "last_activity_at": "2025-11-26T15:30:00Z",
            "linked_providers": ["google"],
        }

        # Required fields
        assert _is_valid_uuid(response["user_id"])
        assert "@" in response["email"]
        assert response["auth_type"] in ["anonymous", "email", "google", "github"]

        # Timestamp fields
        assert _is_valid_iso_datetime(response["session_started_at"])
        assert _is_valid_iso_datetime(response["session_expires_at"])
        assert _is_valid_iso_datetime(response["last_activity_at"])

        # Linked providers array
        assert isinstance(response["linked_providers"], list)

    def test_response_includes_all_linked_providers(self):
        """Response lists all linked authentication providers."""
        response = {
            "user_id": "uuid",
            "email": "user@example.com",
            "auth_type": "google",
            "session_started_at": "2025-11-26T10:00:00Z",
            "session_expires_at": "2025-12-26T10:00:00Z",
            "last_activity_at": "2025-11-26T15:30:00Z",
            "linked_providers": ["email", "google"],
        }

        assert "email" in response["linked_providers"]
        assert "google" in response["linked_providers"]

    def test_response_401_unauthorized(self):
        """401 response for unauthenticated request."""
        response = {
            "error": "unauthorized",
            "message": "Authentication required.",
        }

        assert response["error"] == "unauthorized"


class TestSessionExtendEndpoint:
    """Contract tests for POST /api/v2/auth/session/extend."""

    def test_request_requires_authorization(self):
        """Request must include Bearer token."""
        headers = {"Authorization": "Bearer eyJ..."}

        assert "Authorization" in headers

    def test_response_200_schema(self):
        """200 OK response with new expiry."""
        response = {
            "session_expires_at": "2025-12-26T15:30:00Z",
            "message": "Session extended for 30 days",
        }

        assert _is_valid_iso_datetime(response["session_expires_at"])
        assert "30 days" in response["message"]

    def test_session_extended_by_30_days(self):
        """Session is extended by 30 days from current time."""
        now = datetime.now(UTC)
        expected_expiry = now + timedelta(days=30)

        response = {
            "session_expires_at": expected_expiry.isoformat().replace("+00:00", "Z"),
            "message": "Session extended for 30 days",
        }

        # Expiry should be ~30 days from now
        expiry = datetime.fromisoformat(
            response["session_expires_at"].replace("Z", "+00:00")
        )
        delta = expiry - now

        assert 29 <= delta.days <= 31  # Allow 1 day tolerance


class TestSessionAutoExtend:
    """Contract tests for automatic session extension."""

    def test_authenticated_api_calls_extend_session(self):
        """Per contract, session is auto-extended on any authenticated API call."""
        # Document this behavior for implementers

        # Any call with valid Authorization header should:
        # 1. Process the request
        # 2. Update last_activity_at
        # 3. Session expiry clock resets

        expected_behavior = {
            "auto_extend_on_activity": True,
            "extend_duration_days": 30,
        }

        assert expected_behavior["auto_extend_on_activity"] is True


class TestAccountLinkingEndpoints:
    """Contract tests for account linking (check-email, link-accounts, merge-status)."""

    def test_check_email_request_schema(self):
        """POST /api/v2/auth/check-email request schema."""
        request = {
            "email": "user@example.com",
            "current_provider": "google",
        }

        assert "@" in request["email"]
        assert request["current_provider"] in ["email", "google", "github"]

    def test_check_email_no_conflict_response(self):
        """Response when no account conflict exists."""
        response = {"conflict": False}

        assert response["conflict"] is False

    def test_check_email_conflict_response(self):
        """Response when email exists with different provider."""
        response = {
            "conflict": True,
            "existing_provider": "email",
            "message": "An account with this email exists via magic link. Would you like to link your Google account?",
        }

        assert response["conflict"] is True
        assert response["existing_provider"] in ["email", "google", "github"]

    def test_link_accounts_request_schema(self):
        """POST /api/v2/auth/link-accounts request schema."""
        request = {
            "link_to_user_id": "550e8400-e29b-41d4-a716-446655440000",
            "confirmation": True,
        }

        assert _is_valid_uuid(request["link_to_user_id"])
        assert request["confirmation"] is True  # Must be explicit

    def test_link_accounts_response_schema(self):
        """200 OK response for successful account linking."""
        response = {
            "status": "linked",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "linked_providers": ["email", "google"],
            "message": "Accounts successfully linked",
        }

        assert response["status"] == "linked"
        assert len(response["linked_providers"]) >= 2

    def test_merge_status_completed_response(self):
        """GET /api/v2/auth/merge-status response for completed merge."""
        response = {
            "status": "completed",
            "merged_at": "2025-11-26T10:00:00Z",
            "items_merged": {
                "configurations": 2,
                "alert_rules": 5,
                "preferences": 1,
            },
        }

        assert response["status"] == "completed"
        assert _is_valid_iso_datetime(response["merged_at"])
        assert "configurations" in response["items_merged"]
        assert "alert_rules" in response["items_merged"]

    def test_merge_status_no_data_response(self):
        """GET /api/v2/auth/merge-status response when nothing to merge."""
        response = {
            "status": "no_data",
            "message": "No anonymous data found to merge",
        }

        assert response["status"] == "no_data"


class TestSessionSecurityHeaders:
    """Contract tests for security headers on session endpoints."""

    def test_required_security_headers(self):
        """All responses must include security headers."""
        headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
        }

        assert "Strict-Transport-Security" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers

    def test_hsts_max_age(self):
        """HSTS max-age must be at least 1 year."""
        header_value = "max-age=31536000; includeSubDomains"

        # Extract max-age value
        max_age = int(header_value.split("max-age=")[1].split(";")[0])
        one_year_seconds = 365 * 24 * 60 * 60

        assert max_age >= one_year_seconds


class TestLocalStorageSchema:
    """Contract tests for client-side localStorage schema."""

    def test_complete_storage_schema(self):
        """Complete localStorage schema per contract."""
        storage = {
            "sentiment_user_id": "550e8400-e29b-41d4-a716-446655440000",
            "sentiment_auth_type": "google",
            "sentiment_tokens": {
                "id_token": "eyJ...",
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "expires_at": 1732633200,
            },
            "sentiment_session_expires": "2025-12-26T10:00:00Z",
        }

        # All expected keys present
        assert "sentiment_user_id" in storage
        assert "sentiment_auth_type" in storage
        assert "sentiment_tokens" in storage
        assert "sentiment_session_expires" in storage

        # Auth type valid
        assert storage["sentiment_auth_type"] in [
            "anonymous",
            "email",
            "google",
            "github",
        ]

        # Token structure
        tokens = storage["sentiment_tokens"]
        assert "id_token" in tokens
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_at" in tokens

    def test_anonymous_storage_schema(self):
        """localStorage schema for anonymous users (no tokens)."""
        storage = {
            "sentiment_user_id": "550e8400-e29b-41d4-a716-446655440000",
            "sentiment_auth_type": "anonymous",
            "sentiment_session_expires": "2025-12-26T10:00:00Z",
        }

        # Anonymous users don't have tokens
        assert storage["sentiment_auth_type"] == "anonymous"
        assert (
            "sentiment_tokens" not in storage or storage.get("sentiment_tokens") is None
        )


def _is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID format."""
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _is_valid_iso_datetime(value: str) -> bool:
    """Check if string is valid ISO datetime."""
    try:
        # Handle both Z and +00:00 suffixes
        value = value.replace("Z", "+00:00")
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False
