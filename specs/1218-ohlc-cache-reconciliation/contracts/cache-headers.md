# Contract: OHLC Cache Response Headers

**Feature**: 1218-ohlc-cache-reconciliation
**Date**: 2026-02-12
**Endpoint**: `GET /api/v2/tickers/{ticker}/ohlc`

## Headers

All OHLC price data responses MUST include these headers:

### X-Cache-Source (REQUIRED — always present)

Indicates where the response data was sourced from.

| Value | Meaning |
| ----- | ------- |
| `in-memory` | Data served from the Lambda module-level in-memory cache |
| `persistent-cache` | Data served from DynamoDB persistent cache |
| `live-api` | Data fetched fresh from external API (normal cache miss) |
| `live-api-degraded` | Data fetched from external API because cache read FAILED (not just missed) |

### X-Cache-Age (REQUIRED — always present)

Integer. Number of seconds since the data was originally cached.

| Scenario | Value |
| -------- | ----- |
| In-memory hit | Seconds since data was stored in module-level cache |
| Persistent cache hit | Seconds since `fetched_at` timestamp on the DynamoDB items |
| Live API fetch | `0` |
| Degraded mode | `0` |

### X-Cache-Error (CONDITIONAL — only on degradation)

String. Human-readable description of the cache error that caused degradation.

Present only when `X-Cache-Source` is `live-api-degraded`.

Examples:
- `DynamoDB ClientError: AccessDeniedException`
- `DynamoDB ClientError: ResourceNotFoundException`
- `DynamoDB ClientError: ProvisionedThroughputExceededException`
- `Parse error: KeyError 'open' in cached item`

### X-Cache-Write-Error (CONDITIONAL — only on write failure)

String `true`. Indicates that the cache write-through failed after fetching live data.

Present only when a write to DynamoDB fails. This tells consumers that subsequent identical requests will also miss the persistent cache until the write issue is resolved.

## Sentinel Header: X-Cache-Source: live-api-degraded

The `live-api-degraded` value is the sentinel that distinguishes:
- **Normal cache miss**: `X-Cache-Source: live-api` — Cache was checked, no data found, API called. Normal operation.
- **Cache failure**: `X-Cache-Source: live-api-degraded` — Cache check FAILED (error), API called as explicit degradation. Infrastructure problem.

Monitoring systems SHOULD alert on `X-Cache-Source: live-api-degraded` responses, as they indicate a cache infrastructure problem that needs investigation.

## CORS Note

These `X-Cache-*` headers must be included in the `Access-Control-Expose-Headers` response if the frontend reads them via JavaScript. The existing CORS configuration should be updated to expose these headers.
