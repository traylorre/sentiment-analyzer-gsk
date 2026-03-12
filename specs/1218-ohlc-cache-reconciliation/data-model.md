# Data Model: OHLC Cache Reconciliation

**Feature**: 1218-ohlc-cache-reconciliation
**Date**: 2026-02-12

## Existing Entities (No Changes)

### CachedCandle (pydantic model)

Location: `src/lambdas/shared/cache/ohlc_cache.py`

```
CachedCandle
├── timestamp: datetime
├── open: float
├── high: float
├── low: float
├── close: float
├── volume: int = 0
├── source: str
└── resolution: str
```

No changes to the application-level model.

### OHLCCacheResult (pydantic model)

Location: `src/lambdas/shared/cache/ohlc_cache.py`

```
OHLCCacheResult
├── candles: list[CachedCandle]
├── cache_hit: bool
└── missing_ranges: list[tuple[datetime, datetime]]
```

No changes needed. The `cache_hit` field combined with cache write timestamp provides enough information for the `X-Cache-Age` header calculation.

## DynamoDB Item Schema Changes

### {env}-ohlc-cache Table

**Current schema** (item attributes):

| Attribute | Type | Key | Description |
| --------- | ---- | --- | ----------- |
| PK | S | Partition | `{ticker}#{source}` (e.g., `AAPL#tiingo`) |
| SK | S | Sort | `{resolution}#{timestamp}` (e.g., `5#2025-12-27T10:30:00Z`) |
| open | N | — | Opening price (4 decimal places) |
| high | N | — | Highest price |
| low | N | — | Lowest price |
| close | N | — | Closing price |
| volume | N | — | Trading volume |
| fetched_at | S | — | ISO8601 timestamp of when data was fetched |

**New attribute added**:

| Attribute | Type | Key | Description |
| --------- | ---- | --- | ----------- |
| ttl | N | — | Unix epoch seconds. DynamoDB auto-deletes item after this time. |

**TTL calculation**:
- Daily resolution OR past trading day intraday: `fetched_at + 90 days`
- Current trading day intraday: `fetched_at + 5 minutes`

**Terraform change**: Add `ttl { attribute_name = "ttl" enabled = true }` to the `aws_dynamodb_table.ohlc_cache` resource.

**Migration**: None needed. Existing items without `ttl` attribute are ignored by DynamoDB TTL. Only new writes will have the attribute.

## New Enum: CacheSource

Not a pydantic model — a simple string constant set used for response headers.

```
CacheSource values:
├── "in-memory"          — Served from module-level dict cache
├── "persistent-cache"   — Served from DynamoDB
├── "live-api"           — Fresh fetch from external API (cache miss)
└── "live-api-degraded"  — Fresh fetch because cache read/write failed
```

Used to set the `X-Cache-Source` response header. Not persisted anywhere.

## Validation Rules

1. `ttl` MUST be a positive integer greater than the current epoch time at write
2. `ttl` for daily data MUST be at least 89 days in the future (allows 1-day margin)
3. `ttl` for current-day intraday MUST be no more than 10 minutes in the future
4. Items without `ttl` attribute are valid (backward compatibility with existing data)
