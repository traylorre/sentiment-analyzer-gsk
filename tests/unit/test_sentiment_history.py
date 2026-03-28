"""T012: Unit tests for sentiment history query and mapping logic.

Tests the mapping from timeseries buckets to SentimentPoint objects
as implemented in ohlc.py's sentiment history endpoint (lines 1064-1100).

Since the mapping logic is embedded inside the endpoint handler, these
tests exercise the same transformation rules in isolation by replicating
the bucket-to-SentimentPoint mapping and verifying its behavior.
"""

from dataclasses import dataclass, field
from datetime import date

import pytest

# ---------------------------------------------------------------------------
# Local replica of the mapping logic under test
# ---------------------------------------------------------------------------
# Extracted from ohlc.py lines 1064-1100 to allow unit testing without
# invoking the full HTTP handler. Any change to ohlc.py mapping logic
# should be reflected here.


@dataclass
class _Bucket:
    """Minimal stand-in for SentimentBucketResponse."""

    avg: float
    sources: list[str] = field(default_factory=list)
    timestamp: str = "2024-11-15T00:00:00Z"
    ticker: str = "AAPL"
    resolution: str = "24h"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    count: int = 1
    label_counts: dict = field(default_factory=dict)
    is_partial: bool = False


@dataclass
class _TimeseriesResponse:
    """Minimal stand-in for TimeseriesResponse."""

    ticker: str
    resolution: str
    buckets: list[_Bucket]
    partial_bucket: _Bucket | None = None
    cache_hit: bool = False
    query_time_ms: float = 0.0
    next_cursor: str | None = None
    has_more: bool = False


def _map_buckets_to_points(
    buckets: list[_Bucket],
    source_filter: str,
) -> list[dict]:
    """Replicate the ohlc.py bucket-to-SentimentPoint mapping.

    Returns dicts instead of SentimentPoint models so we avoid importing
    pydantic models and keep this test lightweight.
    """
    history = []
    for bucket in buckets:
        score = round(bucket.avg, 4)

        # Source extraction (ohlc.py line 1070-1072)
        bucket_source = "unknown"
        if bucket.sources:
            bucket_source = bucket.sources[0].split(":")[0]

        # Source filter (ohlc.py line 1075-1076)
        if source_filter != "aggregated" and bucket_source != source_filter:
            continue

        # Label derivation (ohlc.py line 1078-1084)
        if score >= 0.33:
            label = "positive"
        elif score <= -0.33:
            label = "negative"
        else:
            label = "neutral"

        # Date parsing (ohlc.py line 1087-1090)
        try:
            point_date = date.fromisoformat(bucket.timestamp.split("T")[0])
        except (ValueError, AttributeError):
            continue

        history.append(
            {
                "date": point_date,
                "score": score,
                "source": bucket_source,
                "confidence": 0.8,
                "label": label,
            }
        )
    return history


# ---------------------------------------------------------------------------
# Bucket-to-SentimentPoint mapping tests
# ---------------------------------------------------------------------------


class TestBucketMapping:
    """Timeseries buckets map correctly to SentimentPoint-like dicts."""

    def test_single_bucket_maps_to_point(self):
        """A single bucket with valid data produces one point."""
        buckets = [
            _Bucket(
                avg=0.65,
                sources=["tiingo:91120376"],
                timestamp="2024-11-15T00:00:00Z",
            )
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")

        assert len(points) == 1
        assert points[0]["date"] == date(2024, 11, 15)
        assert points[0]["score"] == 0.65
        assert points[0]["source"] == "tiingo"
        assert points[0]["confidence"] == 0.8

    def test_multiple_buckets_map_to_multiple_points(self):
        """Multiple buckets each produce a point."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="2024-11-01T00:00:00Z"),
            _Bucket(avg=-0.2, sources=["tiingo:2"], timestamp="2024-11-02T00:00:00Z"),
            _Bucket(avg=0.1, sources=["tiingo:3"], timestamp="2024-11-03T00:00:00Z"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert len(points) == 3

    def test_score_rounding(self):
        """Scores are rounded to 4 decimal places."""
        buckets = [
            _Bucket(
                avg=0.123456789,
                sources=["tiingo:1"],
                timestamp="2024-11-15T00:00:00Z",
            )
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["score"] == 0.1235


# ---------------------------------------------------------------------------
# Source prefix extraction
# ---------------------------------------------------------------------------


class TestSourceExtraction:
    """Source provider is extracted from 'provider:id' format."""

    def test_tiingo_source_extraction(self):
        """'tiingo:91120376' extracts to 'tiingo'."""
        buckets = [
            _Bucket(
                avg=0.5, sources=["tiingo:91120376"], timestamp="2024-11-15T00:00:00Z"
            )
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["source"] == "tiingo"

    def test_finnhub_source_extraction(self):
        """'finnhub:abc123' extracts to 'finnhub'."""
        buckets = [
            _Bucket(
                avg=0.5, sources=["finnhub:abc123"], timestamp="2024-11-15T00:00:00Z"
            )
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["source"] == "finnhub"

    def test_empty_sources_defaults_to_unknown(self):
        """When sources list is empty, source defaults to 'unknown'."""
        buckets = [_Bucket(avg=0.5, sources=[], timestamp="2024-11-15T00:00:00Z")]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["source"] == "unknown"

    def test_source_without_colon(self):
        """Source string without ':' uses the full string as provider."""
        buckets = [
            _Bucket(avg=0.5, sources=["rawprovider"], timestamp="2024-11-15T00:00:00Z")
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["source"] == "rawprovider"


# ---------------------------------------------------------------------------
# Source filtering
# ---------------------------------------------------------------------------


class TestSourceFilter:
    """Source filter excludes non-matching sources."""

    def test_aggregated_includes_all_sources(self):
        """source='aggregated' includes buckets from any provider."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="2024-11-01T00:00:00Z"),
            _Bucket(avg=0.3, sources=["finnhub:2"], timestamp="2024-11-02T00:00:00Z"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert len(points) == 2

    def test_specific_source_excludes_others(self):
        """Filtering by 'tiingo' excludes finnhub buckets."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="2024-11-01T00:00:00Z"),
            _Bucket(avg=0.3, sources=["finnhub:2"], timestamp="2024-11-02T00:00:00Z"),
            _Bucket(avg=0.7, sources=["tiingo:3"], timestamp="2024-11-03T00:00:00Z"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="tiingo")
        assert len(points) == 2
        assert all(p["source"] == "tiingo" for p in points)

    def test_no_matching_source_returns_empty(self):
        """When no buckets match the source filter, result is empty."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="2024-11-01T00:00:00Z"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="finnhub")
        assert len(points) == 0


# ---------------------------------------------------------------------------
# Empty buckets
# ---------------------------------------------------------------------------


class TestEmptyBuckets:
    """Empty bucket list returns empty history."""

    def test_empty_buckets_returns_empty_list(self):
        """No buckets produces an empty history list."""
        points = _map_buckets_to_points([], source_filter="aggregated")
        assert points == []
        assert len(points) == 0


# ---------------------------------------------------------------------------
# Label derivation
# ---------------------------------------------------------------------------


class TestLabelDerivation:
    """Labels are derived from score thresholds."""

    @pytest.mark.parametrize(
        "score,expected_label",
        [
            (0.33, "positive"),
            (0.5, "positive"),
            (1.0, "positive"),
            (0.32, "neutral"),
            (0.0, "neutral"),
            (-0.32, "neutral"),
            (-0.33, "negative"),
            (-0.5, "negative"),
            (-1.0, "negative"),
        ],
    )
    def test_label_from_score(self, score: float, expected_label: str):
        """Score threshold determines label classification."""
        buckets = [
            _Bucket(avg=score, sources=["tiingo:1"], timestamp="2024-11-15T00:00:00Z")
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["label"] == expected_label

    def test_exact_boundary_positive(self):
        """Score of exactly 0.33 is classified as positive."""
        buckets = [
            _Bucket(avg=0.33, sources=["tiingo:1"], timestamp="2024-11-15T00:00:00Z")
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["label"] == "positive"

    def test_exact_boundary_negative(self):
        """Score of exactly -0.33 is classified as negative."""
        buckets = [
            _Bucket(avg=-0.33, sources=["tiingo:1"], timestamp="2024-11-15T00:00:00Z")
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert points[0]["label"] == "negative"


# ---------------------------------------------------------------------------
# Invalid timestamp handling
# ---------------------------------------------------------------------------


class TestInvalidTimestamp:
    """Buckets with invalid timestamps are skipped."""

    def test_invalid_timestamp_skipped(self):
        """A bucket with an unparseable timestamp is silently skipped."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="not-a-date"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert len(points) == 0

    def test_mixed_valid_invalid_timestamps(self):
        """Valid buckets are kept, invalid ones are dropped."""
        buckets = [
            _Bucket(avg=0.5, sources=["tiingo:1"], timestamp="2024-11-15T00:00:00Z"),
            _Bucket(avg=0.3, sources=["tiingo:2"], timestamp="garbage"),
            _Bucket(avg=0.1, sources=["tiingo:3"], timestamp="2024-11-17T00:00:00Z"),
        ]
        points = _map_buckets_to_points(buckets, source_filter="aggregated")
        assert len(points) == 2
