"""Unit tests for dedup key generation.

Tests generate_dedup_key() for cross-source article matching.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

from datetime import UTC, datetime

from src.lambdas.ingestion.dedup import generate_dedup_key


class TestDedupKeyGeneration:
    """Tests for generate_dedup_key function."""

    def test_same_headline_same_date_produces_same_key(self):
        """Identical headline and date produce identical key."""
        headline = "Apple Reports Q4 Earnings"
        date = "2025-12-21"

        key1 = generate_dedup_key(headline, date)
        key2 = generate_dedup_key(headline, date)

        assert key1 == key2

    def test_key_is_32_hex_characters(self):
        """Key is exactly 32 hexadecimal characters."""
        key = generate_dedup_key("Test Headline", "2025-12-21")

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_different_dates_produce_different_keys(self):
        """Same headline on different days produces different keys."""
        headline = "Apple Reports Q4 Earnings"

        key1 = generate_dedup_key(headline, "2025-12-21")
        key2 = generate_dedup_key(headline, "2025-12-22")

        assert key1 != key2

    def test_normalized_headlines_match(self):
        """Headlines that normalize to same string produce same key."""
        date = "2025-12-21"

        # Different case
        key1 = generate_dedup_key("Apple Reports Earnings", date)
        key2 = generate_dedup_key("APPLE REPORTS EARNINGS", date)
        assert key1 == key2

        # Different punctuation
        key3 = generate_dedup_key("Apple: Reports Earnings!", date)
        key4 = generate_dedup_key("Apple Reports Earnings", date)
        assert key3 == key4

        # Different spacing
        key5 = generate_dedup_key("Apple  Reports   Earnings", date)
        key6 = generate_dedup_key("Apple Reports Earnings", date)
        assert key5 == key6

    def test_datetime_object_handled(self):
        """datetime object is correctly converted to date string."""
        headline = "Test Headline"
        dt = datetime(2025, 12, 21, 14, 30, 0, tzinfo=UTC)

        key_from_datetime = generate_dedup_key(headline, dt)
        key_from_string = generate_dedup_key(headline, "2025-12-21")

        assert key_from_datetime == key_from_string

    def test_iso8601_with_time_uses_date_only(self):
        """ISO8601 string with time portion uses only date."""
        headline = "Test Headline"

        key1 = generate_dedup_key(headline, "2025-12-21T10:30:00Z")
        key2 = generate_dedup_key(headline, "2025-12-21T23:59:59Z")
        key3 = generate_dedup_key(headline, "2025-12-21")

        assert key1 == key2 == key3

    def test_cross_source_matching(self):
        """Articles from different sources with same content produce same key."""
        date = "2025-12-21"

        # Tiingo format
        tiingo_headline = "Apple Reports Q4 Earnings Beat"
        # Finnhub format (same article, different case)
        finnhub_headline = "Apple reports Q4 earnings beat"

        key_tiingo = generate_dedup_key(tiingo_headline, date)
        key_finnhub = generate_dedup_key(finnhub_headline, date)

        assert key_tiingo == key_finnhub

    def test_cross_source_with_punctuation_differences(self):
        """Articles with punctuation differences still match."""
        date = "2025-12-21"

        # Tiingo with punctuation
        tiingo = "What's Next? Apple's Q4 Results"
        # Finnhub without
        finnhub = "Whats Next Apples Q4 Results"

        assert generate_dedup_key(tiingo, date) == generate_dedup_key(finnhub, date)

    def test_different_articles_produce_different_keys(self):
        """Different articles produce different keys."""
        date = "2025-12-21"

        key1 = generate_dedup_key("Apple Reports Earnings", date)
        key2 = generate_dedup_key("Microsoft Reports Earnings", date)

        assert key1 != key2

    def test_empty_headline_produces_key(self):
        """Empty headline still produces a valid key."""
        key = generate_dedup_key("", "2025-12-21")

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_unicode_headlines_work(self):
        """Unicode headlines produce valid keys."""
        key = generate_dedup_key("Tokyo 東京 Stock Market Update", "2025-12-21")

        assert len(key) == 32

    def test_very_long_headline(self):
        """Very long headlines produce valid keys."""
        long_headline = "A" * 10000
        key = generate_dedup_key(long_headline, "2025-12-21")

        assert len(key) == 32

    def test_key_is_deterministic(self):
        """Same inputs always produce same output."""
        headline = "Test Headline For Determinism"
        date = "2025-12-21"

        keys = [generate_dedup_key(headline, date) for _ in range(100)]

        assert all(k == keys[0] for k in keys)

    def test_real_world_tiingo_finnhub_examples(self):
        """Real-world examples from Tiingo and Finnhub APIs."""
        date = "2025-12-21"

        # Example 1: Same Reuters article
        tiingo1 = "Tesla Q4 deliveries beat estimates, hit record"
        finnhub1 = "Tesla Q4 deliveries beat estimates, hit record"
        assert generate_dedup_key(tiingo1, date) == generate_dedup_key(finnhub1, date)

        # Example 2: Case difference
        tiingo2 = "NVIDIA Stock Hits All-Time High"
        finnhub2 = "Nvidia stock hits all-time high"
        assert generate_dedup_key(tiingo2, date) == generate_dedup_key(finnhub2, date)

        # Example 3: Punctuation difference (quotes)
        tiingo3 = '"Big Tech" Earnings Week Begins'
        finnhub3 = "Big Tech Earnings Week Begins"
        assert generate_dedup_key(tiingo3, date) == generate_dedup_key(finnhub3, date)


class TestDedupKeyWithSourceAttribution:
    """Tests for headlines with wire service attribution."""

    def test_attribution_causes_mismatch_when_present_in_one_source(self):
        """Wire service attribution can cause mismatch if present in only one source."""
        date = "2025-12-21"

        # Tiingo includes attribution
        tiingo = "Tesla Beats Estimates - Reuters"
        # Finnhub doesn't
        finnhub = "Tesla Beats Estimates"

        key_tiingo = generate_dedup_key(tiingo, date)
        key_finnhub = generate_dedup_key(finnhub, date)

        # These will NOT match because "reuters" is in one but not other
        # This is expected behavior - the dedup key is content-based
        assert key_tiingo != key_finnhub

    def test_same_attribution_matches(self):
        """Same wire service attribution in both produces match."""
        date = "2025-12-21"

        tiingo = "Tesla Beats Estimates - Reuters"
        finnhub = "Tesla beats estimates - Reuters"

        assert generate_dedup_key(tiingo, date) == generate_dedup_key(finnhub, date)

    def test_no_attribution_both_match(self):
        """No attribution in either source produces match."""
        date = "2025-12-21"

        tiingo = "Tesla Beats Estimates"
        finnhub = "Tesla beats estimates"

        assert generate_dedup_key(tiingo, date) == generate_dedup_key(finnhub, date)
