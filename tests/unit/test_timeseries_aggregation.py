"""
TDD-OHLC-001: OHLC aggregation from raw scores tests.

Canonical Reference: [CS-011] Netflix on OHLC for non-financial, [CS-012] ACM Queue on aggregation

Tests MUST be written FIRST and FAIL before implementation.
"""

from datetime import datetime

import pytest

from src.lib.timeseries.aggregation import aggregate_ohlc
from src.lib.timeseries.models import SentimentScore


def parse_iso(iso_str: str) -> datetime:
    """Parse ISO8601 timestamp to datetime."""
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


class TestOHLCAggregation:
    """
    Canonical: [CS-011] "OHLC effective for any bounded metric where extrema matter"
    [CS-012] "Min/max/open/close captures distribution shape efficiently"
    """

    def test_single_score_all_ohlc_equal(self) -> None:
        """Single score: open == high == low == close."""
        scores = [
            SentimentScore(
                value=0.75,
                timestamp=parse_iso("2025-12-21T10:35:15Z"),
            )
        ]
        result = aggregate_ohlc(scores)
        assert result.open == 0.75
        assert result.high == 0.75
        assert result.low == 0.75
        assert result.close == 0.75

    def test_multiple_scores_ordered_by_timestamp(self) -> None:
        """
        Given scores: [0.6, 0.9, 0.3, 0.7] in timestamp order
        Then: open=0.6, high=0.9, low=0.3, close=0.7
        """
        scores = [
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.9, timestamp=parse_iso("2025-12-21T10:35:20Z")),
            SentimentScore(value=0.3, timestamp=parse_iso("2025-12-21T10:35:30Z")),
            SentimentScore(value=0.7, timestamp=parse_iso("2025-12-21T10:35:40Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.open == 0.6  # First by timestamp
        assert result.high == 0.9  # Maximum value
        assert result.low == 0.3  # Minimum value
        assert result.close == 0.7  # Last by timestamp

    def test_unordered_input_sorted_by_timestamp(self) -> None:
        """Scores provided out-of-order MUST be sorted before aggregation."""
        scores = [
            SentimentScore(value=0.7, timestamp=parse_iso("2025-12-21T10:35:40Z")),
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.9, timestamp=parse_iso("2025-12-21T10:35:20Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.open == 0.6  # Earliest timestamp
        assert result.close == 0.7  # Latest timestamp

    def test_empty_scores_raises_value_error(self) -> None:
        """Empty score list MUST raise ValueError, not return zeros."""
        with pytest.raises(ValueError, match="Cannot aggregate empty"):
            aggregate_ohlc([])

    def test_label_counts_aggregation(self) -> None:
        """Label counts MUST sum individual sentiment labels."""
        scores = [
            SentimentScore(
                value=0.8,
                label="positive",
                timestamp=parse_iso("2025-12-21T10:35:10Z"),
            ),
            SentimentScore(
                value=0.1,
                label="neutral",
                timestamp=parse_iso("2025-12-21T10:35:20Z"),
            ),
            SentimentScore(
                value=0.9,
                label="positive",
                timestamp=parse_iso("2025-12-21T10:35:30Z"),
            ),
            SentimentScore(
                value=-0.6,
                label="negative",
                timestamp=parse_iso("2025-12-21T10:35:40Z"),
            ),
        ]
        result = aggregate_ohlc(scores)
        assert result.label_counts == {"positive": 2, "neutral": 1, "negative": 1}

    def test_average_calculated_correctly(self) -> None:
        """Average MUST be sum/count, not recomputed from OHLC."""
        scores = [
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.8, timestamp=parse_iso("2025-12-21T10:35:20Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.avg == pytest.approx(0.7, rel=0.001)
        assert result.count == 2
        assert result.sum == pytest.approx(1.4, rel=0.001)

    def test_negative_sentiment_values_handled(self) -> None:
        """Negative sentiment values MUST be handled correctly."""
        scores = [
            SentimentScore(value=-0.8, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=-0.2, timestamp=parse_iso("2025-12-21T10:35:20Z")),
            SentimentScore(value=-0.5, timestamp=parse_iso("2025-12-21T10:35:30Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.open == -0.8
        assert result.high == -0.2
        assert result.low == -0.8
        assert result.close == -0.5

    def test_same_timestamp_uses_value_order(self) -> None:
        """Scores with identical timestamps MUST maintain stable ordering."""
        scores = [
            SentimentScore(value=0.5, timestamp=parse_iso("2025-12-21T10:35:00Z")),
            SentimentScore(value=0.7, timestamp=parse_iso("2025-12-21T10:35:00Z")),
        ]
        result = aggregate_ohlc(scores)
        # Both have same timestamp, so order is stable (first in = open)
        assert result.open == 0.5
        assert result.close == 0.7
