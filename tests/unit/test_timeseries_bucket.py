"""
TDD-BUCKET-001: Time bucket alignment tests.

Canonical Reference: [CS-009] Prometheus time-series alignment, [CS-010] Gorilla paper

Tests MUST be written FIRST and FAIL before implementation.
"""

from datetime import UTC, datetime

import pytest

from src.lib.timeseries.bucket import floor_to_bucket
from src.lib.timeseries.models import Resolution


def parse_iso(iso_str: str) -> datetime:
    """Parse ISO8601 timestamp to datetime."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


class TestBucketAlignment:
    """
    Canonical: [CS-009] "Align time buckets to wall-clock boundaries"
    """

    @pytest.mark.parametrize(
        "timestamp,resolution,expected",
        [
            # 1-minute alignment
            ("2025-12-21T10:35:47Z", "1m", "2025-12-21T10:35:00Z"),
            ("2025-12-21T10:35:00Z", "1m", "2025-12-21T10:35:00Z"),
            ("2025-12-21T10:35:59Z", "1m", "2025-12-21T10:35:00Z"),
            # 5-minute alignment
            ("2025-12-21T10:37:00Z", "5m", "2025-12-21T10:35:00Z"),
            ("2025-12-21T10:34:59Z", "5m", "2025-12-21T10:30:00Z"),
            ("2025-12-21T10:40:00Z", "5m", "2025-12-21T10:40:00Z"),
            # 15-minute alignment
            ("2025-12-21T10:45:30Z", "15m", "2025-12-21T10:45:00Z"),
            ("2025-12-21T10:39:59Z", "15m", "2025-12-21T10:30:00Z"),
            # 30-minute alignment
            ("2025-12-21T10:45:00Z", "30m", "2025-12-21T10:30:00Z"),
            ("2025-12-21T10:29:59Z", "30m", "2025-12-21T10:00:00Z"),
            # 1-hour alignment
            ("2025-12-21T10:45:00Z", "1h", "2025-12-21T10:00:00Z"),
            ("2025-12-21T10:00:00Z", "1h", "2025-12-21T10:00:00Z"),
            # 24-hour alignment
            ("2025-12-21T14:30:00Z", "24h", "2025-12-21T00:00:00Z"),
            ("2025-12-21T23:59:59Z", "24h", "2025-12-21T00:00:00Z"),
        ],
    )
    def test_floor_to_resolution_boundary(
        self, timestamp: str, resolution: str, expected: str
    ) -> None:
        """Bucket timestamps MUST align to wall-clock boundaries per [CS-009]."""
        result = floor_to_bucket(parse_iso(timestamp), Resolution(resolution))
        assert result == parse_iso(expected)

    def test_invalid_resolution_raises(self) -> None:
        """Unknown resolution MUST raise ValueError with valid options listed."""
        with pytest.raises(
            ValueError, match="Resolution must be one of|is not a valid"
        ):
            floor_to_bucket(datetime.now(UTC), Resolution("3m"))

    def test_bucket_duration_seconds(self) -> None:
        """Each resolution MUST have correct duration in seconds."""
        expected = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "24h": 86400,
        }
        for res, seconds in expected.items():
            assert Resolution(res).duration_seconds == seconds

    def test_floor_preserves_timezone(self) -> None:
        """Floored timestamps MUST preserve UTC timezone."""
        ts = parse_iso("2025-12-21T10:35:47Z")
        result = floor_to_bucket(ts, Resolution("5m"))
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_all_resolutions_supported(self) -> None:
        """All 6 resolution levels MUST be supported."""
        resolutions = ["1m", "5m", "15m", "30m", "1h", "24h"]
        ts = datetime.now(UTC)
        for res in resolutions:
            result = floor_to_bucket(ts, Resolution(res))
            assert isinstance(result, datetime)
