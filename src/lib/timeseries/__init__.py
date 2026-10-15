"""
Time-series library for multi-resolution sentiment data.

Feature 1009: Real-Time Multi-Resolution Sentiment Time-Series

This module provides utilities for:
- Time bucket alignment ([CS-009, CS-010])
- OHLC aggregation ([CS-011, CS-012])
- DynamoDB key design ([CS-002, CS-004])
- Signed accumulating write fanout (feature 001-signed-fanout)
"""

from src.lib.timeseries.aggregation import aggregate_ohlc
from src.lib.timeseries.bucket import calculate_bucket_progress, floor_to_bucket
from src.lib.timeseries.cache import CacheStats, ResolutionCache, get_global_cache
from src.lib.timeseries.fanout import FanoutWriteError, accumulate_fanout
from src.lib.timeseries.models import (
    OHLCBucket,
    PartialBucket,
    Resolution,
    SentimentBucket,
    SentimentScore,
    TimeseriesKey,
)
from src.lib.timeseries.signed import label_to_signed

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
    "accumulate_fanout",
    "FanoutWriteError",
    "label_to_signed",
    # Cache utilities [CS-005, CS-006]
    "ResolutionCache",
    "CacheStats",
    "get_global_cache",
]
