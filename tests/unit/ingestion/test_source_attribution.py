"""Tests for multi-source attribution tracking.

Feature 1010 Phase 5: User Story 3 - Multi-Source Attribution Tracking

Tests that each article tracks which sources provided it with
detailed per-source metadata.
"""

from datetime import datetime

from src.lambdas.ingestion.dedup import build_source_attribution


class TestSourceAttribution:
    """Tests for source attribution building and structure."""

    def test_single_source_article_has_one_attribution(self) -> None:
        """Single source article should have exactly one attribution entry."""
        attribution = build_source_attribution(
            source="tiingo",
            article_id="91144751",
            url="https://example.com/article",
            crawl_timestamp=datetime(2025, 12, 21, 10, 30, 0),
            original_headline="Apple Reports Q4 Earnings Beat - Reuters",
            source_name="reuters",
        )

        # Verify all required fields present
        assert "article_id" in attribution
        assert "url" in attribution
        assert "crawl_timestamp" in attribution
        assert "original_headline" in attribution
        assert "source_name" in attribution

        # Verify values
        assert attribution["article_id"] == "91144751"
        assert attribution["url"] == "https://example.com/article"
        assert (
            attribution["original_headline"]
            == "Apple Reports Q4 Earnings Beat - Reuters"
        )
        assert attribution["source_name"] == "reuters"

    def test_attribution_contains_required_fields(self) -> None:
        """Attribution must contain article_id, url, crawl_timestamp, original_headline."""
        attribution = build_source_attribution(
            source="finnhub",
            article_id="abc-def-123",
            url="https://finnhub.io/news/abc",
            crawl_timestamp=datetime(2025, 12, 21, 14, 0, 0),
            original_headline="AAPL: Strong quarter reported",
        )

        required_fields = ["article_id", "url", "crawl_timestamp", "original_headline"]
        for field in required_fields:
            assert field in attribution, f"Missing required field: {field}"

    def test_attribution_without_source_name(self) -> None:
        """Attribution without source_name should not include the field."""
        attribution = build_source_attribution(
            source="tiingo",
            article_id="12345",
            url="https://example.com/article",
            crawl_timestamp=datetime(2025, 12, 21, 10, 30, 0),
            original_headline="Some Headline",
            source_name=None,
        )

        assert "source_name" not in attribution

    def test_attribution_with_empty_url(self) -> None:
        """Attribution with empty url should store empty string."""
        attribution = build_source_attribution(
            source="finnhub",
            article_id="no-url-article",
            url="",
            crawl_timestamp=datetime(2025, 12, 21, 10, 30, 0),
            original_headline="Article without URL",
        )

        assert attribution["url"] == ""

    def test_attribution_with_none_url(self) -> None:
        """Attribution with None url should store empty string."""
        attribution = build_source_attribution(
            source="finnhub",
            article_id="no-url-article",
            url=None,  # type: ignore
            crawl_timestamp=datetime(2025, 12, 21, 10, 30, 0),
            original_headline="Article without URL",
        )

        assert attribution["url"] == ""

    def test_crawl_timestamp_formatted_as_iso8601(self) -> None:
        """crawl_timestamp should be formatted as ISO8601."""
        ts = datetime(2025, 12, 21, 10, 30, 45)
        attribution = build_source_attribution(
            source="tiingo",
            article_id="12345",
            url="https://example.com",
            crawl_timestamp=ts,
            original_headline="Headline",
        )

        assert attribution["crawl_timestamp"] == "2025-12-21T10:30:45"

    def test_crawl_timestamp_string_passthrough(self) -> None:
        """String crawl_timestamp should pass through unchanged."""
        ts_str = "2025-12-21T10:30:45+00:00"
        attribution = build_source_attribution(
            source="tiingo",
            article_id="12345",
            url="https://example.com",
            crawl_timestamp=ts_str,  # type: ignore
            original_headline="Headline",
        )

        assert attribution["crawl_timestamp"] == ts_str

    def test_article_id_converted_to_string(self) -> None:
        """article_id should be converted to string."""
        attribution = build_source_attribution(
            source="tiingo",
            article_id=91144751,  # type: ignore - integer input
            url="https://example.com",
            crawl_timestamp=datetime.now(),
            original_headline="Headline",
        )

        assert attribution["article_id"] == "91144751"
        assert isinstance(attribution["article_id"], str)


class TestDualSourceAttribution:
    """Tests for articles with attributions from multiple sources."""

    def test_dual_source_article_has_both_attributions(self) -> None:
        """Article from both sources should have two attribution entries."""
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="91144751",
            url="https://tiingo.com/article/91144751",
            crawl_timestamp=datetime(2025, 12, 21, 10, 30, 0),
            original_headline="Apple Reports Q4 Earnings Beat - Reuters",
            source_name="reuters",
        )

        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="abc-def-123",
            url="https://finnhub.io/news/abc-def-123",
            crawl_timestamp=datetime(2025, 12, 21, 10, 32, 0),
            original_headline="Apple Reports Q4 Earnings Beat",
            source_name="reuters",
        )

        # Build combined attribution map as it would be stored
        source_attribution = {
            "tiingo": tiingo_attr,
            "finnhub": finnhub_attr,
        }

        # Verify both sources present
        assert "tiingo" in source_attribution
        assert "finnhub" in source_attribution
        assert len(source_attribution) == 2

        # Verify each has distinct article_id and url
        assert source_attribution["tiingo"]["article_id"] == "91144751"
        assert source_attribution["finnhub"]["article_id"] == "abc-def-123"
        assert (
            source_attribution["tiingo"]["url"] != source_attribution["finnhub"]["url"]
        )

        # But same source_name (reuters provided to both)
        assert source_attribution["tiingo"]["source_name"] == "reuters"
        assert source_attribution["finnhub"]["source_name"] == "reuters"

    def test_attribution_preserves_original_headlines(self) -> None:
        """Each source preserves its original headline before normalization."""
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="t1",
            url="https://tiingo.com/t1",
            crawl_timestamp=datetime(2025, 12, 21, 10, 0, 0),
            original_headline="Apple Reports Q4 Earnings Beat - Reuters",
        )

        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="f1",
            url="https://finnhub.io/f1",
            crawl_timestamp=datetime(2025, 12, 21, 10, 1, 0),
            original_headline="Apple reports Q4 earnings beat",  # Different formatting
        )

        # Both preserve their original (non-normalized) headlines
        assert (
            tiingo_attr["original_headline"]
            == "Apple Reports Q4 Earnings Beat - Reuters"
        )
        assert finnhub_attr["original_headline"] == "Apple reports Q4 earnings beat"

    def test_attribution_timestamps_can_differ(self) -> None:
        """Different sources may have different crawl timestamps."""
        tiingo_attr = build_source_attribution(
            source="tiingo",
            article_id="t1",
            url="https://tiingo.com/t1",
            crawl_timestamp=datetime(2025, 12, 21, 10, 0, 0),
            original_headline="Headline",
        )

        finnhub_attr = build_source_attribution(
            source="finnhub",
            article_id="f1",
            url="https://finnhub.io/f1",
            crawl_timestamp=datetime(2025, 12, 21, 10, 5, 0),  # 5 minutes later
            original_headline="Headline",
        )

        assert tiingo_attr["crawl_timestamp"] != finnhub_attr["crawl_timestamp"]


class TestAttributionEdgeCases:
    """Edge case tests for attribution handling."""

    def test_unicode_headline_preserved(self) -> None:
        """Unicode characters in headline should be preserved."""
        attribution = build_source_attribution(
            source="tiingo",
            article_id="1",
            url="https://example.com",
            crawl_timestamp=datetime.now(),
            original_headline="Apple 株式会社 reports earnings 📈",
        )

        assert attribution["original_headline"] == "Apple 株式会社 reports earnings 📈"

    def test_very_long_headline_preserved(self) -> None:
        """Very long headlines should be preserved in full."""
        long_headline = "A" * 1000
        attribution = build_source_attribution(
            source="tiingo",
            article_id="1",
            url="https://example.com",
            crawl_timestamp=datetime.now(),
            original_headline=long_headline,
        )

        assert len(attribution["original_headline"]) == 1000

    def test_headline_with_html_preserved(self) -> None:
        """HTML in headline should be preserved (not escaped or stripped)."""
        attribution = build_source_attribution(
            source="tiingo",
            article_id="1",
            url="https://example.com",
            crawl_timestamp=datetime.now(),
            original_headline="<b>Breaking:</b> Apple earnings &amp; outlook",
        )

        assert (
            attribution["original_headline"]
            == "<b>Breaking:</b> Apple earnings &amp; outlook"
        )
