"""Unit tests for financial ingestion handler (T064).

Tests the Tiingo/Finnhub ticker-based news ingestion workflow.
"""

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.adapters.base import NewsArticle, RateLimitError
from src.lambdas.shared.circuit_breaker import CircuitBreakerState
from src.lambdas.shared.quota_tracker import QuotaTracker, clear_quota_cache


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset module-level caches before each test.

    DFA-003 added caching to _get_active_tickers which persists across tests.
    Feature 1010 added quota tracker caching which also persists.
    This fixture ensures each test starts with a clean cache state.
    """
    import src.lambdas.ingestion.handler as handler_module

    # Reset active tickers cache
    handler_module._active_tickers_cache = []
    handler_module._active_tickers_cache_timestamp = 0.0
    # Reset quota tracker cache (Feature 1010)
    clear_quota_cache()
    yield
    # Clean up after test too
    handler_module._active_tickers_cache = []
    handler_module._active_tickers_cache_timestamp = 0.0
    clear_quota_cache()


@pytest.fixture
def env_vars():
    """Set required environment variables."""
    os.environ["DATABASE_TABLE"] = "test-financial-news"
    # Feature 1043: USERS_TABLE used by _get_active_tickers for configuration queries
    os.environ["USERS_TABLE"] = "test-financial-news"
    os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"
    os.environ["TIINGO_SECRET_ARN"] = (
        "arn:aws:secretsmanager:us-east-1:123456789:secret:tiingo"
    )
    os.environ["FINNHUB_SECRET_ARN"] = (
        "arn:aws:secretsmanager:us-east-1:123456789:secret:finnhub"
    )
    os.environ["MODEL_VERSION"] = "v1.0.0"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["ENVIRONMENT"] = "test"
    yield
    for key in [
        "DATABASE_TABLE",
        "USERS_TABLE",
        "SNS_TOPIC_ARN",
        "TIINGO_SECRET_ARN",
        "FINNHUB_SECRET_ARN",
        "MODEL_VERSION",
        "AWS_REGION",
        "ENVIRONMENT",
    ]:
        os.environ.pop(key, None)


def _create_table_with_gsi(dynamodb, table_name: str = "test-financial-news"):
    """Create DynamoDB table with by_entity_status GSI for testing.

    (502-gsi-query-optimization: Added GSI definition for _get_active_tickers tests)
    """
    return dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "entity_type", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_entity_status",
                "KeySchema": [
                    {"AttributeName": "entity_type", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
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
        yield table


def create_news_article(
    article_id: str = "test-123",
    source: str = "tiingo",
    title: str = "Test Article",
    tickers: list[str] | None = None,
) -> NewsArticle:
    """Create a mock NewsArticle for testing."""
    return NewsArticle(
        article_id=article_id,
        source=source,
        title=title,
        description="Test description",
        url="https://example.com/article",
        published_at=datetime.now(UTC),
        tickers=tickers or ["AAPL"],
        tags=["tech"],
        source_name="Test Source",
    )


class TestGetActiveTickers:
    """Tests for _get_active_tickers function.

    (502-gsi-query-optimization: Updated to use by_entity_status GSI)
    """

    @mock_aws
    def test_returns_empty_when_no_configurations(self, env_vars):
        """Should return empty list when no configurations exist."""
        from src.lambdas.ingestion.handler import _get_active_tickers

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table_with_gsi(dynamodb)

        tickers = _get_active_tickers(table)
        assert tickers == []

    @mock_aws
    def test_extracts_tickers_from_configurations(self, env_vars):
        """Should extract unique tickers from all active configurations."""
        from src.lambdas.ingestion.handler import _get_active_tickers

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table_with_gsi(dynamodb)

        # Add configurations with tickers (status="active" for GSI query)
        table.put_item(
            Item={
                "PK": "USER#user1",
                "SK": "CONFIG#config1",
                "entity_type": "CONFIGURATION",
                "status": "active",
                "tickers": [
                    {"symbol": "AAPL", "name": "Apple"},
                    {"symbol": "MSFT", "name": "Microsoft"},
                ],
            }
        )
        table.put_item(
            Item={
                "PK": "USER#user2",
                "SK": "CONFIG#config2",
                "entity_type": "CONFIGURATION",
                "status": "active",
                "tickers": [
                    {"symbol": "GOOGL", "name": "Alphabet"},
                    {"symbol": "AAPL", "name": "Apple"},  # Duplicate
                ],
            }
        )

        tickers = _get_active_tickers(table)
        assert sorted(tickers) == ["AAPL", "GOOGL", "MSFT"]

    @mock_aws
    def test_ignores_inactive_configurations(self, env_vars):
        """Should ignore inactive configurations.

        GSI query only returns status='active' items, so inactive configs
        are filtered at the database level.
        """
        from src.lambdas.ingestion.handler import _get_active_tickers

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table_with_gsi(dynamodb)

        # Add active configuration (status="active" for GSI)
        table.put_item(
            Item={
                "PK": "USER#user1",
                "SK": "CONFIG#config1",
                "entity_type": "CONFIGURATION",
                "status": "active",
                "tickers": [{"symbol": "AAPL"}],
            }
        )
        # Add inactive configuration (status="inactive" won't match GSI query)
        table.put_item(
            Item={
                "PK": "USER#user2",
                "SK": "CONFIG#config2",
                "entity_type": "CONFIGURATION",
                "status": "inactive",
                "tickers": [{"symbol": "MSFT"}],
            }
        )

        tickers = _get_active_tickers(table)
        assert tickers == ["AAPL"]


class TestCircuitBreakerManagement:
    """Tests for circuit breaker state management."""

    @mock_aws
    def test_creates_default_circuit_breaker(self, env_vars):
        """Should create default circuit breaker if none exists."""
        from src.lambdas.ingestion.handler import (
            _get_or_create_circuit_breaker,
        )

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
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

        breaker = _get_or_create_circuit_breaker(table, "tiingo")
        assert breaker.service == "tiingo"
        assert breaker.state == "closed"

    @mock_aws
    def test_loads_existing_circuit_breaker(self, env_vars):
        """Should load existing circuit breaker from DynamoDB."""
        from src.lambdas.ingestion.handler import (
            _get_or_create_circuit_breaker,
            _save_circuit_breaker,
        )

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
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

        # Save a breaker with failures
        breaker = CircuitBreakerState.create_default("tiingo")
        breaker.failure_count = 3
        _save_circuit_breaker(table, breaker)

        # Load it back
        loaded = _get_or_create_circuit_breaker(table, "tiingo")
        assert loaded.failure_count == 3


class TestQuotaTrackerManagement:
    """Tests for quota tracker state management."""

    @mock_aws
    def test_creates_default_quota_tracker(self, env_vars):
        """Should create default quota tracker if none exists."""
        from src.lambdas.ingestion.handler import _get_or_create_quota_tracker

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
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

        tracker = _get_or_create_quota_tracker(table)
        assert tracker.tiingo.remaining == 500
        assert tracker.finnhub.remaining == 60

    @mock_aws
    def test_loads_existing_quota_tracker(self, env_vars):
        """Should load existing quota tracker from DynamoDB."""
        from src.lambdas.ingestion.handler import (
            _get_or_create_quota_tracker,
        )

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
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

        # Create and save a tracker with some usage directly
        tracker = QuotaTracker.create_default()
        tracker.record_call("tiingo", count=10)
        table.put_item(Item=tracker.to_dynamodb_item())

        # Load it back
        loaded = _get_or_create_quota_tracker(table)
        assert loaded.tiingo.used == 10


class TestFetchTiingoArticles:
    """Tests for _fetch_tiingo_articles function."""

    def test_records_quota_and_fetches_articles(self):
        """Should record quota and fetch articles."""
        from src.lambdas.ingestion.handler import _fetch_tiingo_articles

        mock_adapter = MagicMock()
        mock_adapter.get_news.return_value = [
            create_news_article("art1", "tiingo", "Article 1"),
            create_news_article("art2", "tiingo", "Article 2"),
        ]

        tracker = QuotaTracker.create_default()
        articles = _fetch_tiingo_articles(mock_adapter, ["AAPL"], tracker)

        assert len(articles) == 2
        assert tracker.tiingo.used == 1
        mock_adapter.get_news.assert_called_once()


class TestFetchFinnhubArticles:
    """Tests for _fetch_finnhub_articles function."""

    def test_records_quota_and_fetches_articles(self):
        """Should record quota and fetch articles."""
        from src.lambdas.ingestion.handler import _fetch_finnhub_articles

        mock_adapter = MagicMock()
        mock_adapter.get_news.return_value = [
            create_news_article("art1", "finnhub", "Article 1"),
        ]

        tracker = QuotaTracker.create_default()
        articles = _fetch_finnhub_articles(mock_adapter, ["AAPL"], tracker)

        assert len(articles) == 1
        assert tracker.finnhub.used == 1
        mock_adapter.get_news.assert_called_once()


class TestProcessArticle:
    """Tests for _process_article function.

    DFA-002: _process_article now returns SNS message dict for batching
    instead of publishing immediately. Returns None for duplicates.

    Feature 1010: Updated to use cross-source dedup with headline-based keys.
    Now uses upsert_article_with_source() instead of put_item_if_not_exists().
    """

    @mock_aws
    def test_inserts_new_article(self, env_vars):
        """Should insert new article and return SNS message dict for batching."""
        from src.lambdas.ingestion.handler import _process_article

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        article = create_news_article("unique-123", "tiingo", "New Article")

        # Feature 1010: Mock upsert_article_with_source instead of put_item_if_not_exists
        with patch(
            "src.lambdas.ingestion.handler.upsert_article_with_source",
            return_value="created",
        ):
            result = _process_article(
                article=article,
                source="tiingo",
                table=table,
                model_version="v1.0.0",
            )

        # DFA-002: Now returns SNS message dict for batch publishing
        assert result is not None
        assert result["source_type"] == "tiingo"
        assert "body" in result
        # Feature 1010: source_id now uses dedup: prefix with headline hash
        assert result["body"]["source_id"].startswith("dedup:")
        assert result["body"]["model_version"] == "v1.0.0"
        # Feature 1010: Track sources array
        assert result["body"]["sources"] == ["tiingo"]

    @mock_aws
    def test_skips_duplicate_article(self, env_vars):
        """Should skip duplicate article and return None."""
        from src.lambdas.ingestion.handler import _process_article

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        article = create_news_article("duplicate-123", "tiingo", "Duplicate Article")

        # Feature 1010: Mock upsert_article_with_source returning "duplicate"
        with patch(
            "src.lambdas.ingestion.handler.upsert_article_with_source",
            return_value="duplicate",
        ):
            result = _process_article(
                article=article,
                source="tiingo",
                table=table,
                model_version="v1.0.0",
            )

        # DFA-002: Now returns None for duplicates
        assert result is None

    @mock_aws
    def test_returns_none_for_updated_article(self, env_vars):
        """Feature 1010: Should return None when article already exists from another source."""
        from src.lambdas.ingestion.handler import _process_article

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-financial-news",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        article = create_news_article(
            "cross-source-123", "finnhub", "Cross Source Article"
        )

        # Feature 1010: Mock upsert_article_with_source returning "updated"
        # (article exists from tiingo, finnhub added as second source)
        with patch(
            "src.lambdas.ingestion.handler.upsert_article_with_source",
            return_value="updated",
        ):
            result = _process_article(
                article=article,
                source="finnhub",
                table=table,
                model_version="v1.0.0",
            )

        # Should not re-publish for cross-source updates
        assert result is None


class TestGetTextForAnalysis:
    """Tests for _get_text_for_analysis function."""

    def test_combines_title_and_description(self):
        """Should combine title and description."""
        from src.lambdas.ingestion.handler import _get_text_for_analysis

        article = create_news_article()
        article.title = "Breaking News"
        article.description = "Important development"

        text = _get_text_for_analysis(article)
        assert text == "Breaking News. Important development"

    def test_uses_title_only_when_no_description(self):
        """Should use title only when no description."""
        from src.lambdas.ingestion.handler import _get_text_for_analysis

        article = create_news_article()
        article.title = "Breaking News"
        article.description = None

        text = _get_text_for_analysis(article)
        assert text == "Breaking News"

    def test_uses_description_when_no_title(self):
        """Should use description when no title."""
        from src.lambdas.ingestion.handler import _get_text_for_analysis

        article = create_news_article()
        article.title = None
        article.description = "Important development"

        text = _get_text_for_analysis(article)
        assert text == "Important development"


class TestPublishSnsBatch:
    """Tests for _publish_sns_batch function (DFA-002)."""

    def test_publishes_batch_successfully(self):
        """Should publish batch of messages using publish_batch API."""
        from src.lambdas.ingestion.handler import _publish_sns_batch

        mock_sns = MagicMock()
        mock_sns.publish_batch.return_value = {
            "Successful": [{"Id": "0"}, {"Id": "1"}],
            "Failed": [],
        }

        messages = [
            {"source_type": "tiingo", "body": {"source_id": "t:1"}},
            {"source_type": "finnhub", "body": {"source_id": "f:1"}},
        ]

        result = _publish_sns_batch(
            sns_client=mock_sns,
            sns_topic_arn="arn:aws:sns:us-east-1:123:topic",
            messages=messages,
        )

        assert result == 2
        mock_sns.publish_batch.assert_called_once()

    def test_handles_empty_messages(self):
        """Should handle empty messages list."""
        from src.lambdas.ingestion.handler import _publish_sns_batch

        mock_sns = MagicMock()

        result = _publish_sns_batch(
            sns_client=mock_sns,
            sns_topic_arn="arn:aws:sns:us-east-1:123:topic",
            messages=[],
        )

        assert result == 0
        mock_sns.publish_batch.assert_not_called()

    def test_batches_large_message_list(self):
        """Should split large message list into batches of 10."""
        from src.lambdas.ingestion.handler import _publish_sns_batch

        mock_sns = MagicMock()
        mock_sns.publish_batch.return_value = {
            "Successful": [{"Id": str(i)} for i in range(10)],
            "Failed": [],
        }

        # 25 messages should result in 3 batches (10 + 10 + 5)
        messages = [
            {"source_type": "tiingo", "body": {"source_id": f"t:{i}"}}
            for i in range(25)
        ]

        result = _publish_sns_batch(
            sns_client=mock_sns,
            sns_topic_arn="arn:aws:sns:us-east-1:123:topic",
            messages=messages,
        )

        # 3 batches called
        assert mock_sns.publish_batch.call_count == 3
        assert result == 30  # 10 + 10 + 10 from mocked responses

    def test_handles_partial_failures(self):
        """Should handle partial batch failures and return correct count."""
        from src.lambdas.ingestion.handler import _publish_sns_batch

        mock_sns = MagicMock()
        mock_sns.publish_batch.return_value = {
            "Successful": [{"Id": "0"}, {"Id": "1"}],
            "Failed": [{"Id": "2", "Code": "InvalidParameter", "Message": "Bad msg"}],
        }

        messages = [
            {"source_type": "tiingo", "body": {"source_id": "t:1"}},
            {"source_type": "tiingo", "body": {"source_id": "t:2"}},
            {"source_type": "tiingo", "body": {"source_id": "t:3"}},
        ]

        result = _publish_sns_batch(
            sns_client=mock_sns,
            sns_topic_arn="arn:aws:sns:us-east-1:123:topic",
            messages=messages,
        )

        assert result == 2  # Only 2 successful


class TestLambdaHandler:
    """Integration tests for lambda_handler function."""

    @mock_aws
    def test_returns_success_with_no_tickers(self, env_vars):
        """Should return success when no active tickers.

        (502-gsi-query-optimization: Updated to use GSI table)
        """
        from src.lambdas.ingestion.handler import lambda_handler

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_with_gsi(dynamodb)

        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        with (
            patch(
                "src.lambdas.ingestion.handler.get_api_key",
                return_value="test-key",
            ),
            patch(
                "src.lambdas.ingestion.handler.emit_metrics_batch",
            ),
        ):
            response = lambda_handler({"source": "test"}, mock_context)

        assert response["statusCode"] == 200
        assert response["body"]["message"] == "No active tickers"

    @mock_aws
    def test_processes_tickers_from_configurations(self, env_vars):
        """Should process tickers from active configurations.

        (502-gsi-query-optimization: Updated to use GSI table and status attribute)
        """
        from src.lambdas.ingestion.handler import lambda_handler

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table_with_gsi(dynamodb)

        # Add a configuration (status="active" for GSI query)
        table.put_item(
            Item={
                "PK": "USER#user1",
                "SK": "CONFIG#config1",
                "entity_type": "CONFIGURATION",
                "status": "active",
                "tickers": [{"symbol": "AAPL"}],
            }
        )

        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        mock_tiingo = MagicMock()
        mock_tiingo.get_news.return_value = [
            create_news_article("t1", "tiingo", "Tiingo Article", ["AAPL"])
        ]
        mock_tiingo.close = MagicMock()

        mock_finnhub = MagicMock()
        mock_finnhub.get_news.return_value = [
            create_news_article("f1", "finnhub", "Finnhub Article", ["AAPL"])
        ]
        mock_finnhub.close = MagicMock()

        with (
            patch(
                "src.lambdas.ingestion.handler.get_api_key",
                return_value="test-key",
            ),
            patch(
                "src.lambdas.ingestion.handler.TiingoAdapter",
                return_value=mock_tiingo,
            ),
            patch(
                "src.lambdas.ingestion.handler.FinnhubAdapter",
                return_value=mock_finnhub,
            ),
            # Feature 1010: Mock upsert_article_with_source instead of put_item_if_not_exists
            patch(
                "src.lambdas.ingestion.handler.upsert_article_with_source",
                return_value="created",
            ),
            patch(
                "src.lambdas.ingestion.handler._get_sns_client",
                return_value=MagicMock(),
            ),
            patch(
                "src.lambdas.ingestion.handler.emit_metrics_batch",
            ),
        ):
            response = lambda_handler({"source": "test"}, mock_context)

        assert response["statusCode"] == 200
        assert response["body"]["summary"]["tickers_processed"] == 1
        assert response["body"]["summary"]["tiingo_articles"] == 1
        assert response["body"]["summary"]["finnhub_articles"] == 1
        assert response["body"]["summary"]["new_items"] == 2

    @mock_aws
    def test_handles_rate_limit_errors(self, env_vars):
        """Should handle rate limit errors gracefully.

        (502-gsi-query-optimization: Updated to use GSI table and status attribute)
        """
        from src.lambdas.ingestion.handler import lambda_handler

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table_with_gsi(dynamodb)

        # Add a configuration (status="active" for GSI query)
        table.put_item(
            Item={
                "PK": "USER#user1",
                "SK": "CONFIG#config1",
                "entity_type": "CONFIGURATION",
                "status": "active",
                "tickers": [{"symbol": "AAPL"}],
            }
        )

        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        mock_tiingo = MagicMock()
        mock_tiingo.get_news.side_effect = RateLimitError(
            "Rate limited", retry_after=60
        )
        mock_tiingo.close = MagicMock()

        mock_finnhub = MagicMock()
        mock_finnhub.get_news.return_value = []
        mock_finnhub.close = MagicMock()

        with (
            patch(
                "src.lambdas.ingestion.handler.get_api_key",
                return_value="test-key",
            ),
            patch(
                "src.lambdas.ingestion.handler.TiingoAdapter",
                return_value=mock_tiingo,
            ),
            patch(
                "src.lambdas.ingestion.handler.FinnhubAdapter",
                return_value=mock_finnhub,
            ),
            patch(
                "src.lambdas.ingestion.handler._get_sns_client",
                return_value=MagicMock(),
            ),
            patch(
                "src.lambdas.ingestion.handler.emit_metrics_batch",
            ),
            patch(
                "src.lambdas.ingestion.handler.emit_metric",
            ),
        ):
            response = lambda_handler({"source": "test"}, mock_context)

        # Should return 207 (partial content) due to errors
        assert response["statusCode"] == 207
        assert response["body"]["summary"]["errors"] == 1
        assert len(response["body"]["errors"]) == 1
        # Feature 1010: Parallel fetcher passes through exception message
        # rather than normalizing to error codes
        assert "Rate limited" in response["body"]["errors"][0]["error"]
