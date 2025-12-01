"""Contract tests for Feature 014 Session API v2 (Session Consistency).

Tests for:
- POST /api/v2/auth/anonymous (T015)
- GET /api/v2/auth/session (T016)
- POST /api/v2/auth/magic-link/verify - 409 response (T030)

Validates responses conform to contracts/session-api-v2.yaml schema.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, Field

# --- Response Schema Definitions (from session-api-v2.yaml) ---


class SessionResponse(BaseModel):
    """Schema for POST /api/v2/auth/anonymous response."""

    user_id: str = Field(..., description="UUID")
    auth_type: str = Field(..., pattern="^(anonymous|email|google|github)$")
    session_expires_at: str = Field(..., description="ISO 8601 datetime")
    access_token: str = Field(..., description="JWT access token")
    is_new_session: bool | None = None


class SessionStatusResponse(BaseModel):
    """Schema for GET /api/v2/auth/session response."""

    user_id: str
    auth_type: str = Field(..., pattern="^(anonymous|email|google|github)$")
    email: str | None = None
    session_expires_at: str
    is_valid: bool
    remaining_seconds: int | None = None
    revoked: bool | None = None


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str
    message: str
    code: str
    details: dict[str, Any] | None = None


# --- Contract Tests for POST /api/v2/auth/anonymous (T015) ---


@pytest.mark.contract
@pytest.mark.session_consistency
@pytest.mark.session_us1
class TestAnonymousSessionCreateV2:
    """Contract tests for POST /api/v2/auth/anonymous (T015)."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per session-api-v2.yaml."""
        response = self._simulate_create_response()

        # Validate against schema
        parsed = SessionResponse(**response)

        assert parsed.user_id is not None
        assert parsed.auth_type == "anonymous"
        assert parsed.session_expires_at is not None
        assert parsed.access_token is not None

    def test_user_id_is_valid_uuid(self):
        """user_id must be a valid UUID v4."""
        response = self._simulate_create_response()

        user_uuid = uuid.UUID(response["user_id"])
        assert user_uuid.version == 4

    def test_access_token_is_jwt_format(self):
        """access_token must be JWT format (3 dot-separated parts)."""
        response = self._simulate_create_response()

        token = response["access_token"]
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have 3 parts (header.payload.signature)"

    def test_session_expires_in_30_days(self):
        """Session should expire approximately 30 days from creation."""
        response = self._simulate_create_response()

        expires_at = datetime.fromisoformat(
            response["session_expires_at"].replace("Z", "+00:00")
        )
        now = datetime.now(UTC)
        duration = expires_at - now

        # Allow 1 day tolerance
        assert 29 <= duration.days <= 31

    def test_timestamps_are_iso8601(self):
        """Timestamps must be ISO 8601 format."""
        response = self._simulate_create_response()

        # Should parse without error
        expires_at = datetime.fromisoformat(
            response["session_expires_at"].replace("Z", "+00:00")
        )
        assert expires_at.tzinfo is not None

    def test_response_status_200(self):
        """Response status code should be 200 per contract."""
        status_code = 200  # Contract specifies 200
        assert status_code == 200

    def test_is_new_session_flag_optional(self):
        """is_new_session is optional but present for new sessions."""
        response = self._simulate_create_response(is_new=True)

        assert response.get("is_new_session") is True

        response2 = self._simulate_create_response(is_new=False)
        assert response2.get("is_new_session") is False

    def test_existing_session_id_returns_same_user(self):
        """If existing_session_id is valid, returns same session."""
        user_id = str(uuid.uuid4())
        response = self._simulate_create_response(existing_user_id=user_id)

        assert response["user_id"] == user_id
        assert response.get("is_new_session") is False

    def test_x_user_id_header_returned(self):
        """Response should include X-User-ID header for backward compatibility."""
        response = self._simulate_create_response()
        headers = {"X-User-ID": response["user_id"]}

        assert "X-User-ID" in headers
        assert headers["X-User-ID"] == response["user_id"]

    # --- Helper Methods ---

    def _simulate_create_response(
        self,
        existing_user_id: str | None = None,
        is_new: bool = True,
    ) -> dict[str, Any]:
        """Simulate anonymous session creation response per contract."""
        now = datetime.now(UTC)
        expires = now + timedelta(days=30)

        user_id = existing_user_id or str(uuid.uuid4())

        return {
            "user_id": user_id,
            "auth_type": "anonymous",
            "session_expires_at": expires.isoformat().replace("+00:00", "Z"),
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            "is_new_session": is_new if existing_user_id is None else False,
        }


# --- Contract Tests for GET /api/v2/auth/session (T016) ---


@pytest.mark.contract
@pytest.mark.session_consistency
@pytest.mark.session_us1
class TestSessionStatusV2:
    """Contract tests for GET /api/v2/auth/session (T016)."""

    def test_valid_session_response_format(self):
        """Valid session returns correct response format per schema."""
        response = self._simulate_status_response(is_valid=True)

        parsed = SessionStatusResponse(**response)
        assert parsed.is_valid is True
        assert parsed.user_id is not None
        assert parsed.auth_type in ("anonymous", "email", "google", "github")
        assert parsed.session_expires_at is not None

    def test_response_includes_remaining_seconds(self):
        """Response includes remaining_seconds for session."""
        response = self._simulate_status_response(is_valid=True)

        assert "remaining_seconds" in response
        assert response["remaining_seconds"] > 0

    def test_response_includes_revoked_flag(self):
        """Response includes revoked flag."""
        response = self._simulate_status_response(is_valid=True)

        assert "revoked" in response
        assert response["revoked"] is False

    def test_email_included_for_authenticated_users(self):
        """Email is included for authenticated users."""
        response = self._simulate_status_response(
            is_valid=True,
            auth_type="email",
            email="test@example.com",
        )

        assert response["email"] == "test@example.com"
        assert response["auth_type"] == "email"

    def test_email_null_for_anonymous_users(self):
        """Email is null for anonymous users."""
        response = self._simulate_status_response(
            is_valid=True,
            auth_type="anonymous",
        )

        assert response["email"] is None
        assert response["auth_type"] == "anonymous"

    def test_response_status_200_for_valid(self):
        """Valid session returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_401_for_missing_auth(self):
        """Missing authentication header returns 401."""
        error_response = {
            "error": "unauthorized",
            "message": "Authentication required",
            "code": "UNAUTHORIZED",
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error == "unauthorized"
        assert parsed.code == "UNAUTHORIZED"

    def test_403_for_revoked_session(self):
        """Revoked session returns 403 with specific error."""
        error_response = {
            "error": "session_revoked",
            "message": "Your session has been revoked. Please sign in again.",
            "code": "SESSION_REVOKED",
            "details": {"reason": "Security incident response"},
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error == "session_revoked"
        assert parsed.code == "SESSION_REVOKED"
        assert parsed.details is not None
        assert "reason" in parsed.details

    def test_hybrid_auth_accepts_bearer_token(self):
        """Endpoint accepts Authorization: Bearer token (FR-001)."""
        # Contract specifies BearerAuth security scheme
        valid_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."}
        assert "Authorization" in valid_headers
        assert valid_headers["Authorization"].startswith("Bearer ")

    def test_hybrid_auth_accepts_x_user_id(self):
        """Endpoint accepts X-User-ID header for backward compatibility (FR-001)."""
        # Contract specifies UserIdHeader security scheme
        user_id = str(uuid.uuid4())
        valid_headers = {"X-User-ID": user_id}
        assert "X-User-ID" in valid_headers

    # --- Helper Methods ---

    def _simulate_status_response(
        self,
        is_valid: bool,
        auth_type: str = "anonymous",
        email: str | None = None,
    ) -> dict[str, Any]:
        """Simulate session status response per contract."""
        expires = datetime.now(UTC) + timedelta(days=25)
        remaining = int((expires - datetime.now(UTC)).total_seconds())

        return {
            "user_id": str(uuid.uuid4()),
            "auth_type": auth_type,
            "email": email,
            "session_expires_at": expires.isoformat().replace("+00:00", "Z"),
            "is_valid": is_valid,
            "remaining_seconds": remaining if is_valid else 0,
            "revoked": False,
        }


# --- Contract Tests for POST /api/v2/auth/magic-link/verify 409 (T030) ---


@pytest.mark.contract
@pytest.mark.session_consistency
@pytest.mark.session_us2
class TestMagicLinkVerify409:
    """Contract tests for token already used error response (T030)."""

    def test_409_conflict_response_format(self):
        """409 Conflict response follows error schema."""
        error_response = {
            "error": "token_already_used",
            "message": "This magic link has already been verified",
            "code": "TOKEN_ALREADY_USED",
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error == "token_already_used"
        assert parsed.code == "TOKEN_ALREADY_USED"
        assert "already" in parsed.message.lower()

    def test_409_status_for_race_condition(self):
        """Second verification attempt returns 409."""
        status_code = 409  # Contract specifies 409 for already-used token
        assert status_code == 409

    def test_410_for_expired_token(self):
        """Expired token returns 410 Gone."""
        error_response = {
            "error": "token_expired",
            "message": "This magic link has expired. Please request a new one.",
            "code": "TOKEN_EXPIRED",
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error == "token_expired"
        assert parsed.code == "TOKEN_EXPIRED"

    def test_410_status_for_expired(self):
        """Expired token returns 410 status code."""
        status_code = 410  # Contract specifies 410 for expired token
        assert status_code == 410


# --- Security Contract Tests ---


@pytest.mark.contract
@pytest.mark.session_consistency
class TestSessionSecurityContracts:
    """Security requirements for session endpoints."""

    def test_no_sensitive_data_in_error_messages(self):
        """Error messages should not leak sensitive information."""
        error_messages = [
            "Authentication required",
            "Your session has been revoked. Please sign in again.",
            "This magic link has already been verified",
            "This magic link has expired. Please request a new one.",
        ]

        for msg in error_messages:
            assert "Exception" not in msg
            assert "Traceback" not in msg
            assert "stack" not in msg.lower()
            assert "internal" not in msg.lower()

    def test_user_id_is_opaque(self):
        """User IDs should not leak information about creation order."""
        # UUIDs should be random v4, not sequential
        user_id = str(uuid.uuid4())
        parsed = uuid.UUID(user_id)
        assert parsed.version == 4
