"""Unit tests for session consistency (Feature 014, User Story 1).

Tests for FR-001, FR-002, FR-003: Bearer-only authentication and session validation.

Feature 1146: X-User-ID header fallback REMOVED for security (CVSS 9.1).

These tests verify:
- Backend ONLY accepts Authorization: Bearer headers
- X-User-ID header is IGNORED (no longer accepted for identity)
- User ID is extracted exclusively from Bearer tokens
- Invalid headers are rejected appropriately
"""

import uuid

import pytest

from src.lambdas.shared.middleware.auth_middleware import (
    extract_auth_context,
    extract_user_id,
    require_auth,
)


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us1
class TestBearerOnlyAuthentication:
    """Tests for Bearer-only authentication (Feature 1146 security fix)."""

    def test_extract_user_id_from_bearer_token(self):
        """FR-001: Backend accepts Authorization: Bearer token."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        result = extract_user_id(event)

        assert result == user_id

    def test_x_user_id_header_ignored(self):
        """Feature 1146: X-User-ID header is IGNORED (security fix)."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        result = extract_user_id(event)

        # X-User-ID should be ignored - returns None
        assert result is None

    def test_bearer_token_used_even_with_x_user_id_present(self):
        """Feature 1146: Only Bearer token used, X-User-ID completely ignored."""
        bearer_user_id = str(uuid.uuid4())
        header_user_id = str(uuid.uuid4())
        event = {
            "headers": {
                "Authorization": f"Bearer {bearer_user_id}",
                "X-User-ID": header_user_id,
            }
        }

        result = extract_user_id(event)

        # Only Bearer token should be used
        assert result == bearer_user_id
        assert result != header_user_id

    def test_extract_user_id_case_insensitive_authorization_header(self):
        """FR-002: Authorization header keys are case-insensitive."""
        user_id = str(uuid.uuid4())

        # Test lowercase authorization
        event = {"headers": {"authorization": f"Bearer {user_id}"}}
        assert extract_user_id(event) == user_id

    def test_extract_user_id_returns_none_for_missing_headers(self):
        """No user ID when headers are missing."""
        event = {"headers": {}}

        result = extract_user_id(event)

        assert result is None

    def test_extract_user_id_returns_none_for_invalid_bearer(self):
        """Invalid Bearer token (non-UUID) returns None."""
        event = {"headers": {"Authorization": "Bearer invalid-not-uuid"}}

        result = extract_user_id(event)

        assert result is None

    def test_extract_user_id_handles_none_headers(self):
        """Gracefully handles None headers dict."""
        event = {"headers": None}

        result = extract_user_id(event)

        assert result is None


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us1
class TestAuthContext:
    """Tests for full auth context extraction (FR-002)."""

    def test_extract_auth_context_bearer(self):
        """Auth context includes method when using Bearer."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        context = extract_auth_context(event)

        assert context["user_id"] == user_id
        assert context["auth_method"] == "bearer"
        assert context["is_authenticated"] is True

    def test_extract_auth_context_x_user_id_returns_unauthenticated(self):
        """Feature 1146: X-User-ID header returns unauthenticated context."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        context = extract_auth_context(event)

        # X-User-ID is ignored, so no authentication
        assert context["user_id"] is None
        assert context["auth_method"] is None
        assert context["is_authenticated"] is False

    def test_extract_auth_context_unauthenticated(self):
        """Auth context for unauthenticated request."""
        event = {"headers": {}}

        context = extract_auth_context(event)

        assert context["user_id"] is None
        assert context["auth_method"] is None
        assert context["is_authenticated"] is False


@pytest.mark.unit
@pytest.mark.session_consistency
@pytest.mark.session_us1
class TestRequireAuth:
    """Tests for require_auth helper (FR-002)."""

    def test_require_auth_returns_user_id_when_valid_bearer(self):
        """require_auth returns user_id for valid Bearer token."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        result = require_auth(event)

        assert result == user_id

    def test_require_auth_raises_for_x_user_id_only(self):
        """Feature 1146: require_auth raises when only X-User-ID present."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        # X-User-ID alone should NOT authenticate
        with pytest.raises(ValueError, match="Authentication required"):
            require_auth(event)

    def test_require_auth_raises_for_missing_auth(self):
        """require_auth raises ValueError when no auth present."""
        event = {"headers": {}}

        with pytest.raises(ValueError, match="Authentication required"):
            require_auth(event)

    def test_require_auth_raises_for_invalid_uuid(self):
        """require_auth raises ValueError for invalid UUID in Bearer."""
        event = {"headers": {"Authorization": "Bearer not-a-uuid"}}

        with pytest.raises(ValueError, match="Authentication required"):
            require_auth(event)
