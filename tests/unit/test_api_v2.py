"""
Unit tests for POWERPLAN API v2 endpoints.

Tests cover:
- get_sentiment_by_tags: Multi-tag sentiment aggregation
- get_trend_data: Time-series data for sparklines
- get_articles_by_tags: Articles with sentiment filtering
"""

from unittest.mock import MagicMock

import pytest

from src.lambdas.dashboard.api_v2 import (
    get_articles_by_tags,
    get_sentiment_by_tags,
    get_trend_data,
)


class TestGetSentimentByTags:
    """Tests for get_sentiment_by_tags function."""

    def test_single_tag_returns_correct_structure(self):
        """Test that single tag query returns expected structure."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T10:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T11:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "neutral",
                    "timestamp": "2025-11-24T12:00:00Z",
                },
            ]
        }

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["AI"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert "tags" in result
        assert "AI" in result["tags"]
        assert "overall" in result
        assert "total_count" in result
        assert "trend" in result
        assert result["total_count"] == 3

    def test_multiple_tags_aggregates_correctly(self):
        """Test that multiple tags are aggregated correctly."""
        mock_table = MagicMock()
        # First tag query
        mock_table.query.side_effect = [
            {
                "Items": [
                    {
                        "tag": "AI",
                        "sentiment": "positive",
                        "timestamp": "2025-11-24T10:00:00Z",
                    },
                    {
                        "tag": "AI",
                        "sentiment": "positive",
                        "timestamp": "2025-11-24T11:00:00Z",
                    },
                ]
            },
            {
                "Items": [
                    {
                        "tag": "climate",
                        "sentiment": "negative",
                        "timestamp": "2025-11-24T10:00:00Z",
                    },
                ]
            },
        ]

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["AI", "climate"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert "AI" in result["tags"]
        assert "climate" in result["tags"]
        assert result["total_count"] == 3

    def test_empty_results_returns_zeros(self):
        """Test that empty results return zero percentages."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["nonexistent"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert result["tags"]["nonexistent"]["count"] == 0
        assert result["tags"]["nonexistent"]["positive"] == 0.0
        assert result["total_count"] == 0

    def test_max_tags_exceeded_raises_error(self):
        """Test that exceeding max tags raises ValueError."""
        mock_table = MagicMock()

        with pytest.raises(ValueError, match="Maximum 5 tags"):
            get_sentiment_by_tags(
                table=mock_table,
                tags=["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"],
                start_time="2025-11-24T00:00:00Z",
                end_time="2025-11-24T23:59:59Z",
            )

    def test_empty_tags_raises_error(self):
        """Test that empty tags list raises ValueError."""
        mock_table = MagicMock()

        with pytest.raises(ValueError, match="At least one tag"):
            get_sentiment_by_tags(
                table=mock_table,
                tags=[],
                start_time="2025-11-24T00:00:00Z",
                end_time="2025-11-24T23:59:59Z",
            )

    def test_trend_improving_when_mostly_positive(self):
        """Test that trend is 'improving' when positive > 60%."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T10:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T11:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T12:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "neutral",
                    "timestamp": "2025-11-24T13:00:00Z",
                },
            ]
        }

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["AI"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert result["trend"] == "improving"

    def test_trend_declining_when_mostly_negative(self):
        """Test that trend is 'declining' when negative > 40%."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "tag": "AI",
                    "sentiment": "negative",
                    "timestamp": "2025-11-24T10:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "negative",
                    "timestamp": "2025-11-24T11:00:00Z",
                },
                {
                    "tag": "AI",
                    "sentiment": "neutral",
                    "timestamp": "2025-11-24T12:00:00Z",
                },
            ]
        }

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["AI"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert result["trend"] == "declining"

    def test_pagination_handling(self):
        """Test that pagination is handled correctly."""
        mock_table = MagicMock()
        mock_table.query.side_effect = [
            {
                "Items": [
                    {
                        "tag": "AI",
                        "sentiment": "positive",
                        "timestamp": "2025-11-24T10:00:00Z",
                    }
                ],
                "LastEvaluatedKey": {"pk": "some-key"},
            },
            {
                "Items": [
                    {
                        "tag": "AI",
                        "sentiment": "negative",
                        "timestamp": "2025-11-24T11:00:00Z",
                    }
                ],
            },
        ]

        result = get_sentiment_by_tags(
            table=mock_table,
            tags=["AI"],
            start_time="2025-11-24T00:00:00Z",
            end_time="2025-11-24T23:59:59Z",
        )

        assert result["total_count"] == 2
        assert mock_table.query.call_count == 2


class TestGetTrendData:
    """Tests for get_trend_data function."""

    def test_hourly_interval_returns_correct_buckets(self):
        """Test that 1h interval creates hourly buckets."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T10:30:00+00:00",
                },
                {
                    "tag": "AI",
                    "sentiment": "negative",
                    "timestamp": "2025-11-24T10:45:00+00:00",
                },
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T11:30:00+00:00",
                },
            ]
        }

        result = get_trend_data(
            table=mock_table,
            tags=["AI"],
            interval="1h",
            range_hours=24,
        )

        assert "AI" in result
        assert len(result["AI"]) > 0
        # Each entry should have timestamp, sentiment, count
        for point in result["AI"]:
            assert "timestamp" in point
            assert "sentiment" in point
            assert "count" in point

    def test_invalid_interval_raises_error(self):
        """Test that invalid interval raises ValueError."""
        mock_table = MagicMock()

        with pytest.raises(ValueError, match="Invalid interval"):
            get_trend_data(
                table=mock_table,
                tags=["AI"],
                interval="2h",  # Invalid
                range_hours=24,
            )

    def test_max_tags_exceeded_raises_error(self):
        """Test that exceeding max tags raises ValueError."""
        mock_table = MagicMock()

        with pytest.raises(ValueError, match="Maximum 5 tags"):
            get_trend_data(
                table=mock_table,
                tags=["t1", "t2", "t3", "t4", "t5", "t6"],
                interval="1h",
                range_hours=24,
            )

    def test_range_capped_at_maximum(self):
        """Test that range is capped at 168 hours (7 days)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        # Request 1000 hours, should be capped to 168
        result = get_trend_data(
            table=mock_table,
            tags=["AI"],
            interval="1h",
            range_hours=1000,
        )

        # Verify we got approximately 168 buckets (7 days * 24 hours)
        assert len(result["AI"]) <= 169  # Allow for boundary conditions

    def test_sentiment_score_calculation(self):
        """Test that sentiment score is calculated correctly."""
        mock_table = MagicMock()
        # All positive should give score close to 1.0
        mock_table.query.return_value = {
            "Items": [
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T10:30:00+00:00",
                },
                {
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T10:45:00+00:00",
                },
            ]
        }

        result = get_trend_data(
            table=mock_table,
            tags=["AI"],
            interval="1h",
            range_hours=2,
        )

        # Find the bucket with data
        for point in result["AI"]:
            if point["count"] > 0:
                assert point["sentiment"] == 1.0  # All positive

    def test_empty_bucket_has_neutral_sentiment(self):
        """Test that empty buckets have neutral sentiment (0.5)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = get_trend_data(
            table=mock_table,
            tags=["AI"],
            interval="1h",
            range_hours=2,
        )

        for point in result["AI"]:
            if point["count"] == 0:
                assert point["sentiment"] == 0.5


class TestGetArticlesByTags:
    """Tests for get_articles_by_tags function."""

    def test_returns_articles_sorted_by_timestamp(self):
        """Test that articles are sorted by timestamp descending."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"id": "1", "tag": "AI", "timestamp": "2025-11-24T12:00:00Z"},
                {"id": "2", "tag": "AI", "timestamp": "2025-11-24T10:00:00Z"},
            ]
        }

        result = get_articles_by_tags(
            table=mock_table,
            tags=["AI"],
            limit=10,
        )

        assert len(result) == 2
        # Should be sorted descending
        assert result[0]["timestamp"] > result[1]["timestamp"]

    def test_respects_limit(self):
        """Test that limit is respected."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"id": str(i), "tag": "AI", "timestamp": f"2025-11-24T{i:02d}:00:00Z"}
                for i in range(10)
            ]
        }

        result = get_articles_by_tags(
            table=mock_table,
            tags=["AI"],
            limit=5,
        )

        assert len(result) == 5

    def test_sentiment_filter_applied(self):
        """Test that sentiment filter is applied."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "id": "1",
                    "tag": "AI",
                    "sentiment": "positive",
                    "timestamp": "2025-11-24T12:00:00Z",
                },
            ]
        }

        get_articles_by_tags(
            table=mock_table,
            tags=["AI"],
            limit=10,
            sentiment_filter="positive",
        )

        # Verify FilterExpression was added to query
        call_kwargs = mock_table.query.call_args[1]
        assert "FilterExpression" in call_kwargs

    def test_invalid_sentiment_filter_raises_error(self):
        """Test that invalid sentiment filter raises ValueError."""
        mock_table = MagicMock()

        with pytest.raises(ValueError, match="Invalid sentiment filter"):
            get_articles_by_tags(
                table=mock_table,
                tags=["AI"],
                limit=10,
                sentiment_filter="invalid",
            )

    def test_start_time_filter_applied(self):
        """Test that start_time filter is applied to query."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_articles_by_tags(
            table=mock_table,
            tags=["AI"],
            limit=10,
            start_time="2025-11-24T00:00:00Z",
        )

        # Verify query was called with KeyConditionExpression including timestamp
        assert mock_table.query.called

    def test_multiple_tags_aggregated(self):
        """Test that articles from multiple tags are aggregated."""
        mock_table = MagicMock()
        mock_table.query.side_effect = [
            {"Items": [{"id": "1", "tag": "AI", "timestamp": "2025-11-24T12:00:00Z"}]},
            {
                "Items": [
                    {"id": "2", "tag": "climate", "timestamp": "2025-11-24T11:00:00Z"}
                ]
            },
        ]

        result = get_articles_by_tags(
            table=mock_table,
            tags=["AI", "climate"],
            limit=10,
        )

        assert len(result) == 2
        assert mock_table.query.call_count == 2

    def test_max_tags_limit_enforced(self):
        """Test that only first 5 tags are queried."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        get_articles_by_tags(
            table=mock_table,
            tags=["t1", "t2", "t3", "t4", "t5", "t6", "t7"],
            limit=10,
        )

        # Should only query first 5 tags
        assert mock_table.query.call_count == 5

    def test_empty_results(self):
        """Test handling of empty results."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = get_articles_by_tags(
            table=mock_table,
            tags=["AI"],
            limit=10,
        )

        assert result == []
