# Quickstart: Fix SSE Lambda Dockerfile Missing Metrics Module

**Feature**: 1221-fix-sse-metrics-copy
**Date**: 2026-03-15

## What Changed

One line added to `src/lambdas/sse_streaming/Dockerfile`:

```dockerfile
COPY lib/metrics.py /var/task/src/lib/metrics.py
```

This copies the metrics module into the SSE Lambda container image so that
`fanout.py` and `circuit_breaker.py` can import `src.lib.metrics.emit_metric`.

## How to Verify Locally

```bash
cd src
docker build -t sse-test -f lambdas/sse_streaming/Dockerfile .
docker run --rm \
  -e PYTHONPATH=/var/task/packages:/var/task \
  -e USERS_TABLE=test \
  -e SENTIMENTS_TABLE=test \
  --entrypoint python sse-test -c \
  "from src.lib.metrics import emit_metric; print('OK')"
```

Expected output: `OK`

## Why This Fix

PR #720 added metric emission to 5 error handlers in `fanout.py`, introducing
`from src.lib.metrics import emit_metric`. The SSE Dockerfile only copied
`lib/timeseries/` (not `lib/metrics.py`), causing `ModuleNotFoundError` in the
CI smoke test and blocking all deploys.

## No Data Model or API Contracts

This feature modifies only a Dockerfile COPY instruction. No data models,
API contracts, or new modules are introduced.
