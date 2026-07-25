# Target: Admin Dashboard (Lambda HTMX) backend — Feature 1396 refresh re-mint
"""Feature 1396: the Cognito-backed refresh branch re-mints a fresh app JWT (FR-005),
fails closed on unresolved identity (FR-006 / N3), and enforces refresh-time revocation
(N1/FR-008). Transient infra faults keep 1395's IdentityLookupError → 503 posture.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard import auth as auth_mod
from src.lambdas.dashboard.auth import (
    IdentityLookupError,
    mint_app_jwt,
    refresh_access_tokens,
)
from src.lambdas.shared.auth.cognito import CognitoTokens
from src.lambdas.shared.middleware.auth_middleware import validate_jwt
from src.lambdas.shared.models.user import User

_SECRET = "unit-test-app-jwt-secret-not-prod"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)


def _user(revocation_id: int = 0) -> User:
    now = datetime.now(UTC)
    return User(
        user_id="user-oauth-1",
        email="u@example.com",
        auth_type="google",
        role="free",
        verification="verified",
        revocation_id=revocation_id,
        cognito_sub="cog-sub-1",
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


def _cognito_tokens() -> CognitoTokens:
    return CognitoTokens(
        id_token="header.payload.sig",
        access_token="raw-cognito-access-token",
        refresh_token=None,
        expires_in=3600,
    )


def _patched(user_or_exc, sub="cog-sub-1"):
    """Patch the refresh dependencies. user_or_exc: a User, None, or an Exception type
    to raise from get_user_by_cognito_sub."""
    p_block = patch.object(auth_mod, "is_token_blocklisted", return_value=False)
    p_cfg = patch.object(auth_mod.CognitoConfig, "from_env", return_value=MagicMock())
    p_refresh = patch.object(
        auth_mod, "cognito_refresh_tokens", return_value=_cognito_tokens()
    )
    p_decode = patch.object(auth_mod, "decode_id_token", return_value={"sub": sub})
    if isinstance(user_or_exc, type) and issubclass(user_or_exc, Exception):
        p_lookup = patch.object(
            auth_mod, "get_user_by_cognito_sub", side_effect=user_or_exc("boom")
        )
    else:
        p_lookup = patch.object(
            auth_mod, "get_user_by_cognito_sub", return_value=user_or_exc
        )
    return p_block, p_cfg, p_refresh, p_decode, p_lookup


class TestReMint:
    def test_remint_passes_validate_jwt(self):
        patches = _patched(_user())
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens("cognito-refresh-tok", table=MagicMock())
        assert result.error is None
        # Not the raw Cognito access token.
        assert result.access_token != "raw-cognito-access-token"
        assert result.expires_in == 900
        assert result.user_id == "user-oauth-1"
        claim = validate_jwt(result.access_token)
        assert claim is not None
        assert claim.subject == "user-oauth-1"
        assert claim.roles == ["free"]


class TestFailClosedIdentity:
    def test_no_sub_is_definitive_401(self):
        patches = _patched(_user(), sub=None)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens("tok", table=MagicMock())
        assert result.error == "identity_unresolved"
        assert result.access_token is None

    def test_deterministic_none_is_definitive_401(self):
        patches = _patched(None)  # get_user_by_cognito_sub returns None
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens("tok", table=MagicMock())
        assert result.error == "identity_unresolved"
        assert result.access_token is None

    def test_transient_lookup_fault_propagates_as_identity_lookup_error(self):
        # 1395/N3: an infra fault surfaces as IdentityLookupError (not a TokenError),
        # which the app-level handler maps to a retryable 503 (session preserved) —
        # NOT collapsed to a session-dropping 401.
        patches = _patched(IdentityLookupError)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with pytest.raises(IdentityLookupError):
                refresh_access_tokens("tok", table=MagicMock())


class TestRefreshTimeRevocation:
    def test_matching_rev_remints(self):
        user = _user(revocation_id=0)
        bearer = "Bearer " + mint_app_jwt(user)  # rev=0
        patches = _patched(user)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens(
                "tok", table=MagicMock(), incoming_bearer=bearer
            )
        assert result.error is None
        assert result.access_token is not None

    def test_advanced_rev_refuses_remint(self):
        # Client holds a bearer minted at rev=0; the user's revocation_id has since
        # advanced to 5 (force revocation) → refresh must refuse.
        stale_bearer = "Bearer " + mint_app_jwt(_user(revocation_id=0))
        current_user = _user(revocation_id=5)
        patches = _patched(current_user)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens(
                "tok", table=MagicMock(), incoming_bearer=stale_bearer
            )
        assert result.error == "session_revoked"
        assert result.access_token is None

    def test_absent_bearer_skips_check_and_remints(self):
        current_user = _user(revocation_id=5)
        patches = _patched(current_user)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens(
                "tok", table=MagicMock(), incoming_bearer=None
            )
        # Migration-window backward-compat: no bearer → check skipped → still re-mints.
        assert result.error is None
        assert result.access_token is not None

    def test_invalid_signature_bearer_skips_check(self):
        current_user = _user(revocation_id=5)
        patches = _patched(current_user)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = refresh_access_tokens(
                "tok", table=MagicMock(), incoming_bearer="Bearer garbage.token.value"
            )
        assert result.error is None
        assert result.access_token is not None
