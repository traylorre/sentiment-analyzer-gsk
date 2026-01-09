"""Unit tests for role assignment audit trail (Feature 1175)."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.lambdas.shared.auth.audit import create_role_audit_entry


class TestCreateRoleAuditEntry:
    """Tests for create_role_audit_entry() function."""

    def test_oauth_source_format(self) -> None:
        """OAuth source produces oauth:{provider} format."""
        result = create_role_audit_entry("oauth", "google")
        assert result["role_assigned_by"] == "oauth:google"

    def test_oauth_github_provider(self) -> None:
        """OAuth works with github provider."""
        result = create_role_audit_entry("oauth", "github")
        assert result["role_assigned_by"] == "oauth:github"

    def test_stripe_source_format(self) -> None:
        """Stripe source produces stripe:{event} format."""
        result = create_role_audit_entry("stripe", "subscription_activated")
        assert result["role_assigned_by"] == "stripe:subscription_activated"

    def test_stripe_cancellation_event(self) -> None:
        """Stripe works with cancellation events."""
        result = create_role_audit_entry("stripe", "subscription_cancelled")
        assert result["role_assigned_by"] == "stripe:subscription_cancelled"

    def test_admin_source_format(self) -> None:
        """Admin source produces admin:{user_id} format."""
        result = create_role_audit_entry("admin", "admin-user-123")
        assert result["role_assigned_by"] == "admin:admin-user-123"

    def test_returns_both_audit_fields(self) -> None:
        """Result contains both role_assigned_at and role_assigned_by."""
        result = create_role_audit_entry("oauth", "google")
        assert "role_assigned_at" in result
        assert "role_assigned_by" in result

    def test_timestamp_is_iso_format(self) -> None:
        """Timestamp is in ISO 8601 format."""
        result = create_role_audit_entry("oauth", "google")
        timestamp = result["role_assigned_at"]
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None

    def test_timestamp_is_utc(self) -> None:
        """Timestamp is in UTC timezone."""
        with patch("src.lambdas.shared.auth.audit.datetime") as mock_dt:
            mock_now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now
            mock_dt.now.side_effect = None

            result = create_role_audit_entry("oauth", "google")
            assert result["role_assigned_at"] == mock_now.isoformat()

    def test_timestamp_includes_timezone(self) -> None:
        """Timestamp includes timezone indicator."""
        result = create_role_audit_entry("oauth", "google")
        timestamp = result["role_assigned_at"]
        # Should contain + for timezone offset
        assert "+" in timestamp or "Z" in timestamp


class TestAuditFieldConsistency:
    """Tests for consistency with existing patterns."""

    def test_matches_advance_role_pattern(self) -> None:
        """Output matches pattern used in _advance_role()."""
        result = create_role_audit_entry("oauth", "google")
        # _advance_role uses "oauth:{provider}" format
        assert result["role_assigned_by"].startswith("oauth:")

    @pytest.mark.parametrize(
        "source,identifier,expected_prefix",
        [
            ("oauth", "google", "oauth:"),
            ("oauth", "github", "oauth:"),
            ("stripe", "sub_123", "stripe:"),
            ("admin", "user-456", "admin:"),
        ],
    )
    def test_all_sources_have_consistent_format(
        self, source: str, identifier: str, expected_prefix: str
    ) -> None:
        """All sources follow {source}:{identifier} format."""
        result = create_role_audit_entry(source, identifier)  # type: ignore[arg-type]
        assert result["role_assigned_by"].startswith(expected_prefix)
        assert result["role_assigned_by"] == f"{source}:{identifier}"
