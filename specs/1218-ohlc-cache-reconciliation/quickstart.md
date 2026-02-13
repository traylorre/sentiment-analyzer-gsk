# Quickstart: OHLC Cache Reconciliation

**Feature**: 1218-ohlc-cache-reconciliation
**Date**: 2026-02-12

## Prerequisites

- Python 3.13
- AWS credentials configured (for integration tests)
- `make` available

## Setup

```bash
# Ensure on the right branch
git checkout 1218-ohlc-cache-reconciliation

# Verify clean baseline
make test-local
```

## Implementation Order

The implementation follows the priority order from the spec:

1. **P1: Error handling** — Remove silent catch-all in `ohlc_cache.py`, add explicit degradation in `ohlc.py`
2. **P2: Cache headers** — Add `X-Cache-Source`, `X-Cache-Age`, `X-Cache-Error`, `X-Cache-Write-Error` to all responses
3. **P3: DynamoDB TTL** — Add `ttl` attribute to Terraform config and Python write path
4. **P4: Doc hygiene** — Purge banned terms from specs/docs, update checklist, remove scanner exclusion
5. **P5: Bug fixes** — Fix `#o`/`#c` parsing, add batch write retry, remove dead code

## Verification

```bash
# After each priority level:
make test-local        # Unit + integration tests pass
make validate          # Lint + security + banned terms

# After P4 specifically:
bash scripts/check-banned-terms.sh  # Should pass WITHOUT docs/cache/ exclusion

# Final verification:
make validate && make test-local
```

## Key Files

| File | Changes |
| ---- | ------- |
| `src/lambdas/shared/cache/ohlc_cache.py` | Remove try/except, fix parsing, add retry, add TTL, remove dead code |
| `src/lambdas/dashboard/ohlc.py` | Add explicit degradation handlers, add cache headers to all Response objects |
| `infrastructure/terraform/modules/dynamodb/main.tf` | Add TTL block to ohlc-cache table |
| `scripts/check-banned-terms.sh` | Remove `docs/cache/` exclusion |
| `docs/cache/*.md` | Purge banned terms, mark checklist complete |
| `.specify/specs/ohlc-cache-remediation*.md` | Purge banned terms, update BENCHED status |
| `tests/unit/shared/cache/test_ohlc_persistent_cache.py` | Add tests for error propagation, retry, TTL |
| `tests/unit/dashboard/test_ohlc.py` | Add tests for degradation headers |
