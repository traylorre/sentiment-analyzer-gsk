"""Integration tests for market data ingestion collection flow (T020).

Tests the full ingestion flow from scheduled trigger to data storage
using mocked adapters and real DynamoDB (moto).

Marked as integration tests to skip in unit test runs.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.adapters.base import NewsArticle
from src.lambdas.shared.utils.dedup import generate_dedup_key


@pytest.fixture
def dynamodb_table():
    """Create a DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-news-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="test-news-table")
        yield table


@pytest.fixture
def sample_articles() -> list[NewsArticle]:
    """Create sample news articles for testing."""
    return [
        NewsArticle(
            article_id="article-001",
            source="tiingo",
            title="Apple Reports Record Q4 Earnings",
            description="Apple Inc. reported record quarterly revenue.",
            url="https://example.com/apple-q4",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
            source_name="Reuters",
            tickers=["AAPL"],
            tags=["earnings", "technology"],
        ),
        NewsArticle(
            article_id="article-002",
            source="tiingo",
            title="Tesla Announces New Factory",
            description="Tesla to build new gigafactory in Texas.",
            url="https://example.com/tesla-factory",
            published_at=datetime(2025, 12, 9, 15, 0, 0, tzinfo=UTC),
            source_name="Bloomberg",
            tickers=["TSLA"],
            tags=["manufacturing", "automotive"],
        ),
        NewsArticle(
            article_id="article-003",
            source="tiingo",
            title="Microsoft Cloud Revenue Grows",
            description="Azure revenue increased 30% year-over-year.",
            url="https://example.com/msft-cloud",
            published_at=datetime(2025, 12, 9, 15, 30, 0, tzinfo=UTC),
            source_name="CNBC",
            tickers=["MSFT"],
            tags=["cloud", "technology"],
        ),
    ]


@pytest.mark.integration
class TestCollectionFlow:
    """Integration tests for the collection flow."""

    def test_store_news_items_creates_dynamodb_records(
        self, dynamodb_table, sample_articles
    ) -> None:
        """Should store news items in DynamoDB with correct schema."""
        from src.lambdas.ingestion.storage import store_news_items

        result = store_news_items(dynamodb_table, sample_articles, "tiingo")

        assert result.items_stored == 3
        assert result.items_duplicate == 0
        assert result.items_failed == 0

        # Verify items exist in table
        response = dynamodb_table.scan()
        assert response["Count"] == 3

    def test_store_news_items_deduplicates_within_batch(
        self, dynamodb_table, sample_articles
    ) -> None:
        """Should skip duplicate articles within the same batch.

        Note: Cross-batch deduplication requires additional handling since
        DynamoDB conditional writes work on PK+SK combo, and SK includes
        ingested_at timestamp which differs between batches.
        """
        from src.lambdas.ingestion.storage import store_news_items

        # Store articles twice in same batch by duplicating the list
        duplicate_articles = sample_articles + sample_articles
        result = store_news_items(dynamodb_table, duplicate_articles, "tiingo")

        # Within same batch (same ingested_at), duplicates are detected via PK
        # First 3 succeed, second 3 are duplicates
        assert result.items_stored == 3
        assert result.items_duplicate == 3

        # Verify only 3 items in table
        response = dynamodb_table.scan()
        assert response["Count"] == 3

    def test_store_news_items_different_source_not_duplicate(
        self, dynamodb_table, sample_articles
    ) -> None:
        """Same article from different source should not be deduplicated."""
        from src.lambdas.ingestion.storage import store_news_items

        # Store from tiingo
        result1 = store_news_items(dynamodb_table, sample_articles, "tiingo")
        assert result1.items_stored == 3

        # Store from finnhub - should NOT be duplicates (different source in key)
        result2 = store_news_items(dynamodb_table, sample_articles, "finnhub")
        assert result2.items_stored == 3
        assert result2.items_duplicate == 0

        # Verify 6 items in table (3 from each source)
        response = dynamodb_table.scan()
        assert response["Count"] == 6

    def test_news_item_pk_sk_format(self, dynamodb_table, sample_articles) -> None:
        """NewsItem should use correct PK/SK format per ADR-002."""
        from src.lambdas.ingestion.storage import store_news_items

        store_news_items(dynamodb_table, sample_articles[:1], "tiingo")

        response = dynamodb_table.scan()
        item = response["Items"][0]

        # PK should be NEWS#{dedup_key}
        assert item["PK"].startswith("NEWS#")
        assert len(item["PK"]) == 37  # NEWS# (5) + 32 char hash

        # SK should be {source}#{iso_timestamp}
        assert item["SK"].startswith("tiingo#")

    def test_data_freshness_within_15_minutes(
        self, dynamodb_table, sample_articles
    ) -> None:
        """Stored items should have ingested_at within 15 minutes of now (NFR)."""
        from src.lambdas.ingestion.storage import store_news_items

        store_news_items(dynamodb_table, sample_articles[:1], "tiingo")

        response = dynamodb_table.scan()
        item = response["Items"][0]

        ingested_at = datetime.fromisoformat(item["ingested_at"])
        now = datetime.now(UTC)
        age = now - ingested_at

        # Data freshness requirement: <15 minutes
        assert age < timedelta(minutes=15)


@pytest.mark.integration
class TestDeduplicationKey:
    """Integration tests for deduplication key generation."""

    def test_dedup_key_deterministic(self) -> None:
        """Same inputs should always produce same dedup key."""
        headline = "Test Headline"
        source = "tiingo"
        published_at = datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, source, published_at)
        key2 = generate_dedup_key(headline, source, published_at)

        assert key1 == key2
        assert len(key1) == 32

    def test_dedup_key_date_only(self) -> None:
        """Dedup key should use date only, not time."""
        headline = "Same Day Article"
        source = "tiingo"
        morning = datetime(2025, 12, 9, 9, 0, 0, tzinfo=UTC)
        evening = datetime(2025, 12, 9, 21, 0, 0, tzinfo=UTC)

        key_morning = generate_dedup_key(headline, source, morning)
        key_evening = generate_dedup_key(headline, source, evening)

        # Same day should produce same key
        assert key_morning == key_evening

    def test_dedup_key_different_days(self) -> None:
        """Different days should produce different dedup keys."""
        headline = "Daily Article"
        source = "tiingo"
        day1 = datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC)
        day2 = datetime(2025, 12, 10, 14, 0, 0, tzinfo=UTC)

        key1 = generate_dedup_key(headline, source, day1)
        key2 = generate_dedup_key(headline, source, day2)

        assert key1 != key2


@pytest.mark.integration
class TestCollectorFetch:
    """Integration tests for collector fetch operations."""

    def test_fetch_news_returns_fetch_result(self) -> None:
        """fetch_news should return FetchResult with articles."""
        from src.lambdas.ingestion.collector import FetchResult, fetch_news
        from src.lambdas.shared.failover import FailoverOrchestrator, FailoverResult

        # Mock orchestrator
        mock_orchestrator = MagicMock(spec=FailoverOrchestrator)
        mock_orchestrator.get_news_with_failover.return_value = FailoverResult(
            data=[
                NewsArticle(
                    article_id="test-001",
                    source="tiingo",
                    title="Test Article",
                    description="Test description",
                    url="https://example.com",
                    published_at=datetime.now(UTC),
                    source_name="Test",
                    tickers=["AAPL"],
                    tags=[],
                )
            ],
            source_used="tiingo",
            is_failover=False,
            duration_ms=100,
        )

        result = fetch_news(mock_orchestrator, ["AAPL"])

        assert isinstance(result, FetchResult)
        assert len(result.articles) == 1
        assert result.source_used == "tiingo"
        assert result.is_failover is False

    def test_fetch_news_handles_both_sources_failing(self) -> None:
        """fetch_news should return empty result when both sources fail."""
        from src.lambdas.ingestion.collector import fetch_news
        from src.lambdas.shared.adapters.base import AdapterError
        from src.lambdas.shared.failover import FailoverOrchestrator

        mock_orchestrator = MagicMock(spec=FailoverOrchestrator)
        mock_orchestrator.get_news_with_failover.side_effect = AdapterError(
            "Both sources failed"
        )

        result = fetch_news(mock_orchestrator, ["AAPL"])

        assert len(result.articles) == 0
        assert result.error is not None


@pytest.mark.integration
class TestStorageMetrics:
    """Integration tests for storage metrics tracking."""

    def test_storage_result_calculates_duplicate_rate(
        self, dynamodb_table, sample_articles
    ) -> None:
        """StorageResult should enable duplicate rate calculation.

        Tests within-batch deduplication since SK (ingested_at) differs
        between separate store_news_items() calls.
        """
        from src.lambdas.ingestion.storage import get_duplicate_rate, store_news_items

        # Store articles with duplicates in same batch (100% duplicate rate)
        duplicate_articles = sample_articles + sample_articles
        result = store_news_items(dynamodb_table, duplicate_articles, "tiingo")

        # First 3 stored, second 3 are duplicates
        assert result.items_stored == 3
        assert result.items_duplicate == 3

        rate = get_duplicate_rate(result)
        assert rate == 0.5  # 50% duplicates (3 dupes / 6 total)

    def test_mixed_storage_result(self, dynamodb_table, sample_articles) -> None:
        """Should correctly track mixed new/duplicate results.

        Tests within-batch deduplication by including partial duplicates
        in a single batch.
        """
        from src.lambdas.ingestion.storage import get_duplicate_rate, store_news_items

        # Create batch with 2 unique + 1 duplicate of first article
        mixed_batch = sample_articles[:2] + [sample_articles[0]]

        result = store_news_items(dynamodb_table, mixed_batch, "tiingo")

        assert result.items_stored == 2
        assert result.items_duplicate == 1

        rate = get_duplicate_rate(result)
        assert abs(rate - (1 / 3)) < 0.01  # ~33.3% duplicates
