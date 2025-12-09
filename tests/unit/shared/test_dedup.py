"""Unit tests for deduplication key generator.

Tests the deterministic key generation for news article deduplication.
"""

from datetime import UTC, datetime

from src.lambdas.shared.utils.dedup import (
    generate_dedup_key,
    generate_dedup_key_from_article,
)


class TestGenerateDedupKey:
    """Tests for generate_dedup_key function."""

    def test_returns_32_char_hex_string(self) -> None:
        """Key should be exactly 32 hexadecimal characters."""
        key = generate_dedup_key(
            headline="Apple Q4 Earnings Beat Expectations",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 30, 0, tzinfo=UTC),
        )

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_inputs_same_key(self) -> None:
        """Identical inputs should produce identical keys (deterministic)."""
        inputs = {
            "headline": "Tesla Stock Surges on Record Deliveries",
            "source": "finnhub",
            "published_at": datetime(2025, 12, 9, 10, 0, 0, tzinfo=UTC),
        }

        key1 = generate_dedup_key(**inputs)
        key2 = generate_dedup_key(**inputs)

        assert key1 == key2

    def test_different_headlines_different_keys(self) -> None:
        """Different headlines should produce different keys."""
        base = {
            "source": "tiingo",
            "published_at": datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        }

        key1 = generate_dedup_key(headline="Apple Q4 Earnings", **base)
        key2 = generate_dedup_key(headline="Apple Q3 Earnings", **base)

        assert key1 != key2

    def test_different_sources_different_keys(self) -> None:
        """Different sources should produce different keys."""
        base = {
            "headline": "Market Update",
            "published_at": datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        }

        key1 = generate_dedup_key(source="tiingo", **base)
        key2 = generate_dedup_key(source="finnhub", **base)

        assert key1 != key2

    def test_different_dates_different_keys(self) -> None:
        """Different publication dates should produce different keys."""
        base = {
            "headline": "Daily Market Summary",
            "source": "tiingo",
        }

        key1 = generate_dedup_key(
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC), **base
        )
        key2 = generate_dedup_key(
            published_at=datetime(2025, 12, 10, 14, 0, 0, tzinfo=UTC), **base
        )

        assert key1 != key2

    def test_same_date_different_times_same_key(self) -> None:
        """Same date with different times should produce same key (date-level dedup)."""
        base = {
            "headline": "Breaking News",
            "source": "finnhub",
        }

        # Morning and afternoon of same day
        key1 = generate_dedup_key(
            published_at=datetime(2025, 12, 9, 9, 30, 0, tzinfo=UTC), **base
        )
        key2 = generate_dedup_key(
            published_at=datetime(2025, 12, 9, 16, 45, 0, tzinfo=UTC), **base
        )

        assert key1 == key2

    def test_timezone_aware_and_naive_same_date(self) -> None:
        """Timezone-aware and naive datetimes with same date should match."""
        base = {
            "headline": "Market Close Summary",
            "source": "tiingo",
        }

        key_aware = generate_dedup_key(
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC), **base
        )
        key_naive = generate_dedup_key(
            published_at=datetime(2025, 12, 9, 10, 0, 0),
            **base,  # naive
        )

        # Same date (2025-12-09) should produce same key
        assert key_aware == key_naive

    def test_empty_headline_still_works(self) -> None:
        """Empty headline should still generate a valid key."""
        key = generate_dedup_key(
            headline="",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_unicode_headline(self) -> None:
        """Unicode characters in headline should be handled correctly."""
        key = generate_dedup_key(
            headline="日本経済新聞: 株式市場レポート",
            source="tiingo",
            published_at=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


class TestGenerateDedupKeyFromArticle:
    """Tests for generate_dedup_key_from_article function."""

    def test_returns_32_char_hex_string(self) -> None:
        """Key should be exactly 32 hexadecimal characters."""
        key = generate_dedup_key_from_article(
            article_id="tiingo-123456",
            source="tiingo",
        )

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_inputs_same_key(self) -> None:
        """Identical inputs should produce identical keys."""
        key1 = generate_dedup_key_from_article(article_id="xyz789", source="finnhub")
        key2 = generate_dedup_key_from_article(article_id="xyz789", source="finnhub")

        assert key1 == key2

    def test_different_article_ids_different_keys(self) -> None:
        """Different article IDs should produce different keys."""
        key1 = generate_dedup_key_from_article(article_id="abc123", source="tiingo")
        key2 = generate_dedup_key_from_article(article_id="def456", source="tiingo")

        assert key1 != key2

    def test_different_sources_different_keys(self) -> None:
        """Same article ID from different sources should have different keys."""
        key1 = generate_dedup_key_from_article(article_id="123", source="tiingo")
        key2 = generate_dedup_key_from_article(article_id="123", source="finnhub")

        assert key1 != key2
