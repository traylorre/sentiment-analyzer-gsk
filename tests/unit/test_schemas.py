"""
Unit Tests for Pydantic Validation Schemas
==========================================

Tests all schema models with valid and invalid inputs.

For On-Call Engineers:
    If validation errors occur in production, check these tests
    for expected input formats. Common issues:
    - source_id must start with "newsapi#"
    - timestamp must be ISO8601
    - sentiment must be positive/neutral/negative
    - score must be 0.0-1.0

For Developers:
    - Test both valid and invalid inputs for each schema
    - Test edge cases (empty strings, boundary values)
    - Test field validators with specific error messages
"""

import pytest
from pydantic import ValidationError

from src.lambdas.shared.schemas import (
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    SentimentItemCreate,
    SentimentItemResponse,
    SentimentItemUpdate,
    SNSAnalysisMessage,
)


class TestSentimentItemCreate:
    """Tests for SentimentItemCreate schema."""

    def test_valid_item(self):
        """Test valid item creation."""
        item = SentimentItemCreate(
            source_id="newsapi#abc123def456",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test Article Title",
            snippet="Test article content for analysis...",
            url="https://example.com/article/123",
            tag="AI",
            ttl_timestamp=1734444600,
        )

        assert item.source_id == "newsapi#abc123def456"
        assert item.status == "pending"  # default

    def test_valid_item_with_optional_fields(self):
        """Test valid item with optional fields."""
        item = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test Article",
            snippet="Content",
            url="https://example.com/article",
            tag="climate",
            ttl_timestamp=1734444600,
            author="Test Author",
            source_name="Test News",
        )

        assert item.author == "Test Author"
        assert item.source_name == "Test News"

    def test_invalid_source_id_prefix(self):
        """Test that source_id must start with 'newsapi#'."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentItemCreate(
                source_id="invalid#abc123",
                timestamp="2025-11-17T14:30:00.000Z",
                title="Test",
                snippet="Content",
                url="https://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )

        assert "source_id must start with 'newsapi#'" in str(exc_info.value)

    def test_invalid_timestamp_format(self):
        """Test that timestamp must be ISO8601."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentItemCreate(
                source_id="newsapi#abc123",
                timestamp="invalid-timestamp",
                title="Test",
                snippet="Content",
                url="https://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )

        assert "Invalid ISO8601 timestamp" in str(exc_info.value)

    def test_invalid_url_format(self):
        """Test that URL must start with http/https."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentItemCreate(
                source_id="newsapi#abc123",
                timestamp="2025-11-17T14:30:00.000Z",
                title="Test",
                snippet="Content",
                url="ftp://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )

        assert "URL must start with http" in str(exc_info.value)

    def test_snippet_max_length(self):
        """Test that snippet is limited to 200 chars."""
        with pytest.raises(ValidationError):
            SentimentItemCreate(
                source_id="newsapi#abc123",
                timestamp="2025-11-17T14:30:00.000Z",
                title="Test",
                snippet="x" * 201,  # Too long
                url="https://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )

    def test_empty_title_rejected(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError):
            SentimentItemCreate(
                source_id="newsapi#abc123",
                timestamp="2025-11-17T14:30:00.000Z",
                title="",  # Empty
                snippet="Content",
                url="https://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )

    def test_missing_required_field(self):
        """Test that missing required field raises error."""
        with pytest.raises(ValidationError):
            SentimentItemCreate(
                source_id="newsapi#abc123",
                # missing timestamp
                title="Test",
                snippet="Content",
                url="https://example.com",
                tag="AI",
                ttl_timestamp=1734444600,
            )


class TestSentimentItemUpdate:
    """Tests for SentimentItemUpdate schema."""

    def test_valid_update(self):
        """Test valid analysis result update."""
        update = SentimentItemUpdate(
            sentiment="positive",
            score=0.95,
            model_version="v1.0.0",
        )

        assert update.sentiment == "positive"
        assert update.score == 0.95
        assert update.status == "analyzed"  # default

    def test_all_sentiment_values(self):
        """Test all valid sentiment values."""
        for sentiment in ["positive", "neutral", "negative"]:
            update = SentimentItemUpdate(
                sentiment=sentiment,
                score=0.8,
                model_version="v1.0.0",
            )
            assert update.sentiment == sentiment

    def test_invalid_sentiment_value(self):
        """Test that invalid sentiment is rejected."""
        with pytest.raises(ValidationError):
            SentimentItemUpdate(
                sentiment="invalid",
                score=0.8,
                model_version="v1.0.0",
            )

    def test_score_out_of_range_high(self):
        """Test that score > 1.0 is rejected."""
        with pytest.raises(ValidationError):
            SentimentItemUpdate(
                sentiment="positive",
                score=1.5,
                model_version="v1.0.0",
            )

    def test_score_out_of_range_low(self):
        """Test that score < 0.0 is rejected."""
        with pytest.raises(ValidationError):
            SentimentItemUpdate(
                sentiment="positive",
                score=-0.1,
                model_version="v1.0.0",
            )

    def test_score_boundary_values(self):
        """Test boundary values for score."""
        # Minimum
        update_min = SentimentItemUpdate(
            sentiment="negative",
            score=0.0,
            model_version="v1.0.0",
        )
        assert update_min.score == 0.0

        # Maximum
        update_max = SentimentItemUpdate(
            sentiment="positive",
            score=1.0,
            model_version="v1.0.0",
        )
        assert update_max.score == 1.0

    def test_score_precision(self):
        """Test that score is rounded to 4 decimal places."""
        update = SentimentItemUpdate(
            sentiment="neutral",
            score=0.123456789,
            model_version="v1.0.0",
        )
        assert update.score == 0.1235

    def test_invalid_model_version_format(self):
        """Test that model version must match pattern."""
        with pytest.raises(ValidationError):
            SentimentItemUpdate(
                sentiment="positive",
                score=0.8,
                model_version="1.0.0",  # Missing 'v' prefix
            )


class TestSentimentItemResponse:
    """Tests for SentimentItemResponse schema."""

    def test_valid_analyzed_item(self):
        """Test valid analyzed item response."""
        response = SentimentItemResponse(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test Article",
            snippet="Content",
            url="https://example.com",
            tag="AI",
            status="analyzed",
            sentiment="positive",
            score=0.95,
            model_version="v1.0.0",
        )

        assert response.sentiment == "positive"

    def test_valid_pending_item(self):
        """Test valid pending item response (no analysis fields)."""
        response = SentimentItemResponse(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test Article",
            snippet="Content",
            url="https://example.com",
            tag="AI",
            status="pending",
            # No sentiment, score, model_version
        )

        assert response.sentiment is None
        assert response.score is None


class TestSNSAnalysisMessage:
    """Tests for SNSAnalysisMessage schema."""

    def test_valid_message(self):
        """Test valid SNS message."""
        message = SNSAnalysisMessage(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            text_for_analysis="Test Article Title. Content for analysis.",
            correlation_id="newsapi#abc123-request-123",
        )

        assert message.source_id == "newsapi#abc123"

    def test_empty_text_rejected(self):
        """Test that empty analysis text is rejected."""
        with pytest.raises(ValidationError):
            SNSAnalysisMessage(
                source_id="newsapi#abc123",
                timestamp="2025-11-17T14:30:00.000Z",
                text_for_analysis="",  # Empty
                correlation_id="newsapi#abc123-request-123",
            )


class TestMetricsResponse:
    """Tests for MetricsResponse schema."""

    def test_valid_metrics(self):
        """Test valid metrics response."""
        metrics = MetricsResponse(
            total_items=100,
            analyzed_items=80,
            pending_items=20,
            sentiment_distribution={"positive": 40, "neutral": 30, "negative": 10},
            tag_distribution={"AI": 50, "climate": 30, "economy": 20},
            recent_items=[],
            last_updated="2025-11-17T14:30:00.000Z",
        )

        assert metrics.total_items == 100

    def test_invalid_counts(self):
        """Test that counts must be consistent."""
        with pytest.raises(ValidationError) as exc_info:
            MetricsResponse(
                total_items=100,
                analyzed_items=50,
                pending_items=30,  # 50 + 30 != 100
                sentiment_distribution={},
                tag_distribution={},
                recent_items=[],
                last_updated="2025-11-17T14:30:00.000Z",
            )

        assert "must equal total_items" in str(exc_info.value)

    def test_recent_items_max_length(self):
        """Test that recent_items is limited to 20."""
        # Create 21 items
        items = [
            SentimentItemResponse(
                source_id=f"newsapi#item{i}",
                timestamp="2025-11-17T14:30:00.000Z",
                title=f"Item {i}",
                snippet="Content",
                url="https://example.com",
                tag="AI",
                status="analyzed",
            )
            for i in range(21)
        ]

        with pytest.raises(ValidationError):
            MetricsResponse(
                total_items=21,
                analyzed_items=21,
                pending_items=0,
                sentiment_distribution={},
                tag_distribution={},
                recent_items=items,  # Too many
                last_updated="2025-11-17T14:30:00.000Z",
            )


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_healthy_response(self):
        """Test healthy status response."""
        health = HealthResponse(
            status="healthy",
            dynamodb="connected",
            timestamp="2025-11-17T14:30:00.000Z",
            version="v1.0.0",
        )

        assert health.status == "healthy"

    def test_all_status_values(self):
        """Test all valid status values."""
        for status in ["healthy", "degraded", "unhealthy"]:
            health = HealthResponse(
                status=status,
                dynamodb="connected",
                timestamp="2025-11-17T14:30:00.000Z",
                version="v1.0.0",
            )
            assert health.status == status

    def test_invalid_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValidationError):
            HealthResponse(
                status="invalid",
                dynamodb="connected",
                timestamp="2025-11-17T14:30:00.000Z",
                version="v1.0.0",
            )


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_basic_error(self):
        """Test basic error response."""
        error = ErrorResponse(
            error="Something went wrong",
            code="DATABASE_ERROR",
            request_id="request-123",
        )

        assert error.error == "Something went wrong"
        assert error.details is None

    def test_error_with_details(self):
        """Test error response with details."""
        error = ErrorResponse(
            error="Validation failed",
            code="VALIDATION_ERROR",
            details={"field": "score", "issue": "out of range"},
            request_id="request-123",
        )

        assert error.details["field"] == "score"

    def test_all_error_codes(self):
        """Test that all documented error codes are valid."""
        codes = [
            "RATE_LIMIT_EXCEEDED",
            "VALIDATION_ERROR",
            "NOT_FOUND",
            "SECRET_ERROR",
            "DATABASE_ERROR",
        ]

        for code in codes:
            error = ErrorResponse(
                error="Test error",
                code=code,
                request_id="request-123",
            )
            assert error.code == code


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unicode_in_title(self):
        """Test unicode characters in title."""
        item = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test Article with émojis 🚀 and ñ",
            snippet="Content with special chars: αβγ",
            url="https://example.com",
            tag="AI",
            ttl_timestamp=1734444600,
        )

        assert "🚀" in item.title

    def test_timestamp_with_timezone(self):
        """Test various timezone formats."""
        # UTC with Z
        item1 = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test",
            snippet="Content",
            url="https://example.com",
            tag="AI",
            ttl_timestamp=1734444600,
        )
        assert item1.timestamp.endswith("Z")

        # With offset
        item2 = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00+00:00",
            title="Test",
            snippet="Content",
            url="https://example.com",
            tag="AI",
            ttl_timestamp=1734444600,
        )
        assert "+00:00" in item2.timestamp

    def test_http_url_allowed(self):
        """Test that http:// URLs are allowed (not just https)."""
        item = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test",
            snippet="Content",
            url="http://example.com",  # http, not https
            tag="AI",
            ttl_timestamp=1734444600,
        )

        assert item.url.startswith("http://")

    def test_model_dict_serialization(self):
        """Test that models serialize to dict correctly."""
        item = SentimentItemCreate(
            source_id="newsapi#abc123",
            timestamp="2025-11-17T14:30:00.000Z",
            title="Test",
            snippet="Content",
            url="https://example.com",
            tag="AI",
            ttl_timestamp=1734444600,
        )

        data = item.model_dump()
        assert isinstance(data, dict)
        assert data["source_id"] == "newsapi#abc123"
        assert data["status"] == "pending"
