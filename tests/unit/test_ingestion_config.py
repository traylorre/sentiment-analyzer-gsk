"""
Unit Tests for Ingestion Configuration
======================================

Tests configuration parsing and validation.

For On-Call Engineers:
    These tests verify:
    - WATCH_TAGS parsing (comma-separated, max 5)
    - Required environment variables
    - ARN format validation

For Developers:
    - Use monkeypatch to set environment variables
    - Test both valid and invalid configurations
    - Test edge cases (empty, duplicates, whitespace)
"""

import pytest

from src.lambdas.ingestion.config import (
    ConfigurationError,
    IngestionConfig,
    get_config,
    parse_watch_tags,
    validate_tag_format,
)


@pytest.fixture
def valid_env_vars(monkeypatch):
    """Set up valid environment variables for testing."""
    monkeypatch.setenv("WATCH_TAGS", "AI,climate,economy,health,sports")
    monkeypatch.setenv("DYNAMODB_TABLE", "dev-sentiment-items")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789:test-topic")
    monkeypatch.setenv(
        "NEWSAPI_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
    )
    monkeypatch.setenv("MODEL_VERSION", "v1.0.0")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


class TestParseWatchTags:
    """Tests for parse_watch_tags function."""

    def test_parse_basic_tags(self):
        """Test parsing basic comma-separated tags."""
        tags = parse_watch_tags("AI,climate,economy")

        assert tags == ["AI", "climate", "economy"]

    def test_parse_tags_with_spaces(self):
        """Test parsing tags with surrounding spaces."""
        tags = parse_watch_tags("AI , climate , economy")

        assert tags == ["AI", "climate", "economy"]

    def test_parse_single_tag(self):
        """Test parsing single tag."""
        tags = parse_watch_tags("AI")

        assert tags == ["AI"]

    def test_parse_max_tags(self):
        """Test parsing maximum 5 tags."""
        tags = parse_watch_tags("AI,climate,economy,health,sports")

        assert len(tags) == 5

    def test_parse_exceeds_max_raises(self):
        """Test that more than 5 tags raises error."""
        with pytest.raises(ConfigurationError, match="cannot exceed 5"):
            parse_watch_tags("a,b,c,d,e,f")

    def test_parse_empty_string_raises(self):
        """Test that empty string raises error."""
        with pytest.raises(ConfigurationError, match="not set"):
            parse_watch_tags("")

    def test_parse_only_commas_raises(self):
        """Test that only commas raises error."""
        with pytest.raises(ConfigurationError, match="at least one valid"):
            parse_watch_tags(",,,")

    def test_parse_removes_duplicates(self):
        """Test that duplicate tags are removed."""
        tags = parse_watch_tags("AI,climate,AI,economy")

        assert tags == ["AI", "climate", "economy"]

    def test_parse_filters_empty_values(self):
        """Test that empty values between commas are filtered."""
        tags = parse_watch_tags("AI,,climate,,,economy")

        assert tags == ["AI", "climate", "economy"]

    def test_parse_preserves_order(self):
        """Test that tag order is preserved."""
        tags = parse_watch_tags("economy,AI,health,climate,sports")

        assert tags == ["economy", "AI", "health", "climate", "sports"]


class TestValidateTagFormat:
    """Tests for validate_tag_format function."""

    def test_valid_alphanumeric(self):
        """Test valid alphanumeric tag."""
        assert validate_tag_format("AI") is True
        assert validate_tag_format("climate") is True
        assert validate_tag_format("Economy2025") is True

    def test_valid_with_hyphens(self):
        """Test valid tag with hyphens."""
        assert validate_tag_format("machine-learning") is True

    def test_valid_with_underscores(self):
        """Test valid tag with underscores."""
        assert validate_tag_format("tech_news") is True

    def test_valid_with_spaces(self):
        """Test valid tag with spaces."""
        assert validate_tag_format("artificial intelligence") is True

    def test_invalid_empty(self):
        """Test empty tag is invalid."""
        assert validate_tag_format("") is False

    def test_invalid_too_long(self):
        """Test tag over 50 chars is invalid."""
        assert validate_tag_format("a" * 51) is False

    def test_invalid_with_leading_space(self):
        """Test tag with leading space is invalid."""
        assert validate_tag_format(" AI") is False

    def test_invalid_special_chars(self):
        """Test tag with special characters is invalid."""
        assert validate_tag_format("AI!") is False
        assert validate_tag_format("climate@") is False


class TestIngestionConfig:
    """Tests for IngestionConfig dataclass."""

    def test_valid_config(self):
        """Test creating valid configuration."""
        config = IngestionConfig(
            watch_tags=["AI", "climate"],
            dynamodb_table="test-table",
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:topic",
            newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            model_version="v1.0.0",
            aws_region="us-east-1",
        )

        assert config.watch_tags == ["AI", "climate"]
        assert config.dynamodb_table == "test-table"

    def test_empty_watch_tags_raises(self):
        """Test that empty watch_tags raises error."""
        with pytest.raises(ConfigurationError, match="at least one tag"):
            IngestionConfig(
                watch_tags=[],
                dynamodb_table="test-table",
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:topic",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="v1.0.0",
                aws_region="us-east-1",
            )

    def test_too_many_watch_tags_raises(self):
        """Test that more than 5 watch_tags raises error."""
        with pytest.raises(ConfigurationError, match="cannot exceed 5"):
            IngestionConfig(
                watch_tags=["a", "b", "c", "d", "e", "f"],
                dynamodb_table="test-table",
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:topic",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="v1.0.0",
                aws_region="us-east-1",
            )

    def test_missing_dynamodb_table_raises(self):
        """Test that empty dynamodb_table raises error."""
        with pytest.raises(ConfigurationError, match="DATABASE_TABLE is required"):
            IngestionConfig(
                watch_tags=["AI"],
                dynamodb_table="",
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:topic",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="v1.0.0",
                aws_region="us-east-1",
            )

    def test_missing_sns_topic_raises(self):
        """Test that empty sns_topic_arn raises error."""
        with pytest.raises(ConfigurationError, match="SNS_TOPIC_ARN is required"):
            IngestionConfig(
                watch_tags=["AI"],
                dynamodb_table="test-table",
                sns_topic_arn="",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="v1.0.0",
                aws_region="us-east-1",
            )

    def test_invalid_sns_arn_format_raises(self):
        """Test that invalid SNS ARN format raises error."""
        with pytest.raises(ConfigurationError, match="Invalid SNS_TOPIC_ARN"):
            IngestionConfig(
                watch_tags=["AI"],
                dynamodb_table="test-table",
                sns_topic_arn="invalid-arn",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="v1.0.0",
                aws_region="us-east-1",
            )

    def test_invalid_model_version_raises(self):
        """Test that model version without 'v' prefix raises error."""
        with pytest.raises(ConfigurationError, match="must start with 'v'"):
            IngestionConfig(
                watch_tags=["AI"],
                dynamodb_table="test-table",
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:topic",
                newsapi_secret_arn="arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                model_version="1.0.0",  # Missing 'v'
                aws_region="us-east-1",
            )


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_success(self, valid_env_vars):
        """Test loading valid configuration from env vars."""
        config = get_config()

        assert config.watch_tags == ["AI", "climate", "economy", "health", "sports"]
        assert config.dynamodb_table == "dev-sentiment-items"
        assert config.model_version == "v1.0.0"

    def test_get_config_missing_watch_tags(self, monkeypatch):
        """Test error when WATCH_TAGS is missing."""
        monkeypatch.delenv("WATCH_TAGS", raising=False)
        monkeypatch.setenv("DYNAMODB_TABLE", "test")
        monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789:topic")
        monkeypatch.setenv(
            "NEWSAPI_SECRET_ARN",
            "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
        )

        with pytest.raises(ConfigurationError):
            get_config()

    def test_get_config_default_model_version(self, valid_env_vars, monkeypatch):
        """Test default model version when not set."""
        monkeypatch.delenv("MODEL_VERSION", raising=False)

        config = get_config()

        assert config.model_version == "v1.0.0"

    def test_get_config_missing_region_raises(self, valid_env_vars, monkeypatch):
        """Test that missing AWS_REGION raises error."""
        monkeypatch.delenv("AWS_REGION", raising=False)

        with pytest.raises(
            ValueError, match="AWS_REGION environment variable must be set"
        ):
            get_config()


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_error_message(self):
        """Test error message is preserved."""
        error = ConfigurationError("Test error message")

        assert str(error) == "Test error message"

    def test_error_is_exception(self):
        """Test ConfigurationError is an Exception."""
        assert issubclass(ConfigurationError, Exception)
