"""Unit tests for headline normalization.

Tests normalize_headline() edge cases including punctuation,
unicode, and trailing source attribution.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

from src.lambdas.ingestion.dedup import normalize_headline


class TestNormalizeHeadline:
    """Tests for normalize_headline function."""

    def test_basic_normalization(self):
        """Basic headline is lowercased and trimmed."""
        assert normalize_headline("Apple Reports Earnings") == "apple reports earnings"

    def test_punctuation_removed(self):
        """Punctuation is removed."""
        assert normalize_headline("Apple: Q4 Results!") == "apple q4 results"
        assert normalize_headline("What's next?") == "whats next"
        assert normalize_headline("A/B Testing & More") == "ab testing more"

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces become single space."""
        assert (
            normalize_headline("Apple    Reports   Earnings")
            == "apple reports earnings"
        )
        assert normalize_headline("  Leading and trailing  ") == "leading and trailing"

    def test_trailing_source_attribution_normalized(self):
        """Trailing source attribution (- Reuters) is normalized."""
        # Source attribution is kept but normalized (just punctuation removed)
        tiingo = "Apple Reports Q4 Earnings Beat - Reuters"
        finnhub = "Apple reports Q4 earnings beat"

        tiingo_normalized = normalize_headline(tiingo)
        finnhub_normalized = normalize_headline(finnhub)

        # Both should normalize to similar forms
        # Note: "Reuters" is kept but punctuation removed
        assert tiingo_normalized == "apple reports q4 earnings beat reuters"
        assert finnhub_normalized == "apple reports q4 earnings beat"

    def test_unicode_preserved(self):
        """Unicode letters are preserved."""
        assert normalize_headline("Café Results") == "café results"
        assert normalize_headline("Ñoño Company") == "ñoño company"
        assert normalize_headline("Tokyo 東京 News") == "tokyo 東京 news"

    def test_numbers_preserved(self):
        """Numbers are preserved."""
        assert normalize_headline("Q4 2025 Earnings") == "q4 2025 earnings"
        assert normalize_headline("S&P 500 Up 2.5%") == "sp 500 up 25"

    def test_empty_string(self):
        """Empty string returns empty."""
        assert normalize_headline("") == ""

    def test_only_punctuation(self):
        """Only punctuation returns empty."""
        assert normalize_headline("!@#$%^&*()") == ""

    def test_only_whitespace(self):
        """Only whitespace returns empty."""
        assert normalize_headline("   \t\n   ") == ""

    def test_mixed_case(self):
        """Mixed case is normalized to lowercase."""
        assert normalize_headline("APPLE Reports EARNINGS") == "apple reports earnings"
        assert normalize_headline("iPhone 15 Pro Max") == "iphone 15 pro max"

    def test_special_financial_punctuation(self):
        """Financial-specific punctuation is removed."""
        assert normalize_headline("$AAPL Up 5%") == "aapl up 5"
        assert normalize_headline("EUR/USD at 1.08") == "eurusd at 108"
        assert normalize_headline("P&G Reports") == "pg reports"

    def test_quotes_removed(self):
        """Quotes are removed."""
        assert normalize_headline('"Breaking News"') == "breaking news"
        assert normalize_headline("Apple's 'Best' Quarter") == "apples best quarter"

    def test_dashes_and_hyphens(self):
        """Dashes and hyphens are removed."""
        assert (
            normalize_headline("Q4 2025 - Earnings Report") == "q4 2025 earnings report"
        )
        assert normalize_headline("Year-over-year growth") == "yearoveryear growth"

    def test_newlines_and_tabs_normalized(self):
        """Newlines and tabs become spaces, then collapse."""
        assert normalize_headline("Line1\nLine2") == "line1 line2"
        assert normalize_headline("Tab\tSeparated") == "tab separated"

    def test_common_wire_service_suffixes(self):
        """Common wire service suffixes are normalized (not removed)."""
        # These are kept in normalized form - dedup works because same headline
        # from different sources will normalize the same when suffix is absent
        assert "reuters" in normalize_headline("News - Reuters")
        assert "ap" in normalize_headline("News (AP)")
        assert "afp" in normalize_headline("News | AFP")

    def test_cross_source_matching_examples(self):
        """Real-world examples from Tiingo vs Finnhub."""
        # Example 1: Same article, different formatting
        tiingo1 = "Apple Reports Record Q4 Earnings"
        finnhub1 = "Apple reports record Q4 earnings"
        assert normalize_headline(tiingo1) == normalize_headline(finnhub1)

        # Example 2: Wire service attribution
        # "Tesla Deliveries Beat Estimates - Reuters" from Tiingo
        # "Tesla deliveries beat estimates" from Finnhub
        # These won't match exactly due to "reuters" suffix
        # That's expected - dedup key generation handles this differently

        # Example 3: Punctuation differences
        tiingo3 = "Microsoft's AI Push: What's Next?"
        finnhub3 = "Microsofts AI Push Whats Next"
        assert normalize_headline(tiingo3) == normalize_headline(finnhub3)
