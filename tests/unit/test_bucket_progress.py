"""
TDD-BUCKET-002: Partial bucket progress calculation tests.

Canonical Reference: [CS-011] "Partial aggregates with progress indicators"

Tests MUST be written FIRST and FAIL before implementation.
"""

from datetime import datetime

import pytest
from freezegun import freeze_time

from src.lib.timeseries.bucket import calculate_bucket_progress
from src.lib.timeseries.models import Resolution


def parse_iso(iso_str: str) -> datetime:
    """Parse ISO8601 timestamp to datetime."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


class TestPartialBucketProgress:
    """
    Canonical: [CS-011] "Partial aggregates with progress indicators"
    """

    @freeze_time("2025-12-21T10:37:30Z")
    def test_progress_midway_through_5min_bucket(self) -> None:
        """
        Given: Current time is 2:30 into a 5-minute bucket (10:35:00 - 10:40:00)
        Then: Progress should be 50%
        """
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2025-12-21T10:35:00Z")
    def test_progress_at_bucket_start(self) -> None:
        """Progress at exact bucket start should be 0%."""
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert progress == 0.0

    @freeze_time("2025-12-21T10:39:59Z")
    def test_progress_near_bucket_end(self) -> None:
        """Progress near bucket end should approach 100% but never exceed."""
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert 99.0 <= progress < 100.0

    def test_progress_for_completed_bucket_returns_100(self) -> None:
        """Completed buckets should return exactly 100%."""
        with freeze_time("2025-12-21T10:45:00Z"):
            bucket_start = parse_iso("2025-12-21T10:35:00Z")
            progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
            assert progress == 100.0

    @freeze_time("2025-12-21T10:30:30Z")
    def test_progress_1_minute_resolution(self) -> None:
        """Progress for 1-minute resolution at 30 seconds should be 50%."""
        bucket_start = parse_iso("2025-12-21T10:30:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("1m"))
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2025-12-21T11:30:00Z")
    def test_progress_1_hour_resolution_midway(self) -> None:
        """Progress for 1-hour resolution at 30 minutes should be 50%."""
        bucket_start = parse_iso("2025-12-21T11:00:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("1h"))
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2025-12-21T12:00:00Z")
    def test_progress_24_hour_resolution_midday(self) -> None:
        """Progress for 24-hour resolution at noon should be 50%."""
        bucket_start = parse_iso("2025-12-21T00:00:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("24h"))
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2025-12-21T10:34:00Z")
    def test_progress_before_bucket_start_raises(self) -> None:
        """Requesting progress for a bucket that hasn't started MUST raise ValueError."""
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        with pytest.raises(ValueError, match="Current time.*before bucket start"):
            calculate_bucket_progress(bucket_start, Resolution("5m"))
