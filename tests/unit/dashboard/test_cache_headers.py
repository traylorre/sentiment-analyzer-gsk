"""Unit tests for Feature 1157: Auth Cache-Control Headers.

Tests that the _get_no_cache_headers helper returns correct cache prevention
headers for all auth endpoint responses per RFC 7234.

Requirements tested:
- FR-001: Cache-Control: no-store, no-cache, must-revalidate
- FR-002: Pragma: no-cache (HTTP/1.0 compatibility)
- FR-003: Expires: 0 (Legacy proxy compatibility)
"""

from src.lambdas.dashboard.router_v2 import _get_no_cache_headers


class TestGetNoCacheHeaders:
    """Test suite for _get_no_cache_headers helper function."""

    def test_returns_dict(self) -> None:
        """Result should be a dict."""
        headers = _get_no_cache_headers()
        assert isinstance(headers, dict)

    def test_sets_cache_control_header(self) -> None:
        """Test that Cache-Control header is set correctly (FR-001)."""
        headers = _get_no_cache_headers()
        assert headers["Cache-Control"] == "no-store, no-cache, must-revalidate"

    def test_sets_pragma_header(self) -> None:
        """Test that Pragma header is set for HTTP/1.0 compatibility (FR-002)."""
        headers = _get_no_cache_headers()
        assert headers["Pragma"] == "no-cache"

    def test_sets_expires_header(self) -> None:
        """Test that Expires header is set for legacy proxy compatibility (FR-003)."""
        headers = _get_no_cache_headers()
        assert headers["Expires"] == "0"

    def test_sets_all_headers_together(self) -> None:
        """Test that all three headers are present in a single call."""
        headers = _get_no_cache_headers()
        assert headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
        assert headers["Pragma"] == "no-cache"
        assert headers["Expires"] == "0"

    def test_returns_exactly_three_headers(self) -> None:
        """Test that only the expected headers are returned (no extras)."""
        headers = _get_no_cache_headers()
        assert len(headers) == 3
