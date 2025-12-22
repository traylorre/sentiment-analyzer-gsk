"""Unit tests for cross-source deduplication.

Tests dedup behavior when same article appears in both Tiingo and Finnhub.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.lambdas.ingestion.dedup import (
    build_source_attribution,
    generate_dedup_key,
    normalize_headline,
    upsert_article_with_source,
)


@pytest.fixture
def mock_table():
    """Create mock DynamoDB table."""
    return MagicMock()


class TestCrossSourceDedup:
    """Tests for cross-source deduplication logic."""

    def test_same_headline_different_sources_creates_one_record(self):
        """Same article from Tiingo and Finnhub produces same dedup key."""
        headline_tiingo = "Apple Reports Q4 Earnings Beat"
        headline_finnhub = "Apple reports Q4 earnings beat"
        date = "2025-12-21"

        key_tiingo = generate_dedup_key(headline_tiingo, date)
        key_finnhub = generate_dedup_key(headline_finnhub, date)

        assert key_tiingo == key_finnhub

    def test_tiingo_first_finnhub_updates_sources(self, mock_table):
        """When Tiingo article exists, Finnhub updates sources array."""
        dedup_key = "abc123def456"
        timestamp = "2025-12-21T10:30:00Z"

        # First insert from Tiingo succeeds
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="12345",
            url="https://tiingo.com/article",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Apple Reports Q4",
        )

        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        mock_table.get_item.return_value = {}  # No existing item
        mock_table.put_item.return_value = None

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=tiingo_attr,
            item_data={"headline": "Apple Reports Q4", "status": "pending"},
        )

        assert result == "created"
        mock_table.put_item.assert_called_once()

        # Now Finnhub comes with same article
        mock_table.reset_mock()
        # Clear the side_effect so update_item returns successfully
        mock_table.update_item.side_effect = None
        mock_table.update_item.return_value = None  # Update succeeds

        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="abc-def",
            url="https://finnhub.io/article",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Apple reports Q4",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="finnhub",
            attribution=finnhub_attr,
            item_data={"headline": "Apple reports Q4", "status": "pending"},
        )

        assert result == "updated"
        mock_table.update_item.assert_called_once()

    def test_finnhub_first_tiingo_updates_sources(self, mock_table):
        """When Finnhub article exists, Tiingo updates sources array."""
        dedup_key = "xyz789abc123"
        timestamp = "2025-12-21T11:00:00Z"

        # Setup: Finnhub already exists
        mock_table.update_item.return_value = None  # Update succeeds

        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="67890",
            url="https://tiingo.com/article2",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Tesla Deliveries Beat",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key=dedup_key,
            timestamp=timestamp,
            source="tiingo",
            attribution=tiingo_attr,
            item_data={"headline": "Tesla Deliveries Beat", "status": "pending"},
        )

        assert result == "updated"

    def test_normalized_headlines_match_with_punctuation(self):
        """Headlines with punctuation differences still match."""
        date = "2025-12-21"

        tiingo = "What's Next? Apple's Big Announcement!"
        finnhub = "Whats Next Apples Big Announcement"

        assert generate_dedup_key(tiingo, date) == generate_dedup_key(finnhub, date)

    def test_normalized_headlines_match_with_case(self):
        """Headlines with case differences still match."""
        date = "2025-12-21"

        tiingo = "BREAKING: Apple Announces iPhone 16"
        finnhub = "Breaking: Apple announces iPhone 16"

        # Both normalize to "breaking apple announces iphone 16"
        assert normalize_headline(tiingo) == normalize_headline(finnhub)
        assert generate_dedup_key(tiingo, date) == generate_dedup_key(finnhub, date)


class TestUpsertArticleWithSource:
    """Tests for upsert_article_with_source function."""

    def test_creates_new_article_when_not_exists(self, mock_table):
        """Creates new article when it doesn't exist."""
        # Update fails (article doesn't exist)
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        mock_table.get_item.return_value = {}  # No existing item
        mock_table.put_item.return_value = None

        attr = build_source_attribution(
            source="tiingo",
            article_id="123",
            url="https://test.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key="testkey123",
            timestamp="2025-12-21T10:00:00Z",
            source="tiingo",
            attribution=attr,
            item_data={"headline": "Test", "status": "pending"},
        )

        assert result == "created"
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["source_id"] == "dedup:testkey123"
        assert item["sources"] == ["tiingo"]
        assert "tiingo" in item["source_attribution"]

    def test_updates_existing_article_with_new_source(self, mock_table):
        """Updates existing article to add new source."""
        mock_table.update_item.return_value = None  # Update succeeds

        attr = build_source_attribution(
            source="finnhub",
            article_id="abc",
            url="https://test.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key="existingkey",
            timestamp="2025-12-21T10:00:00Z",
            source="finnhub",
            attribution=attr,
            item_data={},
        )

        assert result == "updated"
        mock_table.update_item.assert_called_once()

    def test_returns_duplicate_when_source_already_present(self, mock_table):
        """Returns 'duplicate' when source is already in sources array."""
        # Update fails because source already present
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        # Article exists with source already present
        mock_table.get_item.return_value = {"Item": {"sources": ["tiingo"]}}

        attr = build_source_attribution(
            source="tiingo",
            article_id="123",
            url="https://test.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key="duplicatekey",
            timestamp="2025-12-21T10:00:00Z",
            source="tiingo",
            attribution=attr,
            item_data={},
        )

        assert result == "duplicate"

    def test_handles_race_condition_on_create(self, mock_table):
        """Handles race condition when another thread creates the article."""
        # First update fails (doesn't exist)
        mock_table.update_item.side_effect = [
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
            ),
            None,  # Second update succeeds (after retry)
        ]
        mock_table.get_item.return_value = {}  # No existing item
        # Put fails because another thread created it
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )

        attr = build_source_attribution(
            source="tiingo",
            article_id="123",
            url="https://test.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        result = upsert_article_with_source(
            table=mock_table,
            dedup_key="racekey",
            timestamp="2025-12-21T10:00:00Z",
            source="tiingo",
            attribution=attr,
            item_data={},
        )

        # Should retry and succeed with update
        assert result == "updated"


class TestBuildSourceAttribution:
    """Tests for build_source_attribution function."""

    def test_builds_complete_attribution(self):
        """Builds attribution with all required fields."""
        now = datetime.now(UTC)
        attr = build_source_attribution(
            source="tiingo",
            article_id="91144751",
            url="https://example.com/article",
            crawl_timestamp=now,
            original_headline="Apple Reports Q4 - Reuters",
            source_name="reuters",
        )

        assert attr["article_id"] == "91144751"
        assert attr["url"] == "https://example.com/article"
        assert attr["crawl_timestamp"] == now.isoformat()
        assert attr["original_headline"] == "Apple Reports Q4 - Reuters"
        assert attr["source_name"] == "reuters"

    def test_source_name_optional(self):
        """source_name is optional."""
        attr = build_source_attribution(
            source="finnhub",
            article_id="abc-123",
            url="https://example.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        assert "source_name" not in attr

    def test_empty_url_handled(self):
        """Empty URL is stored as empty string."""
        attr = build_source_attribution(
            source="tiingo",
            article_id="123",
            url="",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        assert attr["url"] == ""

    def test_article_id_converted_to_string(self):
        """Article ID is converted to string."""
        attr = build_source_attribution(
            source="tiingo",
            article_id=12345,  # Integer
            url="https://test.com",
            crawl_timestamp=datetime.now(UTC),
            original_headline="Test",
        )

        assert attr["article_id"] == "12345"
        assert isinstance(attr["article_id"], str)
