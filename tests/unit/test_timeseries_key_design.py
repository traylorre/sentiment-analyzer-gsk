"""
TDD-KEY-001: Composite key generation tests.

Canonical Reference: [CS-002] AWS composite key pattern, [CS-004] DynamoDB Book

Tests MUST be written FIRST and FAIL before implementation.
"""

from datetime import datetime

import pytest

from src.lib.timeseries.models import Resolution, TimeseriesKey


def parse_iso(iso_str: str) -> datetime:
    """Parse ISO8601 timestamp to datetime."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


class TestTimeseriesKeyDesign:
    """
    Canonical: [CS-002] "Use composite keys with delimiter for hierarchical access"
    [CS-004] "ticker#resolution is standard for multi-dimensional time-series"
    """

    @pytest.mark.parametrize(
        "ticker,resolution,expected_pk",
        [
            ("AAPL", "1m", "AAPL#1m"),
            ("TSLA", "5m", "TSLA#5m"),
            ("MSFT", "1h", "MSFT#1h"),
            ("GOOGL", "24h", "GOOGL#24h"),
        ],
    )
    def test_partition_key_format(
        self, ticker: str, resolution: str, expected_pk: str
    ) -> None:
        """PK MUST be {ticker}#{resolution} per [CS-002]."""
        key = TimeseriesKey(ticker=ticker, resolution=Resolution(resolution))
        assert key.pk == expected_pk

    def test_sort_key_is_iso8601_timestamp(self) -> None:
        """SK MUST be ISO8601 bucket timestamp."""
        key = TimeseriesKey(
            ticker="AAPL",
            resolution=Resolution("5m"),
            bucket_timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        assert key.sk == "2025-12-21T10:35:00+00:00"

    def test_key_from_pk_sk_strings(self) -> None:
        """MUST be able to reconstruct key from DynamoDB strings."""
        key = TimeseriesKey.from_dynamodb(pk="AAPL#5m", sk="2025-12-21T10:35:00Z")
        assert key.ticker == "AAPL"
        assert key.resolution == Resolution("5m")
        assert key.bucket_timestamp == parse_iso("2025-12-21T10:35:00Z")

    def test_invalid_pk_format_raises(self) -> None:
        """Malformed PK MUST raise with descriptive error."""
        with pytest.raises(ValueError, match="PK must match pattern"):
            TimeseriesKey.from_dynamodb(pk="AAPL", sk="2025-12-21T10:35:00Z")

    def test_delimiter_in_ticker_rejected(self) -> None:
        """Ticker with # delimiter MUST be rejected."""
        with pytest.raises(ValueError, match="Ticker cannot contain"):
            TimeseriesKey(ticker="AA#PL", resolution=Resolution("5m"))

    def test_empty_ticker_rejected(self) -> None:
        """Empty ticker MUST be rejected."""
        with pytest.raises(ValueError, match="Ticker cannot be empty"):
            TimeseriesKey(ticker="", resolution=Resolution("5m"))

    def test_all_resolutions_supported_in_pk(self) -> None:
        """All 8 resolution levels MUST be supported in PK."""
        resolutions = ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]
        for res in resolutions:
            key = TimeseriesKey(ticker="AAPL", resolution=Resolution(res))
            assert f"AAPL#{res}" == key.pk

    def test_lowercase_ticker_allowed(self) -> None:
        """Lowercase tickers MUST be allowed (no forced uppercase)."""
        key = TimeseriesKey(ticker="aapl", resolution=Resolution("5m"))
        assert key.pk == "aapl#5m"

    def test_key_to_dynamodb_format(self) -> None:
        """Key MUST provide DynamoDB attribute dict."""
        key = TimeseriesKey(
            ticker="AAPL",
            resolution=Resolution("5m"),
            bucket_timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        ddb_key = key.to_dynamodb_key()
        assert ddb_key["PK"]["S"] == "AAPL#5m"
        assert "2025-12-21T10:35:00" in ddb_key["SK"]["S"]
