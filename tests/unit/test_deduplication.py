"""
Unit Tests for Deduplication Module
====================================

Tests all deduplication functions for deterministic hash generation.

For On-Call Engineers:
    These tests verify that:
    - Same URL always produces same source_id
    - Different URLs produce different source_ids
    - Batch deduplication correctly filters duplicates

For Developers:
    - source_id format: "article#{hash16}"
    - Hash is deterministic (same input = same output)
    - Test edge cases: missing fields, unicode, special chars
"""

import pytest

from src.lib.deduplication import (
    batch_deduplicate,
    extract_hash,
    generate_correlation_id,
    generate_source_id,
    get_source_prefix,
    is_duplicate,
)


class TestGenerateSourceId:
    """Tests for generate_source_id function."""

    def test_generate_from_url(self):
        """Test source_id generation from URL."""
        article = {
            "url": "https://example.com/article/123",
            "title": "Test Article",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id = generate_source_id(article)

        assert source_id.startswith("article#")
        assert len(source_id) == len("article#") + 16

    def test_deterministic_hashing(self):
        """Test that same URL produces same hash."""
        article = {
            "url": "https://example.com/article/123",
            "title": "Test Article",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id_1 = generate_source_id(article)
        source_id_2 = generate_source_id(article)

        assert source_id_1 == source_id_2

    def test_different_urls_different_hashes(self):
        """Test that different URLs produce different hashes."""
        article_1 = {"url": "https://example.com/article/1"}
        article_2 = {"url": "https://example.com/article/2"}

        source_id_1 = generate_source_id(article_1)
        source_id_2 = generate_source_id(article_2)

        assert source_id_1 != source_id_2

    def test_fallback_to_title_and_published_at(self):
        """Test fallback when URL is missing."""
        article = {
            "title": "Test Article Title",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id = generate_source_id(article)

        assert source_id.startswith("article#")
        assert len(source_id) == len("article#") + 16

    def test_fallback_deterministic(self):
        """Test that fallback is also deterministic."""
        article = {
            "title": "Test Article Title",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id_1 = generate_source_id(article)
        source_id_2 = generate_source_id(article)

        assert source_id_1 == source_id_2

    def test_missing_all_fields_raises(self):
        """Test that missing all required fields raises ValueError."""
        article = {"description": "Some description"}

        with pytest.raises(ValueError, match="must have 'url' or both"):
            generate_source_id(article)

    def test_missing_title_only_raises(self):
        """Test that missing title with publishedAt raises ValueError."""
        article = {"publishedAt": "2025-11-17T14:30:00Z"}

        with pytest.raises(ValueError):
            generate_source_id(article)

    def test_missing_published_at_only_raises(self):
        """Test that missing publishedAt with title raises ValueError."""
        article = {"title": "Test Title"}

        with pytest.raises(ValueError):
            generate_source_id(article)

    def test_url_with_query_params(self):
        """Test URL with query parameters."""
        article = {"url": "https://example.com/article?id=123&ref=twitter"}

        source_id = generate_source_id(article)

        assert source_id.startswith("article#")

    def test_unicode_url(self):
        """Test URL with unicode characters."""
        article = {"url": "https://example.com/article/αβγ-日本語"}

        source_id = generate_source_id(article)

        assert source_id.startswith("article#")

    def test_unicode_title(self):
        """Test title with unicode characters."""
        article = {
            "title": "Test Article with émojis 🚀 and ñ",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id = generate_source_id(article)

        assert source_id.startswith("article#")

    def test_url_preferred_over_title(self):
        """Test that URL is used when both URL and title present."""
        article_with_url = {
            "url": "https://example.com/article/123",
            "title": "Different Title",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        article_title_only = {
            "title": "Different Title",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        source_id_url = generate_source_id(article_with_url)
        source_id_title = generate_source_id(article_title_only)

        # Different because URL vs title+publishedAt
        assert source_id_url != source_id_title

    def test_empty_url_uses_fallback(self):
        """Test that empty URL string uses fallback."""
        article = {
            "url": "",
            "title": "Test Title",
            "publishedAt": "2025-11-17T14:30:00Z",
        }

        # Empty string is falsy, should use fallback
        source_id = generate_source_id(article)
        assert source_id.startswith("article#")


class TestIsDuplicate:
    """Tests for is_duplicate function."""

    def test_is_duplicate_true(self):
        """Test duplicate detection returns True."""
        existing = {"article#abc123", "article#def456"}

        assert is_duplicate("article#abc123", existing) is True

    def test_is_duplicate_false(self):
        """Test new item returns False."""
        existing = {"article#abc123", "article#def456"}

        assert is_duplicate("article#new789", existing) is False

    def test_empty_existing_set(self):
        """Test with empty existing set."""
        existing: set[str] = set()

        assert is_duplicate("article#abc123", existing) is False


class TestExtractHash:
    """Tests for extract_hash function."""

    def test_extract_hash_basic(self):
        """Test basic hash extraction."""
        source_id = "article#abc123def456"

        hash_part = extract_hash(source_id)

        assert hash_part == "abc123def456"

    def test_extract_hash_with_extra_hashes(self):
        """Test extraction when hash contains # character."""
        source_id = "article#abc#123#456"

        hash_part = extract_hash(source_id)

        # Should only split on first #
        assert hash_part == "abc#123#456"

    def test_invalid_format_no_hash(self):
        """Test ValueError for missing # separator."""
        with pytest.raises(ValueError, match="Invalid source_id format"):
            extract_hash("articleabc123")

    def test_invalid_format_empty(self):
        """Test ValueError for empty string."""
        with pytest.raises(ValueError, match="Invalid source_id format"):
            extract_hash("")

    def test_invalid_format_none(self):
        """Test ValueError for None."""
        with pytest.raises(ValueError):
            extract_hash(None)


class TestGetSourcePrefix:
    """Tests for get_source_prefix function."""

    def test_get_prefix_basic(self):
        """Test basic prefix extraction."""
        source_id = "article#abc123def456"

        prefix = get_source_prefix(source_id)

        assert prefix == "article"

    def test_get_prefix_different_source(self):
        """Test with different source prefix."""
        source_id = "twitter#xyz789"

        prefix = get_source_prefix(source_id)

        assert prefix == "twitter"

    def test_invalid_format(self):
        """Test ValueError for invalid format."""
        with pytest.raises(ValueError):
            get_source_prefix("invalid")


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id function."""

    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        source_id = "article#abc123"
        request_id = "req-456-789"

        correlation_id = generate_correlation_id(source_id, request_id)

        assert correlation_id == "article#abc123-req-456-789"

    def test_correlation_id_format(self):
        """Test correlation ID contains both parts."""
        source_id = "article#test123"
        request_id = "lambda-request-id"

        correlation_id = generate_correlation_id(source_id, request_id)

        assert source_id in correlation_id
        assert request_id in correlation_id


class TestBatchDeduplicate:
    """Tests for batch_deduplicate function."""

    def test_all_new_articles(self):
        """Test batch with all new articles."""
        articles = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
            {"url": "https://example.com/3"},
        ]

        new, duplicates, all_ids = batch_deduplicate(articles)

        assert len(new) == 3
        assert len(duplicates) == 0
        assert len(all_ids) == 3

    def test_all_duplicates(self):
        """Test batch where all are duplicates."""
        articles = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
        ]

        # Pre-populate existing IDs
        existing = {generate_source_id(a) for a in articles}

        new, duplicates, all_ids = batch_deduplicate(articles, existing)

        assert len(new) == 0
        assert len(duplicates) == 2

    def test_mixed_new_and_duplicates(self):
        """Test batch with mix of new and duplicate articles."""
        existing_article = {"url": "https://example.com/existing"}
        existing_ids = {generate_source_id(existing_article)}

        articles = [
            {"url": "https://example.com/new1"},
            {"url": "https://example.com/existing"},  # Duplicate
            {"url": "https://example.com/new2"},
        ]

        new, duplicates, all_ids = batch_deduplicate(articles, existing_ids)

        assert len(new) == 2
        assert len(duplicates) == 1

    def test_duplicates_within_batch(self):
        """Test deduplication within the same batch."""
        articles = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
            {"url": "https://example.com/1"},  # Duplicate within batch
        ]

        new, duplicates, all_ids = batch_deduplicate(articles)

        assert len(new) == 2
        assert len(duplicates) == 1

    def test_adds_source_id_to_new_articles(self):
        """Test that source_id is added to new articles."""
        articles = [
            {"url": "https://example.com/1", "title": "Test"},
        ]

        new, _, _ = batch_deduplicate(articles)

        assert "source_id" in new[0]
        assert new[0]["source_id"].startswith("article#")

    def test_skips_invalid_articles(self):
        """Test that articles without required fields are skipped."""
        articles = [
            {"url": "https://example.com/1"},
            {"description": "No URL or title"},  # Invalid
            {"url": "https://example.com/2"},
        ]

        new, duplicates, all_ids = batch_deduplicate(articles)

        # Invalid article should be skipped (not in new or duplicates)
        assert len(new) == 2
        assert len(duplicates) == 0

    def test_empty_batch(self):
        """Test with empty article list."""
        new, duplicates, all_ids = batch_deduplicate([])

        assert len(new) == 0
        assert len(duplicates) == 0
        assert len(all_ids) == 0

    def test_returns_combined_ids(self):
        """Test that all_ids includes both existing and new."""
        existing_ids = {"article#existing1"}

        articles = [
            {"url": "https://example.com/new"},
        ]

        _, _, all_ids = batch_deduplicate(articles, existing_ids)

        # Should have both existing and new
        assert "article#existing1" in all_ids
        assert len(all_ids) == 2


class TestHashCollisionResistance:
    """Tests to verify hash collision resistance."""

    def test_similar_urls_different_hashes(self):
        """Test that similar URLs produce different hashes."""
        articles = [
            {"url": "https://example.com/article/1"},
            {"url": "https://example.com/article/2"},
            {"url": "https://example.com/article/10"},
            {"url": "https://example.com/article/11"},
        ]

        source_ids = [generate_source_id(a) for a in articles]

        # All should be unique
        assert len(set(source_ids)) == len(articles)

    def test_many_unique_hashes(self):
        """Test that many articles produce unique hashes."""
        articles = [{"url": f"https://example.com/article/{i}"} for i in range(1000)]

        source_ids = [generate_source_id(a) for a in articles]

        # All should be unique
        assert len(set(source_ids)) == len(articles)
