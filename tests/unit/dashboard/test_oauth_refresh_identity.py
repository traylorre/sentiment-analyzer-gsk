"""Unit tests for OAuth (Cognito) refresh identity resolution.

Feature 1381 (Defect B): the Cognito refresh branch of refresh_access_tokens
previously returned user_id=None, so the frontend restoreSession() bailed to
signInAnonymous() and every OAuth session dropped to guest on reload. The fix
resolves the internal user_id from the freshly-issued id_token's stable Cognito
sub via the by_cognito_sub GSI (server-authoritative, never client input).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.auth import (
    get_user_by_cognito_sub,
    refresh_access_tokens,
)
from src.lambdas.shared.auth.cognito import CognitoTokens, TokenError


def _user_item(user_id: str, cognito_sub: str, auth_type: str = "google") -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "user_id": user_id,
        "auth_type": auth_type,
        "cognito_sub": cognito_sub,
        "entity_type": "USER",
        "role": "free",
        "verification": "verified",
        "created_at": now,
        "last_active_at": now,
        "session_expires_at": now,
    }


def _cognito_tokens() -> CognitoTokens:
    return CognitoTokens(
        id_token="header.payload.sig",  # decoded via patched decode_id_token
        access_token="access-xyz",
        refresh_token=None,  # Cognito does not rotate on refresh
        expires_in=3600,
    )


class TestGetUserByCognitoSub:
    def test_queries_by_cognito_sub_gsi_and_returns_user(self):
        table = MagicMock()
        table.query.return_value = {"Items": [_user_item("u-1", "sub-abc")]}

        user = get_user_by_cognito_sub(table, "sub-abc")

        assert user is not None
        assert user.user_id == "u-1"
        kwargs = table.query.call_args.kwargs
        assert kwargs["IndexName"] == "by_cognito_sub"
        assert kwargs["ExpressionAttributeValues"][":sub"] == "sub-abc"

    def test_empty_sub_returns_none_without_query(self):
        table = MagicMock()
        assert get_user_by_cognito_sub(table, "") is None
        table.query.assert_not_called()

    def test_no_match_returns_none(self):
        table = MagicMock()
        table.query.return_value = {"Items": []}
        assert get_user_by_cognito_sub(table, "missing") is None


class TestCognitoRefreshResolvesUserId:
    @patch("src.lambdas.dashboard.auth.CognitoConfig")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    @patch("src.lambdas.dashboard.auth.cognito_refresh_tokens")
    def test_populates_user_id_and_auth_type(
        self, mock_refresh, mock_decode, mock_config
    ):
        mock_refresh.return_value = _cognito_tokens()
        mock_decode.return_value = {"sub": "sub-abc"}
        table = MagicMock()
        # blocklist check + GSI query both go through table; blocklist -> get_item
        table.get_item.return_value = {}
        table.query.return_value = {"Items": [_user_item("u-1", "sub-abc", "google")]}

        result = refresh_access_tokens(refresh_token="cognito-rt", table=table)

        assert result.error is None
        assert result.access_token == "access-xyz"
        assert result.user_id == "u-1"
        assert result.auth_type == "google"

    @patch("src.lambdas.dashboard.auth.CognitoConfig")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    @patch("src.lambdas.dashboard.auth.cognito_refresh_tokens")
    def test_degrades_when_user_not_found(self, mock_refresh, mock_decode, mock_config):
        mock_refresh.return_value = _cognito_tokens()
        mock_decode.return_value = {"sub": "unknown-sub"}
        table = MagicMock()
        table.get_item.return_value = {}
        table.query.return_value = {"Items": []}

        result = refresh_access_tokens(refresh_token="cognito-rt", table=table)

        # tokens still returned; identity simply unresolved (today's behavior)
        assert result.error is None
        assert result.access_token == "access-xyz"
        assert result.user_id is None

    @patch("src.lambdas.dashboard.auth.CognitoConfig")
    @patch("src.lambdas.dashboard.auth.decode_id_token")
    @patch("src.lambdas.dashboard.auth.cognito_refresh_tokens")
    def test_identity_resolution_error_does_not_fail_refresh(
        self, mock_refresh, mock_decode, mock_config
    ):
        mock_refresh.return_value = _cognito_tokens()
        mock_decode.side_effect = ValueError("bad token")
        table = MagicMock()
        table.get_item.return_value = {}

        result = refresh_access_tokens(refresh_token="cognito-rt", table=table)

        assert result.error is None
        assert result.access_token == "access-xyz"
        assert result.user_id is None

    @patch("src.lambdas.dashboard.auth.CognitoConfig")
    @patch("src.lambdas.dashboard.auth.cognito_refresh_tokens")
    def test_cognito_reject_still_returns_error(self, mock_refresh, mock_config):
        mock_refresh.side_effect = TokenError(
            "invalid_refresh_token", "Please sign in again."
        )
        table = MagicMock()
        table.get_item.return_value = {}

        result = refresh_access_tokens(refresh_token="bad-rt", table=table)

        assert result.error == "invalid_refresh_token"
        assert result.user_id is None
