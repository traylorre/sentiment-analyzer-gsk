"""
Ingestion Lambda Configuration
==============================

Parses and validates configuration from environment variables.

For On-Call Engineers:
    Environment variables:
    - WATCH_TAGS: Comma-separated tags (max 5)
    - DYNAMODB_TABLE: DynamoDB table name
    - SNS_TOPIC_ARN: SNS topic for analysis requests
    - NEWSAPI_SECRET_ARN: Secret ARN for NewsAPI key
    - MODEL_VERSION: Sentiment model version

    If ingestion fails with config errors:
    1. Check Lambda environment variables in AWS Console
    2. Verify WATCH_TAGS format (comma-separated, max 5)
    3. Check secret ARN exists and Lambda has access

    See SC-03 in ON_CALL_SOP.md.

For Developers:
    - Use get_config() to load all configuration
    - Use parse_watch_tags() for tag parsing only
    - Configuration is validated on load
    - All required vars must be set

Security Notes:
    - Secret ARNs stored in env vars (not actual secrets)
    - Secrets retrieved at runtime from Secrets Manager
    - Tags are sanitized (stripped, filtered)
"""

import logging
import os
from dataclasses import dataclass, field

# Structured logging
logger = logging.getLogger(__name__)

# Configuration constants
MAX_WATCH_TAGS = 5
DEFAULT_MODEL_VERSION = "v1.0.0"


@dataclass
class IngestionConfig:
    """
    Configuration for the Ingestion Lambda.

    All fields are validated on instantiation.

    On-Call Note:
        If any required field is missing, Lambda will fail to start.
        Check CloudWatch logs for specific missing variable.
    """

    watch_tags: list[str]
    dynamodb_table: str
    sns_topic_arn: str
    newsapi_secret_arn: str
    model_version: str
    aws_region: str = "us-east-1"

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """
        Validate all configuration values.

        Raises:
            ConfigurationError: If any validation fails
        """
        # Validate watch_tags
        if not self.watch_tags:
            raise ConfigurationError("WATCH_TAGS must have at least one tag")

        if len(self.watch_tags) > MAX_WATCH_TAGS:
            raise ConfigurationError(
                f"WATCH_TAGS cannot exceed {MAX_WATCH_TAGS} tags, got {len(self.watch_tags)}"
            )

        # Validate required strings
        if not self.dynamodb_table:
            raise ConfigurationError("DYNAMODB_TABLE is required")

        if not self.sns_topic_arn:
            raise ConfigurationError("SNS_TOPIC_ARN is required")

        if not self.newsapi_secret_arn:
            raise ConfigurationError("NEWSAPI_SECRET_ARN is required")

        # Validate ARN formats
        if not self.sns_topic_arn.startswith("arn:aws:sns:"):
            raise ConfigurationError(
                f"Invalid SNS_TOPIC_ARN format: {self.sns_topic_arn}"
            )

        # Validate model version format
        if not self.model_version.startswith("v"):
            raise ConfigurationError(
                f"MODEL_VERSION must start with 'v': {self.model_version}"
            )


def get_config() -> IngestionConfig:
    """
    Load and validate configuration from environment variables.

    Returns:
        IngestionConfig with all settings

    Raises:
        ConfigurationError: If required vars missing or invalid

    Example:
        >>> config = get_config()
        >>> print(config.watch_tags)
        ['AI', 'climate', 'economy', 'health', 'sports']

    On-Call Note:
        This is called at Lambda cold start. If it fails, check
        Lambda environment variables in AWS Console.
    """
    # Parse watch tags
    watch_tags_str = os.environ.get("WATCH_TAGS", "")
    watch_tags = parse_watch_tags(watch_tags_str)

    # Get required variables
    dynamodb_table = os.environ.get("DYNAMODB_TABLE", "")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN", "")
    newsapi_secret_arn = os.environ.get("NEWSAPI_SECRET_ARN", "")

    # Get optional variables with defaults
    model_version = os.environ.get("MODEL_VERSION", DEFAULT_MODEL_VERSION)
    aws_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    # Create and validate config
    config = IngestionConfig(
        watch_tags=watch_tags,
        dynamodb_table=dynamodb_table,
        sns_topic_arn=sns_topic_arn,
        newsapi_secret_arn=newsapi_secret_arn,
        model_version=model_version,
        aws_region=aws_region,
    )

    logger.info(
        "Configuration loaded",
        extra={
            "watch_tags": config.watch_tags,
            "dynamodb_table": config.dynamodb_table,
            "model_version": config.model_version,
        },
    )

    return config


def parse_watch_tags(tags_string: str) -> list[str]:
    """
    Parse comma-separated watch tags string.

    Args:
        tags_string: Comma-separated tags (e.g., "AI,climate,economy")

    Returns:
        List of cleaned tag strings

    Raises:
        ConfigurationError: If tags are invalid

    Example:
        >>> parse_watch_tags("AI, climate , economy")
        ['AI', 'climate', 'economy']

    On-Call Note:
        Tags are stripped of whitespace and empty strings are filtered.
        Max 5 tags allowed.
    """
    if not tags_string:
        raise ConfigurationError("WATCH_TAGS environment variable is not set")

    # Split and clean tags
    tags = []
    for tag in tags_string.split(","):
        cleaned = tag.strip()
        if cleaned:
            tags.append(cleaned)

    # Validate count
    if not tags:
        raise ConfigurationError("WATCH_TAGS must contain at least one valid tag")

    if len(tags) > MAX_WATCH_TAGS:
        raise ConfigurationError(
            f"WATCH_TAGS cannot exceed {MAX_WATCH_TAGS} tags, got {len(tags)}"
        )

    # Check for duplicates
    if len(tags) != len(set(tags)):
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        logger.warning(
            f"Duplicate tags removed: {len(tags) - len(unique_tags)} duplicates",
            extra={"original": tags, "cleaned": unique_tags},
        )
        tags = unique_tags

    return tags


def validate_tag_format(tag: str) -> bool:
    """
    Validate a single tag format.

    Args:
        tag: Tag string to validate

    Returns:
        True if valid, False otherwise

    Valid tags:
    - 1-50 characters
    - Alphanumeric plus hyphens and underscores
    - No leading/trailing whitespace
    """
    if not tag or len(tag) > 50:
        return False

    if tag != tag.strip():
        return False

    # Allow alphanumeric, hyphens, underscores, and spaces
    allowed_chars = set(
        "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "-_ "
    )

    return all(c in allowed_chars for c in tag)


class ConfigurationError(Exception):
    """
    Raised when configuration is invalid or missing.

    On-Call Note:
        This error means Lambda cannot start. Check environment
        variables in AWS Console and CloudWatch logs for details.
    """

    pass
