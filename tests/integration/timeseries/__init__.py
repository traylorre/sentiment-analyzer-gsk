"""Integration tests for timeseries pipeline.

Tests the complete data flow:
- Write fanout to all 8 resolutions
- Query ordering validation
- Partial bucket detection
- OHLC aggregation accuracy

Uses LocalStack for realistic DynamoDB behavior.
"""
