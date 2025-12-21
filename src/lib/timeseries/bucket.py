"""
Time bucket alignment and progress utilities.

Canonical References:
- [CS-009] Prometheus Docs: Time-Series Alignment
- [CS-010] VLDB 2015 (Facebook): Gorilla paper
- [CS-011] Netflix Tech Blog: Partial aggregates with progress indicators
"""

from datetime import UTC, datetime

from src.lib.timeseries.models import Resolution


def floor_to_bucket(timestamp: datetime, resolution: Resolution) -> datetime:
    """
    Floor a timestamp to the nearest bucket boundary for a given resolution.

    Canonical: [CS-009] "Align time buckets to wall-clock boundaries"

    Args:
        timestamp: The timestamp to floor
        resolution: The resolution level for alignment

    Returns:
        datetime: The floored timestamp aligned to the resolution boundary

    Raises:
        ValueError: If resolution is not supported
    """
    duration_seconds = resolution.duration_seconds

    # Get Unix timestamp
    ts = timestamp.timestamp()

    # Floor to resolution boundary
    floored_ts = (int(ts) // duration_seconds) * duration_seconds

    # Return as UTC datetime
    return datetime.fromtimestamp(floored_ts, tz=UTC)


def calculate_bucket_progress(bucket_start: datetime, resolution: Resolution) -> float:
    """
    Calculate the progress percentage through a bucket period.

    Canonical: [CS-011] "Partial aggregates with progress indicators"

    Args:
        bucket_start: The start time of the bucket
        resolution: The resolution of the bucket

    Returns:
        float: Progress percentage (0.0 to 100.0)

    Raises:
        ValueError: If current time is before bucket start
    """
    now = datetime.now(UTC)
    duration_seconds = resolution.duration_seconds

    # Calculate elapsed seconds
    elapsed = (now - bucket_start).total_seconds()

    if elapsed < 0:
        raise ValueError(f"Current time {now} is before bucket start {bucket_start}")

    # Calculate progress percentage
    progress = (elapsed / duration_seconds) * 100.0

    # Cap at 100%
    return min(progress, 100.0)
