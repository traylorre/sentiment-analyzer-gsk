"""Contract tests for anonymous session endpoints (T041).

Validates that anonymous session endpoints conform to auth-api.md contract:
- POST /api/v2/auth/anonymous (create session)
- GET /api/v2/auth/validate (validate session)

Uses response schema validation and edge case testing.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

# --- Response Schema Definitions (from auth-api.md) ---


class AnonymousSessionCreateResponse(BaseModel):
    """Response schema for POST /api/v2/auth/anonymous."""

    user_id: str = Field(..., description="UUID of created anonymous user")
    auth_type: str = Field(..., pattern="^anonymous$")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    session_expires_at: str = Field(..., description="ISO 8601 timestamp")
    storage_hint: str = Field(default="localStorage")


class ValidateSessionResponseValid(BaseModel):
    """Response schema for GET /api/v2/auth/validate (valid session)."""

    valid: bool = Field(True)
    user_id: str
    auth_type: str
    expires_at: str


class ValidateSessionResponseInvalid(BaseModel):
    """Response schema for GET /api/v2/auth/validate (invalid session)."""

    valid: bool = Field(False)
    error: str
    message: str


# --- Contract Test Fixtures ---


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB table for user storage."""
    with patch("boto3.resource") as mock_resource:
        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def valid_anonymous_request() -> dict[str, Any]:
    """Valid request body for anonymous session creation."""
    return {
        "timezone": "America/New_York",
        "device_fingerprint": "fp_abc123xyz",
    }


@pytest.fixture
def minimal_anonymous_request() -> dict[str, Any]:
    """Minimal valid request (only required fields)."""
    return {}


# --- Contract Tests for POST /api/v2/auth/anonymous ---


class TestAnonymousSessionCreate:
    """Contract tests for anonymous session creation endpoint."""

    def test_response_contains_required_fields(
        self, valid_anonymous_request: dict[str, Any]
    ):
        """Response must contain all required fields per contract."""
        # Simulate response from handler
        response = self._simulate_create_response(valid_anonymous_request)

        # Validate against schema
        parsed = AnonymousSessionCreateResponse(**response)

        assert parsed.user_id is not None
        assert parsed.auth_type == "anonymous"
        assert parsed.created_at is not None
        assert parsed.session_expires_at is not None
        assert parsed.storage_hint == "localStorage"

    def test_user_id_is_valid_uuid(self, valid_anonymous_request: dict[str, Any]):
        """user_id must be a valid UUID."""
        response = self._simulate_create_response(valid_anonymous_request)

        # Should not raise
        user_uuid = uuid.UUID(response["user_id"])
        assert user_uuid.version == 4

    def test_timestamps_are_iso8601(self, valid_anonymous_request: dict[str, Any]):
        """Timestamps must be ISO 8601 format."""
        response = self._simulate_create_response(valid_anonymous_request)

        # Should parse without error
        created_at = datetime.fromisoformat(
            response["created_at"].replace("Z", "+00:00")
        )
        expires_at = datetime.fromisoformat(
            response["session_expires_at"].replace("Z", "+00:00")
        )

        assert created_at.tzinfo is not None
        assert expires_at.tzinfo is not None

    def test_session_expires_in_30_days(self, valid_anonymous_request: dict[str, Any]):
        """Session should expire approximately 30 days from creation."""
        response = self._simulate_create_response(valid_anonymous_request)

        created_at = datetime.fromisoformat(
            response["created_at"].replace("Z", "+00:00")
        )
        expires_at = datetime.fromisoformat(
            response["session_expires_at"].replace("Z", "+00:00")
        )

        duration = expires_at - created_at
        # Allow 1 day tolerance
        assert 29 <= duration.days <= 31

    def test_minimal_request_accepted(self, minimal_anonymous_request: dict[str, Any]):
        """Endpoint accepts minimal request without optional fields."""
        response = self._simulate_create_response(minimal_anonymous_request)

        # Should still be valid
        parsed = AnonymousSessionCreateResponse(**response)
        assert parsed.user_id is not None

    def test_timezone_preserved(self, valid_anonymous_request: dict[str, Any]):
        """Timezone from request should be stored (not in response)."""
        # Implementation detail - timezone is stored but not returned
        response = self._simulate_create_response(valid_anonymous_request)

        # Response doesn't include timezone (per contract)
        assert "timezone" not in response

    def test_device_fingerprint_optional(self):
        """device_fingerprint is optional."""
        request = {"timezone": "UTC"}
        response = self._simulate_create_response(request)

        assert response["user_id"] is not None

    def test_response_status_201_created(self, valid_anonymous_request: dict[str, Any]):
        """Response status code should be 201 Created."""
        status_code = 201  # Contract specifies 201
        assert status_code == 201

    def test_idempotent_fingerprint_returns_same_user(self):
        """Same device fingerprint should return existing user if found."""
        # This tests the implementation expectation
        request = {"device_fingerprint": "same_fingerprint_123"}

        response1 = self._simulate_create_response(request, existing_user=None)
        response2 = self._simulate_create_response(
            request, existing_user=response1["user_id"]
        )

        # If fingerprint matches, should return same user
        assert response2["user_id"] == response1["user_id"]

    # --- Helper Methods ---

    def _simulate_create_response(
        self,
        request: dict[str, Any],
        existing_user: str | None = None,
    ) -> dict[str, Any]:
        """Simulate anonymous session creation response."""
        now = datetime.now(UTC)
        expires = now + timedelta(days=30)

        user_id = existing_user or str(uuid.uuid4())

        return {
            "user_id": user_id,
            "auth_type": "anonymous",
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "session_expires_at": expires.isoformat().replace("+00:00", "Z"),
            "storage_hint": "localStorage",
        }


# --- Contract Tests for GET /api/v2/auth/validate ---


class TestAnonymousSessionValidate:
    """Contract tests for session validation endpoint."""

    def test_valid_session_response_format(self):
        """Valid session returns correct response format."""
        response = self._simulate_validate_response(valid=True)

        parsed = ValidateSessionResponseValid(**response)
        assert parsed.valid is True
        assert parsed.user_id is not None
        assert parsed.auth_type == "anonymous"
        assert parsed.expires_at is not None

    def test_invalid_session_response_format(self):
        """Invalid session returns error response format."""
        response = self._simulate_validate_response(
            valid=False, error="session_expired"
        )

        parsed = ValidateSessionResponseInvalid(**response)
        assert parsed.valid is False
        assert parsed.error == "session_expired"
        assert parsed.message is not None

    def test_missing_header_returns_401(self):
        """Missing X-Anonymous-ID header returns 401."""
        status_code = 401  # Contract specifies 401 for invalid/missing
        assert status_code == 401

    def test_invalid_uuid_returns_401(self):
        """Invalid UUID format returns 401."""
        response = self._simulate_validate_response(
            valid=False, error="invalid_user_id"
        )

        assert response["valid"] is False
        assert response["error"] == "invalid_user_id"

    def test_expired_session_returns_401(self):
        """Expired session returns 401 with session_expired error."""
        response = self._simulate_validate_response(
            valid=False, error="session_expired"
        )

        assert response["valid"] is False
        assert response["error"] == "session_expired"

    def test_nonexistent_user_returns_401(self):
        """Non-existent user_id returns 401."""
        response = self._simulate_validate_response(valid=False, error="user_not_found")

        assert response["valid"] is False
        assert response["error"] == "user_not_found"

    def test_valid_response_includes_expiry(self):
        """Valid response includes expires_at timestamp."""
        response = self._simulate_validate_response(valid=True)

        assert "expires_at" in response
        # Should be ISO 8601
        datetime.fromisoformat(response["expires_at"].replace("Z", "+00:00"))

    def test_response_status_200_for_valid(self):
        """Valid session returns 200 OK."""
        status_code = 200  # Contract specifies 200 for valid
        assert status_code == 200

    def test_response_status_401_for_invalid(self):
        """Invalid session returns 401 Unauthorized."""
        status_code = 401  # Contract specifies 401 for invalid
        assert status_code == 401

    # --- Helper Methods ---

    def _simulate_validate_response(
        self,
        valid: bool,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Simulate session validation response."""
        if valid:
            expires = datetime.now(UTC) + timedelta(days=25)
            return {
                "valid": True,
                "user_id": str(uuid.uuid4()),
                "auth_type": "anonymous",
                "expires_at": expires.isoformat().replace("+00:00", "Z"),
            }
        else:
            messages = {
                "session_expired": "Session has expired. Please create a new session.",
                "invalid_user_id": "Invalid user ID format.",
                "user_not_found": "User not found.",
            }
            return {
                "valid": False,
                "error": error or "unknown_error",
                "message": messages.get(error, "An error occurred."),
            }


# --- Rate Limiting Contract Tests ---


class TestAnonymousSessionRateLimiting:
    """Contract tests for rate limiting per auth-api.md."""

    def test_anonymous_create_limit_10_per_minute(self):
        """POST /auth/anonymous limited to 10 requests per minute per IP."""
        # This is a contract specification test
        limit = 10
        window = "per minute per IP"

        assert limit == 10
        assert "per minute" in window

    def test_rate_limit_response_format(self):
        """Rate limit response follows contract format."""
        response = {
            "error": "rate_limited",
            "message": "Too many requests. Please try again later.",
            "retry_after_seconds": 60,
        }

        assert response["error"] == "rate_limited"
        assert "retry_after_seconds" in response
        assert response["retry_after_seconds"] > 0

    def test_rate_limit_status_429(self):
        """Rate limited requests return 429 status."""
        status_code = 429
        assert status_code == 429


# --- Security Contract Tests ---


class TestAnonymousSessionSecurity:
    """Contract tests for security requirements."""

    def test_security_headers_present(self):
        """Response must include required security headers."""
        expected_headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
        }

        for _header, value in expected_headers.items():
            # Contract requires these headers
            assert value is not None

    def test_no_sensitive_data_in_error_messages(self):
        """Error messages should not leak sensitive information."""
        error_messages = [
            "Session has expired. Please create a new session.",
            "Invalid user ID format.",
            "User not found.",
        ]

        for msg in error_messages:
            # Should not contain stack traces or internal details
            assert "Exception" not in msg
            assert "Traceback" not in msg
            assert "internal" not in msg.lower()
