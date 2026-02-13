# Implementation Plan: OHLC Cache Reconciliation

**Branch**: `1218-ohlc-cache-reconciliation` | **Date**: 2026-02-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1218-ohlc-cache-reconciliation/spec.md`

## Summary

Post-framework-purge reconciliation of the OHLC persistent cache. All five original CACHE-001 work orders are already implemented. This plan addresses quality defects: silent error handling → explicit degradation with observability headers, missing TTL on DynamoDB items, latent parsing bug, no batch write retry, and stale documentation referencing removed patterns.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: aws-lambda-powertools (routing, Response), boto3 (DynamoDB client), pydantic (models), orjson (JSON serialization)
**Storage**: DynamoDB (`{env}-ohlc-cache`, PAY_PER_REQUEST, PK=`{ticker}#{source}`, SK=`{resolution}#{timestamp}`)
**Testing**: pytest + moto (`@mock_aws`), `make_event()` + `lambda_handler` invocation pattern
**Target Platform**: AWS Lambda (Python 3.13 runtime)
**Project Type**: single (serverless)
**Performance Goals**: DynamoDB read < 100ms p95, cache hit rate > 90% for repeated requests
**Constraints**: Lambda 29s timeout budget, DynamoDB BatchWrite 25-item limit, Tiingo rate limits
**Scale/Scope**: ~50 tickers, daily + intraday resolutions, two-tier cache (in-memory + DynamoDB)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status | Notes |
| ---- | ----------- | ------ | ----- |
| Testing (§7) | All implementation accompanied by unit tests, 80% coverage | PASS | Will add tests for every changed function |
| Deterministic Dates (Amend 1.5) | No `date.today()` in tests | PASS | Will use fixed dates (`date(2024, 1, 2)`) |
| Pipeline (Amend 1.2) | No bypass | PASS | Standard PR flow |
| GPG Signing (§8) | All commits signed | PASS | `git commit -S` |
| SAST (Amend 1.6) | Local security scan before push | PASS | `make validate` includes SAST |
| DynamoDB Safety (Arch Notes) | Use ExpressionAttributeNames | PASS | Existing code already uses them — but response parsing is buggy (FR-006 fixes this) |
| Observability (§6) | Structured logs, no raw text | PASS | Will use structured logging for all error paths |
| No Silent Degradation | Cache errors must be visible | PASS | Core objective of this reconciliation |

## Project Structure

### Documentation (this feature)

```text
specs/1218-ohlc-cache-reconciliation/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cache-headers.md # X-Cache-* response header contract
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (files to modify)

```text
src/lambdas/
├── dashboard/
│   └── ohlc.py                          # P1: Error handling, P2: Headers
├── shared/
│   ├── cache/
│   │   └── ohlc_cache.py                # P5: Parsing fix, retry, dead code
│   └── models/
│       └── ohlc.py                      # (no changes needed)

infrastructure/terraform/
└── modules/dynamodb/
    └── main.tf                          # P3: Add TTL attribute to ohlc-cache table

scripts/
└── check-banned-terms.sh               # P4: Remove docs/cache/ exclusion

docs/cache/
├── HL-cache-remediation-checklist.md    # P4: Mark items complete
├── fix-cache-key.md                     # P4: Purge banned terms
├── fix-cache-writing.md                 # P4: Purge banned terms
├── fix-cache-reading.md                 # P4: Purge banned terms
├── fix-cache-tests.md                   # P4: Purge banned terms
└── fix-local-api-tables.md              # P4: Purge banned terms

.specify/specs/
├── ohlc-cache-remediation.md            # P4: Purge banned terms (lines 1000, 1124)
├── ohlc-cache-remediation-tests.md      # P4: Review for banned terms
└── ohlc-cache-remediation-clarifications.md  # P4: Update BENCHED status

tests/
├── unit/
│   ├── dashboard/
│   │   ├── test_ohlc.py                 # Update: test explicit degradation headers
│   │   └── test_ohlc_cache.py           # No changes (in-memory cache unaffected)
│   └── shared/cache/
│       └── test_ohlc_persistent_cache.py # Update: test error propagation, retry, TTL
└── integration/ohlc/
    ├── test_happy_path.py               # Update: verify cache headers present
    └── test_error_resilience.py          # Update: verify explicit degradation
```

**Structure Decision**: Existing single-project serverless structure. No new directories needed. All changes are modifications to existing files.

## Complexity Tracking

No constitution violations requiring justification. All changes are within existing modules.

---

## Phase 0: Research

### R1: DynamoDB TTL — Adding to Existing Table with Existing Items

**Decision**: Use DynamoDB's native TTL feature with a `ttl` attribute (epoch seconds).

**Rationale**: DynamoDB TTL is the canonical approach for automatic item expiration. AWS handles deletion asynchronously (typically within 48 hours of expiration). No application-level garbage collection needed.

**Key details**:
- TTL attribute stores a Unix epoch timestamp (seconds). DynamoDB compares it to current time and deletes expired items automatically.
- Existing items without the `ttl` attribute are NOT affected — they persist indefinitely. This means the rollout is safe: old items stay, new items get TTL.
- Terraform: Add `ttl { attribute_name = "ttl" enabled = true }` block to the table resource.
- Python: When writing items, calculate `ttl = int((datetime.now(UTC) + timedelta(days=90)).timestamp())` for historical data, or `ttl = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())` for current-day intraday data.

**Alternatives considered**:
- Application-level scan-and-delete: Rejected — unnecessary complexity, DynamoDB handles this natively.
- Separate TTL per resolution: Rejected — the spec distinguishes only historical (90d) vs. current-day intraday (5min). Past intraday data is immutable once the trading day ends, so it gets 90d TTL.

### R2: Lambda Powertools Custom Response Headers

**Decision**: Use the `headers` parameter on the `Response` object constructor.

**Rationale**: Lambda Powertools `Response` accepts a `headers: dict[str, str]` parameter. The existing codebase already uses `Response(status_code=..., content_type=..., body=..., headers=...)` in `response_builder.py`.

**Pattern**:
```python
from aws_lambda_powertools.event_handler import Response

headers = {
    "X-Cache-Source": "in-memory",
    "X-Cache-Age": "42",
}
return Response(
    status_code=200,
    content_type="application/json",
    body=orjson.dumps(data).decode(),
    headers=headers,
)
```

**No unknowns**: This is already the established pattern in the codebase (`response_builder.py:json_response`).

### R3: Exponential Backoff for BatchWrite Unprocessed Items

**Decision**: Retry unprocessed items with exponential backoff (base 100ms, max 3 retries).

**Rationale**: AWS best practice for `BatchWriteItem` is to retry unprocessed items with exponential backoff. The AWS SDK's built-in retry handles throttling errors, but `UnprocessedItems` in a successful response requires application-level retry.

**Pattern**:
```python
import time

MAX_RETRIES = 3
BASE_DELAY_MS = 100

for attempt in range(MAX_RETRIES + 1):
    response = client.batch_write_item(RequestItems={table: batch})
    unprocessed = response.get("UnprocessedItems", {}).get(table, [])

    if not unprocessed:
        break  # All items processed

    if attempt < MAX_RETRIES:
        delay = BASE_DELAY_MS * (2 ** attempt) / 1000  # 0.1s, 0.2s, 0.4s
        time.sleep(delay)
        batch = unprocessed  # Retry only unprocessed items
    else:
        raise RuntimeError(
            f"BatchWrite failed after {MAX_RETRIES} retries: "
            f"{len(unprocessed)} items unprocessed"
        )
```

**Source**: [AWS DynamoDB Developer Guide — BatchWriteItem](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html#Programming.Errors.BatchOperations)

**Alternatives considered**:
- Silently drop unprocessed items (current behavior): Rejected — violates fail-fast principle.
- Use boto3 built-in retry config: Doesn't apply to `UnprocessedItems` — only to HTTP-level errors.

### R4: DynamoDB Response Attribute Names (Latent Bug)

**Decision**: Use actual attribute names (`open`, `close`) in response parsing — not expression alias names (`#o`, `#c`).

**Rationale**: When DynamoDB returns query results, the item keys are the actual attribute names regardless of what aliases were used in `ProjectionExpression`/`ExpressionAttributeNames`. The aliases only affect the expression string itself.

**Current bug**: `ohlc_cache.py:206-213` checks for `item["#o"]` first (which always fails `KeyError`), then falls through to `item.get("open", ...)`. The secondary path works correctly, masking the bug.

**Fix**: Remove the `"#o" in item` check entirely. Use `item["open"]["N"]` directly. The `ProjectionExpression` already requests these attributes, so they will always be present in successful responses.

**Source**: [AWS DynamoDB Developer Guide — Expression Attribute Names](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ExpressionAttributeNames.html) — "Expression attribute names are substitutes used in an expression... The response items use the actual attribute names."

---

## Phase 1: Design

### Data Model Changes

**File**: `data-model.md` (see separate artifact)

The only data model change is adding a `ttl` attribute to DynamoDB items written by `put_cached_candles()`:

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `ttl` | Number (epoch seconds) | DynamoDB TTL expiration timestamp. 90 days from write for historical/daily data. For current-day intraday data: write time + 5 minutes. For past intraday data (completed trading day): write time + 90 days. |

No changes to `CachedCandle` pydantic model — the `ttl` attribute is DynamoDB-only metadata, not part of the application data model.

### Response Header Contract

**File**: `contracts/cache-headers.md` (see separate artifact)

All OHLC price data responses (`GET /api/v2/tickers/{ticker}/ohlc`) MUST include these headers:

| Header | Values | When Set |
| ------ | ------ | -------- |
| `X-Cache-Source` | `in-memory`, `persistent-cache`, `live-api`, `live-api-degraded` | Always |
| `X-Cache-Age` | Integer (seconds since data was cached, 0 for live-api) | Always |
| `X-Cache-Error` | String (error description) | Only when `X-Cache-Source` is `live-api-degraded` |
| `X-Cache-Write-Error` | `true` | Only when cache write fails after live-api fetch |

### Error Propagation Design

**Current (BROKEN)**:
```
Cache module catches exception → returns None → handler doesn't know why
```

**New (CORRECT)**:
```
Cache module raises exception → handler catches → logs ERROR → sets degradation headers → fetches from API
```

Changes to `ohlc_cache.py`:
- `get_cached_candles()`: Remove `try/except ClientError` wrapping. Let `ClientError` propagate.
- `put_cached_candles()`: Remove `try/except ClientError` wrapping. Let `ClientError` propagate.

Changes to `ohlc.py`:
- `_read_from_dynamodb()`: Remove `try/except Exception`. Let exceptions from `get_cached_candles()` propagate.
- `_write_through_to_dynamodb()`: Remove `try/except Exception`. Let exceptions from `put_cached_candles()` propagate.
- `get_ohlc_data()`: Add explicit try/except around DynamoDB read and write calls. On exception: log ERROR, set `cache_error` context variable, continue to external API fetch with degradation headers.

### Quickstart

**File**: `quickstart.md` (see separate artifact)

```bash
# 1. Ensure on the right branch
git checkout 1218-ohlc-cache-reconciliation

# 2. Run existing tests to confirm baseline
make test-local

# 3. Run banned-term scanner to see current state
bash scripts/check-banned-terms.sh

# 4. After implementation, verify
make validate          # lint + security + banned terms
make test-local        # all unit + integration tests
```

### Agent Context Update

Will run `.specify/scripts/bash/update-agent-context.sh claude` after design artifacts are written.
