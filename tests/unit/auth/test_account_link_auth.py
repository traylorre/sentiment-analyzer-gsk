"""Tests for account merge authorization (Feature 1222, US2)."""

from unittest.mock import MagicMock

from src.lambdas.dashboard.auth import LinkAccountsRequest, link_accounts


class TestAccountMergeAuth:
    """FR-003, FR-004: Account merge authorization checks."""

    def test_unauthenticated_rejected(self):
        """Empty current_user_id is rejected."""
        table = MagicMock()
        request = LinkAccountsRequest(
            link_to_user_id="target-user-id",
            confirmation=True,
        )

        result = link_accounts(table, "", request)
        assert result.status == "error"
        assert result.error == "authentication_required"

    def test_self_merge_rejected(self):
        """Cannot merge an account with itself."""
        table = MagicMock()
        user_id = "aaaa1111-0000-0000-0000-000000000001"
        request = LinkAccountsRequest(
            link_to_user_id=user_id,
            confirmation=True,
        )

        result = link_accounts(table, user_id, request)
        assert result.status == "error"
        assert result.error == "self_link_not_allowed"

    def test_confirmation_required(self):
        """Request without confirmation flag is rejected."""
        table = MagicMock()
        request = LinkAccountsRequest(
            link_to_user_id="target-user-id",
            confirmation=False,
        )

        result = link_accounts(table, "aaaa1111-0000-0000-0000-000000000001", request)
        assert result.status == "error"
        assert "confirmation" in result.message.lower()
