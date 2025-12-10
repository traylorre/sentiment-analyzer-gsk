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
    algorithm: str = "HS256",
    include_iat: bool = True,
    include_exp: bool = True,
    include_sub: bool = True,
) -> str:
    """Create a test JWT token."""
    payload = {}

    if include_sub:
        payload["sub"] = user_id
    if include_exp:
        payload["exp"] = datetime.now(UTC) + expires_in
    if include_iat:
        payload["iat"] = datetime.now(UTC)
    if issuer:
        payload["iss"] = issuer

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
        config = JWTConfig(secret=TEST_SECRET)

        claim = validate_jwt(token, config)

        assert claim is not None
        assert claim.subject == TEST_USER_ID
        assert claim.issuer == "sentiment-analyzer"
        assert isinstance(claim.expiration, datetime)
        assert isinstance(claim.issued_at, datetime)

    def test_expired_jwt_token(self):
        """Expired JWT tokens should return None."""
        token = create_test_token(expires_in=timedelta(seconds=-60))
        config = JWTConfig(secret=TEST_SECRET, leeway_seconds=0)

        claim = validate_jwt(token, config)
        assert claim is None

    def test_malformed_jwt_token(self):
        """Malformed JWT tokens should return None."""
        config = JWTConfig(secret=TEST_SECRET)

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
        config = JWTConfig(secret=TEST_SECRET)

        claim = validate_jwt(token, config)
        assert claim is None

    def test_missing_required_claims(self):
        """JWT tokens missing sub/exp/iat should return None."""
        config = JWTConfig(secret=TEST_SECRET)

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
        config = JWTConfig(secret=TEST_SECRET)

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
        config = JWTConfig(secret=TEST_SECRET, issuer="expected-issuer")

        claim = validate_jwt(token, config)
        assert claim is None

    def test_issuer_validation_skipped_if_none(self):
        """Issuer validation should be skipped if config.issuer is None."""
        token = create_test_token(issuer="any-issuer")
        config = JWTConfig(secret=TEST_SECRET, issuer=None)

        claim = validate_jwt(token, config)
        assert claim is not None


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

        with patch.dict("os.environ", {"JWT_SECRET": TEST_SECRET}):
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

        with patch.dict("os.environ", {"JWT_SECRET": TEST_SECRET}):
            user_id = extract_user_id(event)
            assert user_id == TEST_USER_ID

    def test_bearer_uuid_token_extracted(self):
        """Should extract user ID from Bearer UUID token."""
        uuid_token = "550e8400-e29b-41d4-a716-446655440000"
        event = {"headers": {"Authorization": f"Bearer {uuid_token}"}}

        user_id = extract_user_id(event)
        assert user_id == uuid_token

    def test_x_user_id_header_fallback(self):
        """Should fall back to X-User-ID header."""
        user_id_value = "550e8400-e29b-41d4-a716-446655440000"
        event = {"headers": {"X-User-ID": user_id_value}}

        user_id = extract_user_id(event)
        assert user_id == user_id_value

    def test_no_auth_returns_none(self):
        """Should return None if no authentication present."""
        event = {"headers": {}}
        user_id = extract_user_id(event)
        assert user_id is None
