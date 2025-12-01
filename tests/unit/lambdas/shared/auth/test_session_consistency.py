"""Unit tests for session consistency (Feature 014, User Story 1).

Tests for FR-001, FR-002, FR-003: Hybrid auth header support and session validation.

These tests verify:
- Backend accepts both X-User-ID and Authorization: Bearer headers
- User ID is extracted consistently from either format
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
class TestHybridHeaderExtraction:
    """Tests for hybrid authentication header extraction (FR-001, FR-002)."""

    def test_extract_user_id_from_bearer_token(self):
        """FR-001: Backend accepts Authorization: Bearer token."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"Authorization": f"Bearer {user_id}"}}

        result = extract_user_id(event)

        assert result == user_id

    def test_extract_user_id_from_x_user_id_header(self):
        """FR-001: Backend accepts X-User-ID header (legacy)."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        result = extract_user_id(event)

        assert result == user_id

    def test_bearer_token_takes_precedence_over_x_user_id(self):
        """FR-001: Bearer token is preferred when both headers present."""
        bearer_user_id = str(uuid.uuid4())
        header_user_id = str(uuid.uuid4())
        event = {
            "headers": {
                "Authorization": f"Bearer {bearer_user_id}",
                "X-User-ID": header_user_id,
            }
        }

        result = extract_user_id(event)

        assert result == bearer_user_id

    def test_extract_user_id_case_insensitive_headers(self):
        """FR-002: Header keys are case-insensitive."""
        user_id = str(uuid.uuid4())

        # Test lowercase
        event1 = {"headers": {"authorization": f"Bearer {user_id}"}}
        assert extract_user_id(event1) == user_id

        # Test mixed case
        event2 = {"headers": {"x-user-id": user_id}}
        assert extract_user_id(event2) == user_id

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

    def test_extract_user_id_returns_none_for_invalid_x_user_id(self):
        """Invalid X-User-ID (non-UUID) returns None."""
        event = {"headers": {"X-User-ID": "invalid-not-uuid"}}

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

    def test_extract_auth_context_x_user_id(self):
        """Auth context includes method when using X-User-ID."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        context = extract_auth_context(event)

        assert context["user_id"] == user_id
        assert context["auth_method"] == "x-user-id"
        assert context["is_authenticated"] is True

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

    def test_require_auth_returns_user_id_when_valid(self):
        """require_auth returns user_id for valid request."""
        user_id = str(uuid.uuid4())
        event = {"headers": {"X-User-ID": user_id}}

        result = require_auth(event)

        assert result == user_id

    def test_require_auth_raises_for_missing_auth(self):
        """require_auth raises ValueError when no auth present."""
        event = {"headers": {}}

        with pytest.raises(ValueError, match="Authentication required"):
            require_auth(event)

    def test_require_auth_raises_for_invalid_uuid(self):
        """require_auth raises ValueError for invalid UUID."""
        event = {"headers": {"X-User-ID": "not-a-uuid"}}

        with pytest.raises(ValueError, match="Authentication required"):
            require_auth(event)
