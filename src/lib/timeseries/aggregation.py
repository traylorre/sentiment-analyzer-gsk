"""
OHLC aggregation logic for sentiment data.

Canonical References:
- [CS-011] Netflix Tech Blog: OHLC for non-financial metrics
- [CS-012] ACM Queue 2017: Time-Series Databases aggregation patterns
"""

from collections import Counter

from src.lib.timeseries.models import OHLCBucket, SentimentScore


def aggregate_ohlc(scores: list[SentimentScore]) -> OHLCBucket:
    """
    Aggregate sentiment scores into an OHLC bucket.

    Canonical: [CS-011] "OHLC effective for any bounded metric where extrema matter"
    [CS-012] "Min/max/open/close captures distribution shape efficiently"

    Args:
        scores: List of sentiment scores to aggregate

    Returns:
        OHLCBucket: Aggregated OHLC data

    Raises:
        ValueError: If scores list is empty
    """
    if not scores:
        raise ValueError("Cannot aggregate empty score list")

    # Sort by timestamp for correct open/close determination
    sorted_scores = sorted(scores, key=lambda s: (s.timestamp, scores.index(s)))

    values = [s.value for s in sorted_scores]

    # Count labels
    labels = [s.label for s in sorted_scores if s.label]
    label_counts = dict(Counter(labels))

    total_sum = sum(values)
    count = len(values)

    return OHLCBucket(
        open=sorted_scores[0].value,
        high=max(values),
        low=min(values),
        close=sorted_scores[-1].value,
        count=count,
        sum=total_sum,
        avg=total_sum / count,
        label_counts=label_counts,
    )
