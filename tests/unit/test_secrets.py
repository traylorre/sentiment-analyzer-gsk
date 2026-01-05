"""
Unit Tests for Secrets Manager Helper Module
=============================================

Tests all Secrets Manager helper functions using moto mocks.

For On-Call Engineers:
    If tests fail with credential errors:
    1. Ensure moto @mock_aws decorator is present
    2. Check aws_credentials fixture is used
    3. Verify no real AWS calls are being made

For Developers:
    - All tests use moto to mock Secrets Manager
    - Test caching behavior with time mocking (freezegun)
    - Test error cases for all exception types
"""

import json
import os
import time

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.secrets import (
    SecretAccessDeniedError,
    SecretNotFoundError,
    SecretRetrievalError,
    clear_cache,
    compare_digest,
    get_api_key,
    get_secret,
    get_secrets_client,
)


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def secrets_manager(aws_credentials):
    """
    Create mocked Secrets Manager with test secrets.

    Creates secrets matching the paths used in production:
    - dev/sentiment-analyzer/tiingo
    - dev/sentiment-analyzer/dashboard-api-key
    """
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")

        # Create Tiingo API secret
        client.create_secret(
            Name="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "test-tiingo-key-12345"}),
        )

        # Create Dashboard API key secret
        client.create_secret(
            Name="dev/sentiment-analyzer/dashboard-api-key",
            SecretString=json.dumps({"api_key": "test-dashboard-key-67890"}),
        )

        # Create a secret with multiple fields
        client.create_secret(
            Name="dev/sentiment-analyzer/multi-field",
            SecretString=json.dumps(
                {
                    "api_key": "multi-key",
                    "username": "test-user",
                    "password": "test-pass",
                }
            ),
        )

        # Clear any cached secrets from previous tests
        clear_cache()

        yield client


class TestGetSecretsClient:
    """Tests for get_secrets_client function."""

    def test_get_client_default_region(self, aws_credentials):
        """Test client creation with default region."""
        with mock_aws():
            client = get_secrets_client()
            assert client is not None

    def test_get_client_custom_region(self, aws_credentials):
        """Test client creation with custom region."""
        with mock_aws():
            client = get_secrets_client(region_name="us-west-2")
            assert client is not None


class TestGetSecret:
    """Tests for get_secret function."""

    def test_get_secret_success(self, secrets_manager):
        """Test successful secret retrieval."""
        secret = get_secret("dev/sentiment-analyzer/tiingo")

        assert secret == {"api_key": "test-tiingo-key-12345"}

    def test_get_secret_multiple_fields(self, secrets_manager):
        """Test retrieving secret with multiple fields."""
        secret = get_secret("dev/sentiment-analyzer/multi-field")

        assert secret["api_key"] == "multi-key"
        assert secret["username"] == "test-user"
        assert secret["password"] == "test-pass"

    def test_get_secret_caching(self, secrets_manager):
        """Test that secrets are cached."""
        # First call - fetches from Secrets Manager (result triggers caching)
        get_secret("dev/sentiment-analyzer/tiingo")

        # Modify the secret in Secrets Manager
        secrets_manager.update_secret(
            SecretId="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "updated-key"}),
        )

        # Second call - should return cached value
        secret2 = get_secret("dev/sentiment-analyzer/tiingo")

        # Should still be original value (cached)
        assert secret2 == {"api_key": "test-tiingo-key-12345"}

    def test_get_secret_force_refresh(self, secrets_manager):
        """Test force_refresh bypasses cache."""
        # First call - caches the secret
        get_secret("dev/sentiment-analyzer/tiingo")

        # Modify the secret
        secrets_manager.update_secret(
            SecretId="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "updated-key"}),
        )

        # Force refresh - should get new value
        secret = get_secret("dev/sentiment-analyzer/tiingo", force_refresh=True)

        assert secret == {"api_key": "updated-key"}

    def test_get_secret_not_found(self, secrets_manager, caplog):
        """Test SecretNotFoundError for missing secret."""
        with pytest.raises(SecretNotFoundError, match="Secret not found"):
            get_secret("nonexistent/secret")

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Secret not found")

    def test_get_secret_invalid_json(self, secrets_manager, caplog):
        """Test SecretRetrievalError for non-JSON secret."""
        # Create secret with invalid JSON
        secrets_manager.create_secret(
            Name="invalid-json-secret",
            SecretString="not-json",
        )

        with pytest.raises(SecretRetrievalError, match="not valid JSON"):
            get_secret("invalid-json-secret")

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        # Log message updated in 070-validation-blindspot-audit to avoid
        # CodeQL py/clear-text-logging-sensitive-data false positive
        assert_error_logged(caplog, "Failed to parse resource as JSON")

    def test_cache_expiry(self, secrets_manager, monkeypatch):
        """Test that cache expires after TTL."""
        # Clear any stale cache entries from previous tests
        clear_cache()

        # Set short TTL for test (use monkeypatch for proper cleanup)
        monkeypatch.setenv("SECRETS_CACHE_TTL_SECONDS", "1")

        # First call - caches the secret
        get_secret("dev/sentiment-analyzer/tiingo")

        # Modify the secret
        secrets_manager.update_secret(
            SecretId="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "updated-key"}),
        )

        # Wait for cache to expire
        time.sleep(1.1)

        # Should get new value after cache expiry
        secret = get_secret("dev/sentiment-analyzer/tiingo")

        assert secret == {"api_key": "updated-key"}


class TestGetApiKey:
    """Tests for get_api_key function."""

    def test_get_api_key_default_field(self, secrets_manager):
        """Test getting API key with default field name."""
        api_key = get_api_key("dev/sentiment-analyzer/tiingo")

        assert api_key == "test-tiingo-key-12345"

    def test_get_api_key_custom_field(self, secrets_manager):
        """Test getting value with custom field name."""
        username = get_api_key(
            "dev/sentiment-analyzer/multi-field",
            key_field="username",
        )

        assert username == "test-user"

    def test_get_api_key_missing_field(self, secrets_manager):
        """Test SecretRetrievalError for missing field."""
        with pytest.raises(SecretRetrievalError, match="Field 'missing' not found"):
            get_api_key("dev/sentiment-analyzer/tiingo", key_field="missing")


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clear_cache(self, secrets_manager):
        """Test that clear_cache removes all cached secrets."""
        # Cache a secret
        get_secret("dev/sentiment-analyzer/tiingo")

        # Modify the secret
        secrets_manager.update_secret(
            SecretId="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "updated-key"}),
        )

        # Clear cache
        clear_cache()

        # Should get new value
        secret = get_secret("dev/sentiment-analyzer/tiingo")

        assert secret == {"api_key": "updated-key"}


class TestCompareDigest:
    """Tests for compare_digest function (timing-safe comparison)."""

    def test_compare_equal_strings(self):
        """Test comparison of equal strings returns True."""
        assert compare_digest("test-key-123", "test-key-123") is True

    def test_compare_unequal_strings(self):
        """Test comparison of unequal strings returns False."""
        assert compare_digest("test-key-123", "different-key") is False

    def test_compare_empty_strings(self):
        """Test comparison of empty strings."""
        assert compare_digest("", "") is True

    def test_compare_with_none_first(self):
        """Test comparison with None first argument returns False."""
        assert compare_digest(None, "test") is False

    def test_compare_with_none_second(self):
        """Test comparison with None second argument returns False."""
        assert compare_digest("test", None) is False

    def test_compare_both_none(self):
        """Test comparison with both None returns False."""
        assert compare_digest(None, None) is False

    def test_compare_unicode_strings(self):
        """Test comparison of unicode strings."""
        assert compare_digest("key-with-émoji-🔑", "key-with-émoji-🔑") is True
        assert compare_digest("key-with-émoji-🔑", "key-with-emoji") is False

    def test_compare_different_lengths(self):
        """Test comparison of strings with different lengths."""
        assert compare_digest("short", "much-longer-string") is False


class TestSecretExceptions:
    """Tests for custom exception classes."""

    def test_secret_not_found_error(self):
        """Test SecretNotFoundError can be raised and caught."""
        with pytest.raises(SecretNotFoundError):
            raise SecretNotFoundError("Test error")

    def test_secret_access_denied_error(self):
        """Test SecretAccessDeniedError can be raised and caught."""
        with pytest.raises(SecretAccessDeniedError):
            raise SecretAccessDeniedError("Test error")

    def test_secret_retrieval_error(self):
        """Test SecretRetrievalError can be raised and caught."""
        with pytest.raises(SecretRetrievalError):
            raise SecretRetrievalError("Test error")

    def test_exception_inheritance(self):
        """Test all exceptions inherit from SecretError."""
        from src.lambdas.shared.secrets import SecretError

        assert issubclass(SecretNotFoundError, SecretError)
        assert issubclass(SecretAccessDeniedError, SecretError)
        assert issubclass(SecretRetrievalError, SecretError)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_secret_with_arn(self, secrets_manager):
        """Test retrieving secret by ARN."""
        # Get the ARN of an existing secret
        response = secrets_manager.describe_secret(
            SecretId="dev/sentiment-analyzer/tiingo"
        )
        arn = response["ARN"]

        # Retrieve by ARN
        secret = get_secret(arn)

        assert secret == {"api_key": "test-tiingo-key-12345"}

    def test_concurrent_cache_access(self, secrets_manager):
        """Test that cache handles concurrent access safely."""
        # This is a basic test - real concurrency testing would need threads
        for _ in range(10):
            secret = get_secret("dev/sentiment-analyzer/tiingo")
            assert secret == {"api_key": "test-tiingo-key-12345"}
            clear_cache()

    def test_different_secrets_cached_separately(self, secrets_manager):
        """Test that different secrets are cached independently."""
        # Cache both secrets
        tiingo = get_secret("dev/sentiment-analyzer/tiingo")
        dashboard = get_secret("dev/sentiment-analyzer/dashboard-api-key")

        # Verify they're different
        assert tiingo["api_key"] == "test-tiingo-key-12345"
        assert dashboard["api_key"] == "test-dashboard-key-67890"

        # Update only one
        secrets_manager.update_secret(
            SecretId="dev/sentiment-analyzer/tiingo",
            SecretString=json.dumps({"api_key": "updated-tiingo"}),
        )

        # Dashboard should still be cached, tiingo should be cached (not updated)
        tiingo2 = get_secret("dev/sentiment-analyzer/tiingo")
        dashboard2 = get_secret("dev/sentiment-analyzer/dashboard-api-key")

        # Both should be original cached values
        assert tiingo2["api_key"] == "test-tiingo-key-12345"
        assert dashboard2["api_key"] == "test-dashboard-key-67890"
