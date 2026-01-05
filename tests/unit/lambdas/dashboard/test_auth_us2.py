"""Unit tests for User Story 2 auth endpoints (T090-T099)."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.auth import (
    CheckEmailRequest,
    LinkAccountsRequest,
    MagicLinkRequest,
    OAuthCallbackRequest,
    _generate_magic_link_signature,
    _verify_magic_link_signature,
    check_email_conflict,
    get_merge_status_endpoint,
    get_oauth_urls,
    get_session_info,
    handle_oauth_callback,
    link_accounts,
    refresh_access_tokens,
    request_magic_link,
    sign_out,
    verify_magic_link,
)
from src.lambdas.shared.errors.session_errors import (
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from src.lambdas.shared.models.user import User


class TestMagicLinkSignature:
    """Tests for magic link signature generation/verification."""

    def test_generate_signature(self):
        """Generates consistent HMAC signature."""
        sig1 = _generate_magic_link_signature("token123", "user@example.com")
        sig2 = _generate_magic_link_signature("token123", "user@example.com")

        assert sig1 == sig2
        assert len(sig1) == 64  # SHA256 hex length

    def test_different_inputs_different_signature(self):
        """Different inputs produce different signatures."""
        sig1 = _generate_magic_link_signature("token123", "user@example.com")
        sig2 = _generate_magic_link_signature("token456", "user@example.com")

        assert sig1 != sig2

    def test_verify_valid_signature(self):
        """Verifies valid signature returns True."""
        sig = _generate_magic_link_signature("token123", "user@example.com")
        result = _verify_magic_link_signature("token123", "user@example.com", sig)

        assert result is True

    def test_verify_invalid_signature(self):
        """Verifies invalid signature returns False."""
        result = _verify_magic_link_signature(
            "token123", "user@example.com", "invalid_sig"
        )

        assert result is False


class TestRequestMagicLink:
    """Tests for T090: request_magic_link."""

    def test_creates_token_and_stores(self):
        """Creates token and stores in DynamoDB."""
        table = MagicMock()
        table.query.return_value = {"Items": []}
        table.put_item.return_value = {}

        request = MagicLinkRequest(email="test@example.com")

        response = request_magic_link(table, request)

        assert response.status == "email_sent"
        assert response.email == "test@example.com"
        assert response.expires_in_seconds == 3600

        # Verify put_item was called
        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        assert item["email"] == "test@example.com"
        assert item["entity_type"] == "MAGIC_LINK_TOKEN"

    def test_invalidates_existing_tokens(self):
        """Invalidates any existing tokens for the email.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        # Mock GSI query response for by_email GSI
        table.query.return_value = {
            "Items": [
                {"PK": "TOKEN#old1", "SK": "MAGIC_LINK", "email": "test@example.com"}
            ]
        }
        table.put_item.return_value = {}
        table.update_item.return_value = {}

        request = MagicLinkRequest(email="test@example.com")
        request_magic_link(table, request)

        # Should have called update_item to invalidate old token
        table.update_item.assert_called()

    def test_includes_anonymous_user_id(self):
        """Stores anonymous user ID for merge.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        table.query.return_value = {"Items": []}
        table.put_item.return_value = {}

        anon_id = str(uuid.uuid4())
        request = MagicLinkRequest(email="test@example.com", anonymous_user_id=anon_id)

        request_magic_link(table, request)

        item = table.put_item.call_args.kwargs["Item"]
        assert item["anonymous_user_id"] == anon_id


class TestVerifyMagicLink:
    """Tests for T091: verify_magic_link."""

    def test_verify_valid_token(self):
        """Verifies valid token and creates session.

        Feature 1129: verify_magic_link now uses atomic token consumption.
        Signature parameter removed - tokens are validated by UUID only.
        """
        table = MagicMock()
        token_id = str(uuid.uuid4())
        email = "test@example.com"
        now = datetime.now(UTC)

        # Token in database
        table.get_item.return_value = {
            "Item": {
                "token_id": token_id,
                "email": email,
                "signature": "legacy-sig",  # No longer used for validation
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "used": False,
            }
        }
        table.update_item.return_value = {}
        # Mock GSI query for by_email GSI (502-gsi-query-optimization)
        table.query.return_value = {"Items": []}
        table.put_item.return_value = {}

        # Feature 1129: New signature - no signature param, optional client_ip
        response = verify_magic_link(table, token_id)

        assert response.status == "verified"
        # email is now masked for security
        assert response.email_masked == "t***@example.com"
        assert response.auth_type == "email"
        assert response.tokens is not None
        # refresh_token is now separated for HttpOnly cookie
        assert response.refresh_token_for_cookie is not None

    def test_verify_used_token(self):
        """Rejects already used token with TokenAlreadyUsedError.

        Feature 1129: verify_magic_link now raises exceptions instead
        of returning error response objects. Router handles conversion
        to HTTP 409 Conflict.
        """
        table = MagicMock()
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        table.get_item.return_value = {
            "Item": {
                "token_id": token_id,
                "email": "test@example.com",
                "signature": "sig",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "used": True,  # Already used
            }
        }

        # Feature 1129: Now raises TokenAlreadyUsedError
        with pytest.raises(TokenAlreadyUsedError) as exc_info:
            verify_magic_link(table, token_id)

        assert exc_info.value.token_id == token_id

    def test_verify_expired_token(self):
        """Rejects expired token with TokenExpiredError.

        Feature 1129: verify_magic_link now raises exceptions instead
        of returning error response objects. Router handles conversion
        to HTTP 410 Gone.
        """
        table = MagicMock()
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        table.get_item.return_value = {
            "Item": {
                "token_id": token_id,
                "email": "test@example.com",
                "signature": "sig",
                "created_at": (now - timedelta(hours=2)).isoformat(),
                "expires_at": (now - timedelta(hours=1)).isoformat(),  # Expired
                "used": False,
            }
        }

        # Feature 1129: Now raises TokenExpiredError
        with pytest.raises(TokenExpiredError) as exc_info:
            verify_magic_link(table, token_id)

        assert exc_info.value.token_id == token_id

    def test_verify_nonexistent_token(self):
        """Rejects nonexistent token."""
        table = MagicMock()
        table.get_item.return_value = {}

        # Feature 1129: Nonexistent tokens still return error response
        response = verify_magic_link(table, "nonexistent")

        assert response.status == "invalid"
        assert response.error == "token_not_found"


class TestGetOAuthUrls:
    """Tests for T092: get_oauth_urls."""

    def test_returns_provider_urls(self):
        """Returns OAuth URLs for all providers."""
        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            response = get_oauth_urls()

            assert "google" in response.providers
            assert "github" in response.providers
            assert "authorize_url" in response.providers["google"]
            assert "icon" in response.providers["google"]
            assert response.providers["google"]["icon"] == "google"


class TestHandleOAuthCallback:
    """Tests for T093: handle_oauth_callback."""

    def test_successful_new_user(self):
        """Creates new user on successful OAuth.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        table.query.return_value = {"Items": []}  # No existing user (by_email GSI)
        table.put_item.return_value = {}
        table.update_item.return_value = {}

        mock_tokens = MagicMock()
        mock_tokens.id_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.sig"
        mock_tokens.access_token = "access_token"
        mock_tokens.refresh_token = "refresh_token"
        mock_tokens.expires_in = 3600

        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            with patch(
                "src.lambdas.dashboard.auth.exchange_code_for_tokens",
                return_value=mock_tokens,
            ):
                request = OAuthCallbackRequest(code="auth_code", provider="google")

                response = handle_oauth_callback(table, request)

                assert response.status == "authenticated"
                assert response.is_new_user is True

    def test_existing_user_different_provider_conflict(self):
        """Returns conflict when email exists with different provider.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        existing_user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub=None,
            auth_type="email",  # Different from google
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        table.query.return_value = {"Items": [existing_user.to_dynamodb_item()]}

        mock_tokens = MagicMock()
        mock_tokens.id_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.sig"

        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            with patch(
                "src.lambdas.dashboard.auth.exchange_code_for_tokens",
                return_value=mock_tokens,
            ):
                request = OAuthCallbackRequest(code="auth_code", provider="google")

                response = handle_oauth_callback(table, request)

                assert response.status == "conflict"
                assert response.conflict is True
                assert response.existing_provider == "email"


class TestRefreshAccessTokens:
    """Tests for T094: refresh_access_tokens."""

    def test_refresh_success(self):
        """Returns new tokens on success."""
        mock_tokens = MagicMock()
        mock_tokens.id_token = "new_id_token"
        mock_tokens.access_token = "new_access_token"
        mock_tokens.expires_in = 3600

        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            with patch(
                "src.lambdas.dashboard.auth.cognito_refresh_tokens",
                return_value=mock_tokens,
            ):
                response = refresh_access_tokens("refresh_token")

                assert response.id_token == "new_id_token"
                assert response.access_token == "new_access_token"

    def test_refresh_failure(self):
        """Returns error on failure."""
        from src.lambdas.shared.auth.cognito import TokenError

        with patch.dict(
            os.environ,
            {
                "COGNITO_USER_POOL_ID": "us-east-1_ABC123",
                "COGNITO_CLIENT_ID": "client123",
                "COGNITO_DOMAIN": "myapp",
                "AWS_REGION": "us-east-1",
                "COGNITO_REDIRECT_URI": "https://app.example.com/callback",
            },
        ):
            with patch(
                "src.lambdas.dashboard.auth.cognito_refresh_tokens",
                side_effect=TokenError(
                    "invalid_refresh_token", "Please sign in again."
                ),
            ):
                response = refresh_access_tokens("bad_token")

                assert response.error == "invalid_refresh_token"


class TestSignOut:
    """Tests for T095: sign_out."""

    def test_sign_out_returns_success(self):
        """Returns success response and invalidates session."""
        table = MagicMock()
        table.update_item.return_value = {}
        user_id = str(uuid.uuid4())

        response = sign_out(table, user_id, "access_token")

        assert response.status == "signed_out"
        assert "this device" in response.message.lower()

        # Verify session was invalidated
        table.update_item.assert_called_once()
        call_args = table.update_item.call_args
        assert f"USER#{user_id}" in call_args.kwargs["Key"]["PK"]


class TestGetSessionInfo:
    """Tests for T096: get_session_info."""

    def test_returns_session_info(self):
        """Returns session info for valid user."""
        table = MagicMock()
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        user = User(
            user_id=user_id,
            email="test@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=now - timedelta(days=1),
            last_active_at=now,
            session_expires_at=now + timedelta(days=29),
        )

        table.get_item.return_value = {"Item": user.to_dynamodb_item()}

        response = get_session_info(table, user_id)

        assert response is not None
        # Security: user_id no longer in response (frontend has it in header)
        # email is now masked
        assert response.email_masked == "t***@example.com"
        assert response.auth_type == "google"
        # Relative time instead of absolute timestamp
        assert response.session_expires_in_seconds > 0

    def test_returns_none_for_missing_user(self):
        """Returns None for nonexistent user."""
        table = MagicMock()
        table.get_item.return_value = {}

        response = get_session_info(table, str(uuid.uuid4()))

        assert response is None


class TestCheckEmailConflict:
    """Tests for T097: check_email_conflict."""

    def test_no_conflict_new_email(self):
        """Returns no conflict for new email.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        table.query.return_value = {"Items": []}  # by_email GSI

        request = CheckEmailRequest(email="new@example.com", current_provider="google")
        response = check_email_conflict(table, request)

        assert response.conflict is False

    def test_no_conflict_same_provider(self):
        """Returns no conflict if same provider.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        table.query.return_value = {"Items": [user.to_dynamodb_item()]}

        request = CheckEmailRequest(email="test@example.com", current_provider="google")
        response = check_email_conflict(table, request)

        assert response.conflict is False

    def test_conflict_different_provider(self):
        """Returns conflict for different provider.

        (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
        """
        table = MagicMock()
        user = User(
            user_id=str(uuid.uuid4()),
            email="test@example.com",
            cognito_sub=None,
            auth_type="email",
            created_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
            session_expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        table.query.return_value = {"Items": [user.to_dynamodb_item()]}

        request = CheckEmailRequest(email="test@example.com", current_provider="google")
        response = check_email_conflict(table, request)

        assert response.conflict is True
        assert response.existing_provider == "email"


class TestLinkAccounts:
    """Tests for T098: link_accounts."""

    def test_link_success(self):
        """Links accounts successfully."""
        table = MagicMock()
        current_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        current_user = User(
            user_id=current_id,
            email="current@example.com",
            cognito_sub=None,
            auth_type="google",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )
        target_user = User(
            user_id=target_id,
            email="target@example.com",
            cognito_sub=None,
            auth_type="email",
            created_at=now,
            last_active_at=now,
            session_expires_at=now + timedelta(days=30),
        )

        def get_item_side_effect(**kwargs):
            pk = kwargs["Key"]["PK"]
            if current_id in pk:
                return {"Item": current_user.to_dynamodb_item()}
            if target_id in pk:
                return {"Item": target_user.to_dynamodb_item()}
            return {}

        table.get_item.side_effect = get_item_side_effect

        # Setup query to return items to merge
        def query_side_effect(**kwargs):
            pk = kwargs.get("ExpressionAttributeValues", {}).get(":pk", "")
            if current_id in pk:
                # Current user has a configuration to merge
                sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                    ":sk_prefix", ""
                )
                if sk_prefix == "CONFIG#":
                    return {
                        "Items": [
                            {
                                "PK": f"USER#{current_id}",
                                "SK": "CONFIG#1",
                                "entity_type": "CONFIGURATION",
                            }
                        ]
                    }
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        request = LinkAccountsRequest(link_to_user_id=target_id, confirmation=True)
        response = link_accounts(table, current_id, request)

        assert response.status == "linked"
        assert target_id in response.user_id

    def test_link_requires_confirmation(self):
        """Rejects link without confirmation."""
        table = MagicMock()

        request = LinkAccountsRequest(link_to_user_id="target_id", confirmation=False)
        response = link_accounts(table, "current_id", request)

        assert response.status == "error"
        assert response.error == "confirmation_required"


class TestGetMergeStatusEndpoint:
    """Tests for T099: get_merge_status_endpoint."""

    def test_completed_merge(self):
        """Returns completed status with counts."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{anon_id}",
                "SK": "PROFILE",
                "merged_to": auth_id,
                "merged_at": datetime.now(UTC).isoformat(),
            }
        }

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {
                    "Items": [{"merged_from": anon_id, "entity_type": "CONFIGURATION"}]
                }
            return {"Items": []}

        table.query.side_effect = query_side_effect

        response = get_merge_status_endpoint(table, auth_id, anon_id)

        assert response.status == "completed"
        assert response.items_merged is not None
        assert response.items_merged["configurations"] == 1

    def test_no_data_to_merge(self):
        """Returns no_data when nothing to merge."""
        table = MagicMock()
        table.get_item.return_value = {}

        response = get_merge_status_endpoint(table, "auth_id", "anon_id")

        assert response.status == "no_data"
