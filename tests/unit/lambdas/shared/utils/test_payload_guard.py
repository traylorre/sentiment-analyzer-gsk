"""Tests for payload_guard module."""

from src.lambdas.shared.utils.payload_guard import (
    MAX_PAYLOAD_BYTES,
    check_response_size,
)


class TestCheckResponseSize:
    """Tests for check_response_size."""

    def test_small_payload_returns_none(self):
        """Payload within limits returns None."""
        assert check_response_size("hello") is None

    def test_exact_limit_returns_none(self):
        """Payload at exact limit returns None."""
        body = "x" * MAX_PAYLOAD_BYTES
        assert check_response_size(body) is None

    def test_oversized_payload_returns_error(self):
        """Payload exceeding limit returns error message."""
        body = "x" * (MAX_PAYLOAD_BYTES + 1)
        result = check_response_size(body)
        assert result is not None
        assert "exceeds" in result
        assert "6MB" in result

    def test_unicode_counts_bytes_not_chars(self):
        """Multi-byte characters are counted by byte size."""
        # Each emoji is 4 bytes in UTF-8
        body = "\U0001f600" * (MAX_PAYLOAD_BYTES // 4 + 1)
        result = check_response_size(body)
        assert result is not None
