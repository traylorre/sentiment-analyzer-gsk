# Quickstart: Cache Architecture Audit and Remediation

**Feature Branch**: `001-cache-architecture-audit`

## Overview

This feature fixes three high-risk cache bugs and adds observability/consistency improvements across all 12 caches in the sentiment-analyzer-gsk application.

## Key Files to Understand

Before working on this feature, read these in order:

1. **`src/lib/cache_utils.py`** (NEW) — Shared utilities: `jittered_ttl()`, `CacheStats`, `CacheMetricEmitter`
2. **`src/lambdas/shared/auth/cognito.py:413-433`** — JWKS cache (the @lru_cache being replaced)
3. **`src/lambdas/shared/quota_tracker.py:382-409`** — Quota sync mechanism (put_item → update_item)
4. **`src/lambdas/shared/cache/ticker_cache.py:234-256`** — Ticker cache (lru_cache → TTL+ETag)
5. **`src/lib/metrics.py:169-296`** — Existing metric emission helpers we reuse

## Development Workflow

```bash
# 1. Switch to feature branch
git checkout 001-cache-architecture-audit

# 2. Run existing tests (baseline — should all pass)
make test-local

# 3. Make changes (one cache at a time, with tests)
# Example: JWKS cache
# - Edit src/lambdas/shared/auth/cognito.py
# - Add tests/unit/test_jwks_cache.py
# - Run: pytest tests/unit/test_jwks_cache.py -v

# 4. Validate before push
make validate
make test-local
```

## Implementation Order

Work in this order to minimize risk and enable incremental testing:

1. **cache_utils.py** — Shared utilities (no dependencies on other changes)
2. **JWKS cache** (P1 — security fix, self-contained in cognito.py)
3. **Ticker cache** (P2 — self-contained in ticker_cache.py)
4. **Quota tracker** (P1 — most complex, touches DynamoDB write path)
5. **Jitter sweep** (P3 — mechanical change across all 12 caches)
6. **Metrics cache bound** (P3 — one-line max_entries addition)
7. **Cache metrics emission** (P3 — integrate CacheStats across all caches)
8. **Failure policy documentation** (P2 — document, then verify via fault injection tests)

## Environment Variables

New env vars introduced (all optional with defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `JWKS_CACHE_TTL` | `300` | JWKS refresh interval (seconds) |
| `JWKS_GRACE_PERIOD` | `900` | Max time to serve stale JWKS on failure (seconds) |
| `TICKER_CACHE_TTL` | `300` | Ticker list refresh interval (seconds) |
| `QUOTA_READ_CACHE_TTL` | `10` | Quota read cache (how often to check DynamoDB for aggregate count) |
| `CACHE_JITTER_PCT` | `0.1` | Jitter percentage applied to all TTLs |
| `CACHE_METRICS_FLUSH_INTERVAL` | `60` | Seconds between CloudWatch metric flushes |
| `METRICS_CACHE_MAX_ENTRIES` | `100` | Max entries for dashboard metrics cache |

## Testing Strategy

- **Unit tests**: All cache changes tested with moto (AWS) and freezegun (time). One test file per major change.
- **Deterministic time**: Use `@freeze_time` for all TTL/expiry tests. Never `datetime.now()` or `time.time()` in assertions.
- **Cache isolation**: Autouse fixture clears all caches between tests (added to tests/conftest.py).
- **Jitter testing**: Use `random.seed()` or mock `random.uniform()` for deterministic jitter in tests.
- **Quota concurrency**: Use `threading.Thread` to simulate concurrent Lambda instances in unit tests.
