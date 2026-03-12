# Research: OHLC Cache Reconciliation

**Feature**: 1218-ohlc-cache-reconciliation
**Date**: 2026-02-12

## R1: DynamoDB TTL — Adding to Existing Table

**Decision**: Use DynamoDB native TTL with a `ttl` attribute (epoch seconds).

**Rationale**: DynamoDB TTL is the canonical AWS approach for automatic item expiration. The storage engine handles deletion asynchronously (typically within 48 hours of the TTL timestamp). No application-level garbage collection needed.

**Key details**:
- TTL attribute stores a Unix epoch timestamp (seconds)
- Existing items without the `ttl` attribute are NOT affected — they persist indefinitely
- Terraform: `ttl { attribute_name = "ttl" enabled = true }`
- Python: `ttl = int((datetime.now(UTC) + timedelta(days=90)).timestamp())`

**TTL calculation logic**:

| Resolution | Current Day? | TTL |
| ---------- | ------------ | --- |
| Daily ("D") | N/A (always historical) | write_time + 90 days |
| Intraday (1/5/15/30/60) | Yes (today) | write_time + 5 minutes |
| Intraday (1/5/15/30/60) | No (past day) | write_time + 90 days |

**Alternatives rejected**:
- Application-level scan-and-delete: Unnecessary complexity
- Per-resolution TTL: Spec only distinguishes historical vs. current-day intraday

## R2: Lambda Powertools Custom Response Headers

**Decision**: Use `headers` parameter on `Response` constructor.

**Rationale**: Already the established pattern in the codebase (`response_builder.py:json_response`). No new patterns needed.

## R3: BatchWrite Exponential Backoff

**Decision**: Retry unprocessed items with exponential backoff (base 100ms, max 3 retries, raise on exhaustion).

**Rationale**: AWS best practice. SDK retries handle HTTP errors; `UnprocessedItems` in successful responses require application-level retry.

**Source**: AWS DynamoDB Developer Guide — BatchWriteItem error handling.

## R4: DynamoDB Response Parsing (Latent Bug Fix)

**Decision**: Use actual attribute names (`open`, `close`) — not expression aliases (`#o`, `#c`).

**Rationale**: DynamoDB returns actual attribute names in response items regardless of expression aliases. Current code's primary path (`item["#o"]`) always fails; the fallback path (`item.get("open")`) works by accident.

**Source**: AWS DynamoDB Developer Guide — Expression Attribute Names.

## All NEEDS CLARIFICATION: Resolved

No remaining unknowns. All four research topics have clear decisions backed by AWS documentation and existing codebase patterns.
