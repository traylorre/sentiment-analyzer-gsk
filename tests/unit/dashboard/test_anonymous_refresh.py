"""Unit tests for anonymous-session refresh (M1 WI-3, guest restore).

Guests are not Cognito-backed: their refresh token is opaque and
self-describing (anon.{user_id}.{secret}), only its hash is stored on the
USER#/PROFILE item, and POST /refresh serves them from DynamoDB with
single-use rotation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.auth import (
    AnonymousSessionRequest,
    create_anonymous_session,
    hash_refresh_token,
    refresh_access_tokens,
)


def _guest_item(user_id: str, token: str, *, expires_in_days: int = 10) -> dict:
    """Build a USER#/PROFILE item as stored by create_anonymous_session."""
    expires = datetime.now(UTC) + timedelta(days=expires_in_days)
    return {
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "user_id": user_id,
        "auth_type": "anonymous",
        "session_expires_at": expires.isoformat().replace("+00:00", "Z"),
        "anon_refresh_token_hash": hash_refresh_token(token),
    }


class TestAnonymousSessionMintsRefreshToken:
    """create_anonymous_session must mint and hash-store a refresh token."""

    def test_response_carries_cookie_token_with_anon_prefix(self):
        mock_table = MagicMock()
        response = create_anonymous_session(mock_table, AnonymousSessionRequest())

        token = response.refresh_token_for_cookie
        assert token is not None
        assert token.startswith(f"anon.{response.user_id}.")
        # secret part is non-trivial
        assert len(token.split(".")[2]) >= 32

    def test_item_stores_only_the_hash_never_the_token(self):
        mock_table = MagicMock()
        response = create_anonymous_session(mock_table, AnonymousSessionRequest())

        item = mock_table.put_item.call_args.kwargs["Item"]
        token = response.refresh_token_for_cookie
        assert item["anon_refresh_token_hash"] == hash_refresh_token(token)
        # raw token must not appear anywhere on the stored item
        assert token not in str(item)


class TestRefreshAnonymousSession:
    """refresh_access_tokens must serve anon.* tokens from DynamoDB."""

    def _table_with(self, item: dict | None) -> MagicMock:
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": item} if item is not None else {}
        # blocklist lookup path (is_token_blocklisted) also uses get_item;
        # first call is the blocklist BLOCKLIST# key, second is the user.
        # Simpler: blocklist helper queries a different key shape and returns
        # falsy on {} - here every get_item returns the user item, and the
        # blocklist check tolerates that because the item lacks blocklist
        # attributes. Guarded by test_blocklisted_token_refused below.
        return mock_table

    def test_happy_path_restores_and_rotates(self):
        user_id = "11111111-2222-3333-4444-555555555555"
        token = f"anon.{user_id}.legit-secret-value-0123456789abcdef"
        item = _guest_item(user_id, token)
        mock_table = self._table_with(item)

        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(refresh_token=token, table=mock_table)

        assert result.error is None
        assert result.access_token == user_id  # guest bearer IS the user_id
        assert result.user_id == user_id
        assert result.auth_type == "anonymous"
        assert result.expires_in > 0
        # rotated: new token minted, different from presented
        new_token = result.refresh_token_for_cookie
        assert new_token is not None and new_token != token
        assert new_token.startswith(f"anon.{user_id}.")
        # rotation persisted with a conditional update on the old hash
        update_kwargs = mock_table.update_item.call_args.kwargs
        assert update_kwargs["ExpressionAttributeValues"][":h"] == hash_refresh_token(
            new_token
        )
        assert update_kwargs["ExpressionAttributeValues"][":old"] == hash_refresh_token(
            token
        )
        assert "anon_refresh_token_hash = :old" in update_kwargs["ConditionExpression"]

    def test_never_touches_cognito(self):
        user_id = "11111111-2222-3333-4444-555555555555"
        token = f"anon.{user_id}.secret"
        mock_table = self._table_with(_guest_item(user_id, token))

        with (
            patch(
                "src.lambdas.dashboard.auth.is_token_blocklisted",
                return_value=False,
            ),
            patch("src.lambdas.dashboard.auth.CognitoConfig") as mock_config,
        ):
            refresh_access_tokens(refresh_token=token, table=mock_table)
            mock_config.from_env.assert_not_called()

    def test_malformed_token_refused(self):
        mock_table = self._table_with(None)
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(refresh_token="anon.", table=mock_table)
        assert result.error == "invalid_token"

    def test_unknown_user_refused(self):
        mock_table = self._table_with(None)
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(
                refresh_token="anon.nobody.secret", table=mock_table
            )
        assert result.error == "invalid_token"

    def test_hash_mismatch_refused(self):
        user_id = "u-1"
        item = _guest_item(user_id, f"anon.{user_id}.the-real-secret")
        mock_table = self._table_with(item)
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(
                refresh_token=f"anon.{user_id}.a-stolen-guess", table=mock_table
            )
        assert result.error == "invalid_token"
        mock_table.update_item.assert_not_called()

    def test_non_anonymous_user_refused(self):
        user_id = "u-2"
        token = f"anon.{user_id}.secret"
        item = _guest_item(user_id, token)
        item["auth_type"] = "cognito"
        mock_table = self._table_with(item)
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(refresh_token=token, table=mock_table)
        assert result.error == "invalid_token"

    def test_expired_session_refused(self):
        user_id = "u-3"
        token = f"anon.{user_id}.secret"
        item = _guest_item(user_id, token, expires_in_days=-1)
        mock_table = self._table_with(item)
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(refresh_token=token, table=mock_table)
        assert result.error == "session_expired"
        mock_table.update_item.assert_not_called()

    def test_blocklisted_token_refused_before_anon_path(self):
        user_id = "u-4"
        token = f"anon.{user_id}.secret"
        mock_table = self._table_with(_guest_item(user_id, token))
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=True
        ):
            result = refresh_access_tokens(refresh_token=token, table=mock_table)
        assert result.error == "token_revoked"
        mock_table.update_item.assert_not_called()

    def test_no_table_refused(self):
        result = refresh_access_tokens(refresh_token="anon.u.secret", table=None)
        assert result.error == "invalid_token"

    def test_concurrent_rotation_conflict_refused(self):
        """ConditionExpression failure (already-rotated token) must 401."""
        user_id = "u-5"
        token = f"anon.{user_id}.secret"
        mock_table = self._table_with(_guest_item(user_id, token))
        mock_table.update_item.side_effect = Exception("ConditionalCheckFailed")
        with patch(
            "src.lambdas.dashboard.auth.is_token_blocklisted", return_value=False
        ):
            result = refresh_access_tokens(refresh_token=token, table=mock_table)
        assert result.error == "invalid_token"
