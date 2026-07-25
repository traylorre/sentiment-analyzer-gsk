# Target: Admin Dashboard (Lambda HTMX) backend — Feature 1396 app-JWT mint
"""Feature 1396: mint_app_jwt produces a first-party HS256 app JWT that the API
middleware's validate_jwt accepts, replacing the raw Cognito access token that the
middleware never validated (the M1 401 storm).

TDD security properties covered:
- round-trip through validate_jwt (FR-007, SC-001)
- roles are the LITERAL expected list per user state (N4/FR-002a, de-tautologized)
- N4 regression: an un-reconciled just-upgraded user under-grants ["anonymous"]
- rev == user.revocation_id (FR-008); exp-iat==900; nbf==iat; jti fresh (FR-002/003)
- iss default match with JWT_ISSUER unset (AR1-8)
- alg pinned HS256; alg:none and wrong-key rejected by validate_jwt (FR-009, T2)
- JWT_SECRET unset → mint raises (fail closed, FR-006)
- regression lock: a raw Cognito-style bearer is rejected by validate_jwt (SC-002)
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.lambdas.dashboard.auth import (
    APP_JWT_TTL_SECONDS,
    mint_app_jwt,
)
from src.lambdas.shared.middleware.auth_middleware import validate_jwt
from src.lambdas.shared.models.user import User

_SECRET = "unit-test-app-jwt-secret-not-prod"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    """Configure a signing secret; leave JWT_ISSUER/JWT_AUDIENCE unset so mint and
    validate both fall back to the default issuer 'sentiment-analyzer' and no aud."""
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)


def _user(
    *,
    user_id: str = "user-123",
    auth_type: str = "google",
    role: str = "free",
    verification: str = "verified",
    revocation_id: int = 0,
    subscription_active: bool = False,
    is_operator: bool = False,
) -> User:
    now = datetime.now(UTC)
    return User(
        user_id=user_id,
        email="u@example.com",
        auth_type=auth_type,
        role=role,
        verification=verification,
        revocation_id=revocation_id,
        subscription_active=subscription_active,
        is_operator=is_operator,
        created_at=now,
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
    )


class TestMintRoundTrip:
    def test_minted_token_passes_validate_jwt(self):
        user = _user(user_id="user-abc", revocation_id=3)
        token = mint_app_jwt(user)

        claim = validate_jwt(token)
        assert claim is not None
        assert claim.subject == "user-abc"
        assert claim.roles == ["free"]
        assert claim.rev == 3
        assert claim.jti  # present

    def test_header_alg_is_hs256(self):
        token = mint_app_jwt(_user())
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"


class TestRolesLiteralPerState:
    """N4 (de-tautologized): assert LITERAL role lists, not == get_roles_for_user()."""

    def test_new_oauth_user_is_free(self):
        claim = validate_jwt(mint_app_jwt(_user(auth_type="google", role="free")))
        assert claim.roles == ["free"]

    def test_unreconciled_anonymous_is_anonymous(self):
        # role="anonymous" requires verification != verified to satisfy the model.
        user = _user(auth_type="anonymous", role="anonymous", verification="none")
        claim = validate_jwt(mint_app_jwt(user))
        assert claim.roles == ["anonymous"]

    def test_paid_user_is_free_paid(self):
        user = _user(role="paid", subscription_active=True)
        claim = validate_jwt(mint_app_jwt(user))
        assert claim.roles == ["free", "paid"]

    def test_operator_user_is_free_paid_operator(self):
        user = _user(role="operator", is_operator=True)
        claim = validate_jwt(mint_app_jwt(user))
        assert claim.roles == ["free", "paid", "operator"]

    def test_n4_regression_unreconciled_upgraded_user_undergrants(self):
        """Locks the N4 fix: minting from a just-upgraded user whose in-memory
        auth_type is STILL 'anonymous' under-grants ['anonymous']. After the caller
        reconciles auth_type to the provider, roles correctly become ['free']."""
        upgraded = _user(auth_type="anonymous", role="anonymous", verification="none")

        # Un-reconciled: get_roles_for_user gates on auth_type → under-grant.
        assert validate_jwt(mint_app_jwt(upgraded)).roles == ["anonymous"]

        # Reconcile (what handle_oauth_callback does before minting).
        upgraded.auth_type = "google"
        upgraded.role = "free"
        assert validate_jwt(mint_app_jwt(upgraded)).roles == ["free"]


class TestClaims:
    def test_ttl_and_nbf(self):
        fixed = datetime(2026, 1, 1, tzinfo=UTC)
        token = mint_app_jwt(_user(), now=fixed)
        payload = jwt.decode(
            token,
            _SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": False},
        )
        assert payload["exp"] - payload["iat"] == APP_JWT_TTL_SECONDS == 900
        assert payload["nbf"] == payload["iat"]

    def test_jti_is_fresh_across_mints(self):
        u = _user()
        p1 = jwt.decode(
            mint_app_jwt(u),
            _SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        p2 = jwt.decode(
            mint_app_jwt(u),
            _SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        assert p1["jti"] != p2["jti"]

    def test_iss_default_matches_validator(self):
        payload = jwt.decode(
            mint_app_jwt(_user()),
            _SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        assert payload["iss"] == "sentiment-analyzer"


class TestAudienceMatch:
    def test_aud_included_and_validated_when_set(self, monkeypatch):
        monkeypatch.setenv("JWT_AUDIENCE", "sentiment-api")
        token = mint_app_jwt(_user())
        # validate_jwt reads JWT_AUDIENCE from the same env → must accept.
        assert validate_jwt(token) is not None
        payload = jwt.decode(
            token, _SECRET, algorithms=["HS256"], audience="sentiment-api"
        )
        assert payload["aud"] == "sentiment-api"

    def test_aud_mismatch_rejected(self, monkeypatch):
        monkeypatch.setenv("JWT_AUDIENCE", "sentiment-api")
        token = mint_app_jwt(_user())
        # A validator expecting a DIFFERENT audience must reject.
        monkeypatch.setenv("JWT_AUDIENCE", "some-other-aud")
        assert validate_jwt(token) is None


class TestAlgorithmConfusion:
    def test_alg_none_rejected(self):
        payload = {
            "sub": "user-1",
            "iss": "sentiment-analyzer",
            "iat": int(datetime.now(UTC).timestamp()),
            "nbf": int(datetime.now(UTC).timestamp()),
            "exp": int(datetime.now(UTC).timestamp()) + 900,
            "roles": ["operator"],
        }
        forged = jwt.encode(payload, None, algorithm="none")
        assert validate_jwt(forged) is None

    def test_wrong_key_rejected(self):
        payload = {
            "sub": "user-1",
            "iss": "sentiment-analyzer",
            "iat": int(datetime.now(UTC).timestamp()),
            "nbf": int(datetime.now(UTC).timestamp()),
            "exp": int(datetime.now(UTC).timestamp()) + 900,
            "roles": ["operator"],
        }
        forged = jwt.encode(payload, "attacker-key", algorithm="HS256")
        assert validate_jwt(forged) is None


class TestFailClosed:
    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            mint_app_jwt(_user())


class TestRegressionLock:
    def test_raw_cognito_style_bearer_rejected(self):
        # SC-002: a non-app-JWT string (e.g. a raw Cognito access token) must NOT
        # validate — proves the fix and prevents reverting to the broken state.
        assert validate_jwt("not-a-jwt-cognito-access-token") is None
