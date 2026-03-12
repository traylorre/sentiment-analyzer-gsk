"""Tests for url_decode module."""

from src.lambdas.shared.utils.url_decode import decode_path_param


class TestDecodePathParam:
    """Tests for decode_path_param."""

    def test_encoded_dot(self):
        """URL-encoded dot is decoded."""
        assert decode_path_param("BRK%2EB") == "BRK.B"

    def test_plain_string(self):
        """Plain string passes through unchanged."""
        assert decode_path_param("AAPL") == "AAPL"

    def test_encoded_space(self):
        """URL-encoded space is decoded."""
        assert decode_path_param("hello%20world") == "hello world"
