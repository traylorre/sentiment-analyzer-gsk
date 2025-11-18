# Shared Libraries

## Purpose

Non-Lambda-specific utilities shared across the codebase.

## Modules

### deduplication.py
Content hashing for article deduplication.

**Algorithm**:
```
source_id = "newsapi#" + sha256(url or title+publishedAt)[:16]
```

**On-Call Note**: If duplicate articles appear, check:
1. URL changed but content same → expected behavior (different source_id)
2. Hash collision (extremely rare) → items will have same source_id but different timestamps

### metrics.py
CloudWatch metrics and structured logging.

**Metrics emitted**:
- `ArticlesFetched` - Raw count from NewsAPI
- `NewItemsIngested` - After deduplication
- `DuplicatesSkipped` - Dedup count
- `AnalysisCount` - Items analyzed
- `InferenceLatencyMs` - Model inference time

**Log format**: JSON structured logging for CloudWatch Insights queries.

Example query:
```
fields @timestamp, @message
| filter level = "ERROR"
| filter correlation_id like /newsapi#/
| sort @timestamp desc
```

## Security Notes

- Deduplication uses SHA-256 (cryptographically secure)
- Metrics never include PII or article content
- Correlation IDs are safe to log (contain only source_id prefix)
