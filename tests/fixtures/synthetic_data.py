"""
Synthetic Test Data Generator for E2E Testing

This module generates deterministic test data for E2E and integration tests.
It creates items in DynamoDB that can be verified against known properties.

Test Debt Item: TD-004
Spec: 005-synthetic-test-data

Usage:
    from tests.fixtures.synthetic_data import SyntheticDataGenerator

    with SyntheticDataGenerator(table_name) as generator:
        items = generator.create_test_dataset()
        # Run tests against known data
        assert len(items) == 6
    # Cleanup happens automatically
"""

import logging
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

import boto3

logger = logging.getLogger(__name__)

# All synthetic items have this prefix for easy identification and cleanup
TEST_DATA_PREFIX = "TEST_E2E_"


class SyntheticDataGenerator:
    """Generate synthetic sentiment items for E2E testing.

    Creates deterministic test data in DynamoDB with known properties,
    allowing tests to verify behavior against expected values rather
    than hoping real data exists.

    Attributes:
        table_name: Name of the DynamoDB table
        region: AWS region (default: us-east-1)
        created_items: List of item keys created (for cleanup)
    """

    def __init__(self, table_name: str | None = None, region: str = "us-east-1"):
        """Initialize the generator.

        Args:
            table_name: DynamoDB table name. Defaults to DYNAMODB_TABLE env var
                       or 'preprod-sentiment-items'.
            region: AWS region for DynamoDB client.
        """
        self.table_name = table_name or os.environ.get(
            "DYNAMODB_TABLE", "preprod-sentiment-items"
        )
        self.region = region
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(self.table_name)
        self.created_items: list[dict] = []  # List of {source_id, timestamp} dicts

    def create_sentiment_item(
        self,
        sentiment: Literal["positive", "neutral", "negative"] = "neutral",
        score: float = 0.75,
        tags: list[str] | None = None,
        source: str = "test-source",
        hours_ago: int = 0,
    ) -> dict:
        """Create a synthetic sentiment item in DynamoDB.

        Args:
            sentiment: Sentiment classification (positive/neutral/negative)
            score: Confidence score (0.0 to 1.0)
            tags: List of tags for the item
            source: Source identifier prefix
            hours_ago: How many hours ago the item was "created"

        Returns:
            The created item dict
        """
        item_id = f"{TEST_DATA_PREFIX}{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
        timestamp_str = timestamp.isoformat()

        # Calculate TTL (30 days from now)
        ttl_timestamp = int((datetime.now(UTC) + timedelta(days=30)).timestamp())

        item = {
            "source_id": f"newsapi:{item_id}",
            "timestamp": timestamp_str,
            "title": f"Test Article - {sentiment.upper()} sentiment",
            "source_url": f"https://test.example.com/article/{item_id}",
            "snippet": f"This is a synthetic test article with {sentiment} sentiment.",
            "source_name": source,
            "status": "analyzed",
            "sentiment": sentiment,
            "score": Decimal(str(score)),  # DynamoDB requires Decimal for floats
            "model_version": "test-model-v1",
            "analyzed_at": timestamp_str,
            "matched_tags": tags or ["test", "synthetic"],
            "text_for_analysis": f"Test article content for {sentiment} sentiment analysis.",
            "ttl_timestamp": ttl_timestamp,
            "_synthetic": True,  # Marker for synthetic data
        }

        self.table.put_item(Item=item)
        self.created_items.append(
            {"source_id": item["source_id"], "timestamp": item["timestamp"]}
        )

        logger.debug("Created synthetic item: %s", item["source_id"])
        return item

    def create_test_dataset(self) -> list[dict]:
        """Create a standard test dataset with known properties.

        Creates 6 items covering all sentiment types and various tags:
        - 2 positive items (tech/ai, business)
        - 2 neutral items (tech, politics)
        - 2 negative items (business/economy, tech)

        Returns:
            List of created items with known properties
        """
        items = []

        # Positive sentiment items
        items.append(
            self.create_sentiment_item(
                sentiment="positive",
                score=0.95,
                tags=["tech", "ai"],
                hours_ago=1,
            )
        )
        items.append(
            self.create_sentiment_item(
                sentiment="positive",
                score=0.75,
                tags=["business"],
                hours_ago=2,
            )
        )

        # Neutral sentiment items
        items.append(
            self.create_sentiment_item(
                sentiment="neutral",
                score=0.55,
                tags=["tech"],
                hours_ago=3,
            )
        )
        items.append(
            self.create_sentiment_item(
                sentiment="neutral",
                score=0.50,
                tags=["politics"],
                hours_ago=4,
            )
        )

        # Negative sentiment items
        items.append(
            self.create_sentiment_item(
                sentiment="negative",
                score=0.85,
                tags=["business", "economy"],
                hours_ago=5,
            )
        )
        items.append(
            self.create_sentiment_item(
                sentiment="negative",
                score=0.65,
                tags=["tech"],
                hours_ago=6,
            )
        )

        logger.info(
            "Created synthetic test dataset with %d items in table %s",
            len(items),
            self.table_name,
        )
        return items

    def cleanup(self) -> None:
        """Delete all synthetic test items created by this generator.

        This is called automatically when using the context manager.
        Cleanup is best-effort - failures are logged but don't raise.
        """
        cleaned = 0
        for item_key in self.created_items:
            try:
                self.table.delete_item(Key=item_key)
                cleaned += 1
            except Exception as e:
                logger.warning(
                    "Failed to cleanup synthetic item %s: %s",
                    item_key.get("source_id"),
                    e,
                )

        logger.info(
            "Cleaned up %d/%d synthetic items",
            cleaned,
            len(self.created_items),
        )
        self.created_items.clear()

    def __enter__(self) -> "SyntheticDataGenerator":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context manager and cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions


@contextmanager
def synthetic_test_data(table_name: str | None = None):
    """Context manager for creating and cleaning up synthetic test data.

    Example:
        with synthetic_test_data() as data:
            assert len(data["items"]) == 6
            assert data["positive_count"] == 2
            # Tests run here with known data
        # Cleanup happens automatically

    Args:
        table_name: DynamoDB table name (optional, uses env var if not provided)

    Yields:
        Dict containing:
        - items: List of created items
        - generator: The SyntheticDataGenerator instance
        - positive_count: Number of positive items (2)
        - neutral_count: Number of neutral items (2)
        - negative_count: Number of negative items (2)
        - total_count: Total number of items (6)
        - tech_count: Number of items with "tech" tag (3)
    """
    with SyntheticDataGenerator(table_name) as generator:
        items = generator.create_test_dataset()
        yield {
            "items": items,
            "generator": generator,
            "positive_count": 2,
            "neutral_count": 2,
            "negative_count": 2,
            "total_count": 6,
            "tech_count": 3,  # tech tag appears in 3 items
            "business_count": 2,  # business tag appears in 2 items
        }
