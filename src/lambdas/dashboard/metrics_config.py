"""
Chaos Metrics Configuration (Feature 1247)
===========================================

Defines CloudWatch metric groups for the real-time metrics panel.
Dimension values use {environment} template placeholders, substituted at query time.
"""

METRIC_GROUPS = [
    {
        "title": "Lambda Invocations & Errors",
        "queries": [
            {
                "namespace": "AWS/Lambda",
                "metric_name": "Invocations",
                "dimensions": {"FunctionName": "{environment}-sentiment-ingestion"},
                "stat": "Sum",
                "label": "Invocations",
                "color": "#36d399",
            },
            {
                "namespace": "AWS/Lambda",
                "metric_name": "Errors",
                "dimensions": {"FunctionName": "{environment}-sentiment-ingestion"},
                "stat": "Sum",
                "label": "Errors",
                "color": "#f87272",
            },
        ],
    },
    {
        "title": "Lambda Duration (P95)",
        "queries": [
            {
                "namespace": "AWS/Lambda",
                "metric_name": "Duration",
                "dimensions": {"FunctionName": "{environment}-sentiment-ingestion"},
                "stat": "p95",
                "label": "Duration P95 (ms)",
                "color": "#fbbd23",
            },
        ],
    },
    {
        "title": "DynamoDB Writes & Throttles",
        "queries": [
            {
                "namespace": "AWS/DynamoDB",
                "metric_name": "ConsumedWriteCapacityUnits",
                "dimensions": {"TableName": "{environment}-sentiment-articles"},
                "stat": "Sum",
                "label": "Write Capacity",
                "color": "#3abff8",
            },
            {
                "namespace": "AWS/DynamoDB",
                "metric_name": "ThrottledRequests",
                "dimensions": {"TableName": "{environment}-sentiment-articles"},
                "stat": "Sum",
                "label": "Throttled Requests",
                "color": "#f87272",
            },
        ],
    },
    {
        "title": "Items Ingested",
        "queries": [
            {
                "namespace": "SentimentAnalyzer",
                "metric_name": "NewItemsIngested",
                "dimensions": {},
                "stat": "Sum",
                "label": "New Items",
                "color": "#a78bfa",
            },
        ],
    },
]
