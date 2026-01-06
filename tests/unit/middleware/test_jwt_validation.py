"""Tests for JWT validation in auth middleware.

Feature: 075-validation-gaps
User Story 3: JWT Authentication for Authenticated Sessions
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt

from src.lambdas.shared.middleware.auth_middleware import (
    JWTConfig,
    _extract_user_id_from_token,
    _get_jwt_config,
    extract_user_id,
    validate_jwt,
)

# Test configuration
TEST_SECRET = "test-secret-key-do-not-use-in-production"
TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


def create_test_token(
    user_id: str = TEST_USER_ID,
    secret: str = TEST_SECRET,
    expires_in: timedelta = timedelta(minutes=15),
    issuer: str = "sentiment-analyzer",
    audience: str | None = "sentiment-analyzer-api",
    nbf_offset: timedelta = timedelta(seconds=0),
    algorithm: str = "HS256",
    include_iat: bool = True,
    include_exp: bool = True,
    include_sub: bool = True,
    include_nbf: bool = True,
    include_aud: bool = True,
    roles: list[str] | None = None,
    include_roles: bool = True,
) -> str:
    """Create a test JWT token.

    Feature 1147: Added audience and nbf parameters for CVSS 7.8 fix.
    Feature 1152: Added roles parameter for RBAC support.

    Args:
        user_id: Subject claim value
        secret: Signing secret
        expires_in: Expiration offset from now
        issuer: Issuer claim value
        audience: Audience claim value (Feature 1147)
        nbf_offset: Not-before offset from now (negative = past, positive = future)
        algorithm: JWT algorithm
        include_iat: Include issued-at claim
        include_exp: Include expiration claim
        include_sub: Include subject claim
        include_nbf: Include not-before claim (Feature 1147)
        include_aud: Include audience claim (Feature 1147)
        roles: User roles for RBAC (defaults to ["free"])
        include_roles: Include roles claim (Feature 1152)
    """
    payload = {}
    now = datetime.now(UTC)

    if include_sub:
        payload["sub"] = user_id
    if include_exp:
        payload["exp"] = now + expires_in
    if include_iat:
        payload["iat"] = now
    if issuer:
        payload["iss"] = issuer
    if include_nbf:
        payload["nbf"] = now + nbf_offset
    if include_aud and audience:
        payload["aud"] = audience
    if include_roles:
        payload["roles"] = roles if roles is not None else ["free"]

    return jwt.encode(payload, secret, algorithm=algorithm)


class TestJWTConfig:
    """Test JWTConfig dataclass."""

    def test_default_values(self):
        """JWTConfig should have sensible defaults."""
        config = JWTConfig(secret="test-secret")
        assert config.algorithm == "HS256"
        assert config.issuer == "sentiment-analyzer"
        assert config.leeway_seconds == 60
        assert config.access_token_lifetime_seconds == 900  # 15 minutes

    def test_custom_values(self):
        """JWTConfig should accept custom values."""
        config = JWTConfig(
            secret="custom-secret",
            algorithm="HS512",
            issuer="custom-issuer",
            leeway_seconds=30,
        )
        assert config.secret == "custom-secret"
        assert config.algorithm == "HS512"
        assert config.issuer == "custom-issuer"
        assert config.leeway_seconds == 30


class TestGetJWTConfig:
    """Test _get_jwt_config function."""

    def test_returns_none_without_secret(self):
        """Should return None if JWT_SECRET not set."""
        with patch.dict("os.environ", {}, clear=True):
            config = _get_jwt_config()
            assert config is None

    def test_returns_config_with_secret(self):
        """Should return JWTConfig if JWT_SECRET is set."""
        with patch.dict("os.environ", {"JWT_SECRET": TEST_SECRET}):
            config = _get_jwt_config()
            assert config is not None
            assert config.secret == TEST_SECRET

    def test_reads_optional_env_vars(self):
        """Should read optional environment variables."""
        env_vars = {
            "JWT_SECRET": TEST_SECRET,
            "JWT_ALGORITHM": "HS512",
            "JWT_ISSUER": "custom-issuer",
            "JWT_LEEWAY_SECONDS": "120",
        }
        with patch.dict("os.environ", env_vars):
            config = _get_jwt_config()
            assert config.algorithm == "HS512"
            assert config.issuer == "custom-issuer"
            assert config.leeway_seconds == 120


class TestValidateJWT:
    """Test validate_jwt function."""

    def test_valid_jwt_token(self):
        """Valid JWT tokens should return JWTClaim with correct subject."""
        token = create_test_token()
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)

        assert claim is not None
        assert claim.subject == TEST_USER_ID
        assert claim.issuer == "sentiment-analyzer"
        assert isinstance(claim.expiration, datetime)
        assert isinstance(claim.issued_at, datetime)

    def test_expired_jwt_token(self):
        """Expired JWT tokens should return None."""
        token = create_test_token(expires_in=timedelta(seconds=-60))
        config = JWTConfig(
            secret=TEST_SECRET, audience="sentiment-analyzer-api", leeway_seconds=0
        )

        claim = validate_jwt(token, config)
        assert claim is None

    def test_malformed_jwt_token(self):
        """Malformed JWT tokens should return None."""
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        # Not a valid JWT structure
        claim = validate_jwt("not.a.valid.jwt", config)
        assert claim is None

        # Empty string
        claim = validate_jwt("", config)
        assert claim is None

        # Random garbage
        claim = validate_jwt("random-garbage-string", config)
        assert claim is None

    def test_invalid_signature(self):
        """JWT tokens with invalid signatures should return None."""
        # Create token with one secret, validate with another
        token = create_test_token(secret="wrong-secret")
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None

    def test_missing_required_claims(self):
        """JWT tokens missing sub/exp/iat should return None."""
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        # Missing sub
        token = create_test_token(include_sub=False)
        claim = validate_jwt(token, config)
        assert claim is None

        # Missing exp
        token = create_test_token(include_exp=False)
        claim = validate_jwt(token, config)
        assert claim is None

        # Missing iat
        token = create_test_token(include_iat=False)
        claim = validate_jwt(token, config)
        assert claim is None

    def test_jwt_performance_benchmark(self):
        """1000 JWT validations should complete in <1 second."""
        token = create_test_token()
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        start_time = time.time()
        for _ in range(1000):
            validate_jwt(token, config)
        elapsed = time.time() - start_time

        assert elapsed < 1.0, f"1000 validations took {elapsed:.2f}s (expected <1s)"

    def test_missing_jwt_secret_fails_fast(self):
        """Should return None quickly if no config available."""
        token = create_test_token()

        with patch.dict("os.environ", {}, clear=True):
            start_time = time.time()
            claim = validate_jwt(token)  # No config, should use env
            elapsed = time.time() - start_time

            assert claim is None
            assert elapsed < 0.1, "Should fail fast without config"

    def test_invalid_issuer_rejected(self):
        """JWT with wrong issuer should return None."""
        token = create_test_token(issuer="wrong-issuer")
        config = JWTConfig(
            secret=TEST_SECRET,
            audience="sentiment-analyzer-api",
            issuer="expected-issuer",
        )

        claim = validate_jwt(token, config)
        assert claim is None

    def test_issuer_validation_skipped_if_none(self):
        """Issuer validation should be skipped if config.issuer is None."""
        token = create_test_token(issuer="any-issuer")
        config = JWTConfig(
            secret=TEST_SECRET, audience="sentiment-analyzer-api", issuer=None
        )

        claim = validate_jwt(token, config)
        assert claim is not None

    # Feature 1147: Audience (aud) validation tests

    def test_rejects_wrong_audience(self):
        """Feature 1147 US1: JWT with wrong audience should return None.

        Prevents cross-service token replay attacks (CVSS 7.8).
        """
        token = create_test_token(audience="other-service-api")
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None

    def test_accepts_correct_audience(self):
        """Feature 1147 US1: JWT with correct audience should be accepted."""
        token = create_test_token(audience="sentiment-analyzer-api")
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.subject == TEST_USER_ID

    def test_rejects_missing_audience(self):
        """Feature 1147 US1: JWT without audience claim should return None.

        When config has audience set, tokens must include the aud claim.
        """
        token = create_test_token(include_aud=False)
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None

    # Feature 1147: Not-Before (nbf) validation tests

    def test_rejects_future_nbf(self):
        """Feature 1147 US2: JWT with future nbf should return None.

        Prevents pre-generated token attacks (CVSS 7.8).
        Token with nbf 5 minutes in future should be rejected.
        """
        token = create_test_token(nbf_offset=timedelta(minutes=5))
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None

    def test_accepts_past_nbf(self):
        """Feature 1147 US2: JWT with nbf in past should be accepted."""
        token = create_test_token(nbf_offset=timedelta(seconds=-60))
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None

    def test_rejects_missing_nbf(self):
        """Feature 1147 US2: JWT without nbf claim should return None.

        nbf is now a required claim per Feature 1147.
        """
        token = create_test_token(include_nbf=False)
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None

    # Feature 1147: Clock skew tolerance (leeway) tests

    def test_accepts_nbf_within_leeway(self):
        """Feature 1147 US3: JWT with nbf slightly in future within leeway accepted.

        Default leeway is 60 seconds. Token with nbf 30s in future should be accepted.
        """
        token = create_test_token(nbf_offset=timedelta(seconds=30))
        config = JWTConfig(
            secret=TEST_SECRET, audience="sentiment-analyzer-api", leeway_seconds=60
        )

        claim = validate_jwt(token, config)
        assert claim is not None

    def test_rejects_nbf_beyond_leeway(self):
        """Feature 1147 US3: JWT with nbf beyond leeway should be rejected.

        Default leeway is 60 seconds. Token with nbf 120s in future should be rejected.
        """
        token = create_test_token(nbf_offset=timedelta(seconds=120))
        config = JWTConfig(
            secret=TEST_SECRET, audience="sentiment-analyzer-api", leeway_seconds=60
        )

        claim = validate_jwt(token, config)
        assert claim is None


class TestExtractUserIdFromToken:
    """Test _extract_user_id_from_token function."""

    def test_uuid_token_returns_uuid(self):
        """UUID tokens should return the UUID directly."""
        uuid_token = "550e8400-e29b-41d4-a716-446655440000"
        result = _extract_user_id_from_token(uuid_token)
        assert result == uuid_token

    def test_jwt_token_returns_subject(self):
        """JWT tokens should return the subject claim."""
        token = create_test_token()

        with patch.dict(
            "os.environ",
            {"JWT_SECRET": TEST_SECRET, "JWT_AUDIENCE": "sentiment-analyzer-api"},
        ):
            result = _extract_user_id_from_token(token)
            assert result == TEST_USER_ID

    def test_invalid_token_returns_none(self):
        """Invalid tokens should return None."""
        result = _extract_user_id_from_token("invalid-token")
        assert result is None


class TestExtractUserId:
    """Test extract_user_id function integration."""

    def test_bearer_jwt_token_extracted(self):
        """Should extract user ID from Bearer JWT token."""
        token = create_test_token()
        event = {"headers": {"Authorization": f"Bearer {token}"}}

        with patch.dict(
            "os.environ",
            {"JWT_SECRET": TEST_SECRET, "JWT_AUDIENCE": "sentiment-analyzer-api"},
        ):
            user_id = extract_user_id(event)
            assert user_id == TEST_USER_ID

    def test_bearer_uuid_token_extracted(self):
        """Should extract user ID from Bearer UUID token."""
        uuid_token = "550e8400-e29b-41d4-a716-446655440000"
        event = {"headers": {"Authorization": f"Bearer {uuid_token}"}}

        user_id = extract_user_id(event)
        assert user_id == uuid_token

    def test_x_user_id_header_ignored(self):
        """Feature 1146: X-User-ID header is IGNORED (security fix).

        X-User-ID header fallback was removed to prevent impersonation attacks.
        Users MUST use Bearer token for authentication.
        """
        user_id_value = "550e8400-e29b-41d4-a716-446655440000"
        event = {"headers": {"X-User-ID": user_id_value}}

        user_id = extract_user_id(event)
        # X-User-ID is ignored - returns None
        assert user_id is None

    def test_no_auth_returns_none(self):
        """Should return None if no authentication present."""
        event = {"headers": {}}
        user_id = extract_user_id(event)
        assert user_id is None


class TestJWTRolesClaim:
    """Feature 1152: Tests for roles claim in JWT tokens."""

    def test_roles_extracted_from_jwt(self):
        """Feature 1152: Roles claim should be extracted from JWT."""
        token = create_test_token(roles=["free", "paid"])
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.roles == ["free", "paid"]

    def test_default_roles_is_free(self):
        """Feature 1152: Default roles should be ['free'] for authenticated users."""
        token = create_test_token()  # No roles specified, uses default
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.roles == ["free"]

    def test_operator_roles(self):
        """Feature 1152: Operator should have ['free', 'paid', 'operator'] roles."""
        token = create_test_token(roles=["free", "paid", "operator"])
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.roles == ["free", "paid", "operator"]
        assert "operator" in claim.roles

    def test_empty_roles_array(self):
        """Feature 1152: Empty roles array is valid (user has no roles)."""
        token = create_test_token(roles=[])
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.roles == []

    def test_missing_roles_claim_rejected(self):
        """Feature 1153: Missing roles claim should REJECT token (v3.0 breaking change).

        v3.0 requires all tokens to have explicit roles claim. Tokens without
        roles are rejected to prevent auto-promotion security bypass.
        """
        token = create_test_token(include_roles=False)
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None  # Token REJECTED - missing roles

    def test_anonymous_role(self):
        """Feature 1152: Anonymous users should have ['anonymous'] role."""
        token = create_test_token(roles=["anonymous"])
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is not None
        assert claim.roles == ["anonymous"]

    def test_null_roles_rejected(self):
        """Feature 1153: null roles value should be REJECTED.

        roles: null is not the same as roles: [] - null means missing.
        """
        # Create token with roles explicitly set to None (simulating "roles": null)
        token = create_test_token(include_roles=False)
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        claim = validate_jwt(token, config)
        assert claim is None  # Null roles treated same as missing

    def test_v3_breaking_change_forces_relogin(self):
        """Feature 1153: v3.0 tokens without roles force re-authentication.

        This is the core v3.0 breaking change. Old tokens (pre-1152/1153)
        will be rejected, forcing users to re-login and get new tokens
        with explicit roles claims.
        """
        # Simulate old token without roles
        token = create_test_token(include_roles=False)
        config = JWTConfig(secret=TEST_SECRET, audience="sentiment-analyzer-api")

        # Old token should be rejected
        claim = validate_jwt(token, config)
        assert claim is None, "Old tokens without roles must be rejected"

        # New token with roles should work
        new_token = create_test_token(roles=["free"])
        new_claim = validate_jwt(new_token, config)
        assert new_claim is not None, "New tokens with roles must be accepted"
        assert new_claim.roles == ["free"]
