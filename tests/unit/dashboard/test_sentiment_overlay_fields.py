"""
Sentiment Overlay Field Validation Tests for Dashboard JavaScript.

Feature 1069: Tests that verify the sentiment overlay code uses correct
field names to extract timestamps from API responses.

The API returns buckets with 'timestamp' field, not 'bucket_timestamp' or 'SK'.
This test ensures the JavaScript code checks 'timestamp' first.

Run: pytest tests/unit/dashboard/test_sentiment_overlay_fields.py -v
"""

import re
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parents[3]


def read_ohlc_js() -> str:
    """Read the ohlc.js file content."""
    repo_root = get_repo_root()
    ohlc_path = repo_root / "src" / "dashboard" / "ohlc.js"
    assert ohlc_path.exists(), f"ohlc.js not found at {ohlc_path}"
    return ohlc_path.read_text()


class TestSentimentOverlayFields:
    """Test that sentiment overlay uses correct API field names."""

    def test_file_exists(self) -> None:
        """Verify ohlc.js exists."""
        repo_root = get_repo_root()
        ohlc_path = repo_root / "src" / "dashboard" / "ohlc.js"
        assert ohlc_path.exists(), "ohlc.js not found"

    def test_update_sentiment_overlay_method_exists(self) -> None:
        """Verify updateSentimentOverlay method exists."""
        content = read_ohlc_js()
        assert (
            "updateSentimentOverlay()" in content
        ), "updateSentimentOverlay method not found"

    def test_uses_timestamp_field_first(self) -> None:
        """
        Verify the code checks bucket.timestamp as the primary field.

        The API returns SentimentBucketResponse with 'timestamp' field.
        The JS code must check this field first, before legacy fallbacks.
        """
        content = read_ohlc_js()

        # Find the updateSentimentOverlay function
        overlay_match = re.search(
            r"updateSentimentOverlay\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert overlay_match, "Could not find updateSentimentOverlay method body"

        method_body = overlay_match.group(1)

        # The correct pattern: bucket.timestamp should appear first
        # Pattern should be: bucket.timestamp || bucket.bucket_timestamp || bucket.SK
        correct_pattern = r"bucket\.timestamp\s*\|\|"

        assert re.search(correct_pattern, method_body), (
            "Sentiment overlay must check bucket.timestamp first.\n"
            "The API returns SentimentBucketResponse with 'timestamp' field, "
            "not 'bucket_timestamp' or 'SK'.\n"
            "Expected pattern: bucket.timestamp || bucket.bucket_timestamp || bucket.SK"
        )

    def test_has_feature_1069_comment(self) -> None:
        """Verify the Feature 1069 fix has a comment for traceability."""
        content = read_ohlc_js()

        # Look for Feature 1069 reference
        assert "Feature 1069" in content or "1069" in content, (
            "Missing Feature 1069 reference in ohlc.js. "
            "The fix should have a comment for traceability."
        )

    def test_does_not_skip_timestamp_field(self) -> None:
        """
        Verify the code does NOT only check bucket_timestamp or SK.

        Bug was: const ts = bucket.bucket_timestamp || bucket.SK;
        This skips the actual 'timestamp' field that the API returns.
        """
        content = read_ohlc_js()

        # Find the updateSentimentOverlay function
        overlay_match = re.search(
            r"updateSentimentOverlay\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert overlay_match, "Could not find updateSentimentOverlay method body"

        method_body = overlay_match.group(1)

        # Bug pattern: starting with bucket_timestamp, skipping timestamp
        bug_pattern = r"=\s*bucket\.bucket_timestamp\s*\|\|\s*bucket\.SK\s*;"

        assert not re.search(bug_pattern, method_body), (
            "Found bug pattern: bucket.bucket_timestamp || bucket.SK\n"
            "This skips the 'timestamp' field that the API actually returns.\n"
            "Fix: bucket.timestamp || bucket.bucket_timestamp || bucket.SK"
        )


class TestSentimentApiFieldNames:
    """Test that we document the expected API field names."""

    def test_load_sentiment_data_method_exists(self) -> None:
        """Verify loadSentimentData method exists."""
        content = read_ohlc_js()
        assert "loadSentimentData" in content, "loadSentimentData method not found"

    def test_uses_buckets_array(self) -> None:
        """Verify the code accesses data.buckets from API response."""
        content = read_ohlc_js()

        # The API returns { buckets: [...] }
        assert (
            "data.buckets" in content
        ), "Code should access data.buckets from API response"
