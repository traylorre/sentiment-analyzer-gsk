"""
Time-series library for multi-resolution sentiment data.

Feature 1009: Real-Time Multi-Resolution Sentiment Time-Series

This module provides utilities for:
- Time bucket alignment ([CS-009, CS-010])
- OHLC aggregation ([CS-011, CS-012])
- DynamoDB key design ([CS-002, CS-004])
"""

from src.lib.timeseries.aggregation import aggregate_ohlc
from src.lib.timeseries.bucket import calculate_bucket_progress, floor_to_bucket
from src.lib.timeseries.fanout import (
    generate_fanout_items,
    write_fanout,
    write_fanout_with_update,
)
from src.lib.timeseries.models import (
    OHLCBucket,
    PartialBucket,
    Resolution,
    SentimentBucket,
    SentimentScore,
    TimeseriesKey,
)

__all__ = [
    "Resolution",
    "SentimentScore",
    "SentimentBucket",
    "PartialBucket",
    "OHLCBucket",
    "TimeseriesKey",
    "floor_to_bucket",
    "calculate_bucket_progress",
    "aggregate_ohlc",
    "generate_fanout_items",
    "write_fanout",
    "write_fanout_with_update",
]
