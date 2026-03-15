# Research: Fix SSE Lambda Dockerfile Missing Metrics Module

**Feature**: 1221-fix-sse-metrics-copy
**Date**: 2026-03-15

## R1: Root Cause Analysis

**Decision**: The SSE Dockerfile uses selective COPY instructions for `lib/` submodules,
unlike the analysis and dashboard Dockerfiles which copy all of `lib/`. When `fanout.py`
gained an import of `src.lib.metrics.emit_metric` in PR #720, the SSE Dockerfile was
not updated to include `lib/metrics.py`.

**Rationale**: The import chain is:
1. `src/lib/timeseries/__init__.py` imports from `fanout.py`
2. `fanout.py` imports `from src.lib.metrics import emit_metric`
3. `src/lambdas/shared/circuit_breaker.py` also imports `from src.lib.metrics import emit_metric`
4. Both are COPY'd into the container, but their dependency (`metrics.py`) is not

**Alternatives considered**:
- Copy entire `lib/` directory (like analysis/dashboard Dockerfiles): Would work but
  adds unnecessary files (deduplication.py, threading_utils.py, README.md, __pycache__)
  to a size-sensitive image with ADOT sidecar
- Add .dockerignore to exclude __pycache__: Extra file for marginal benefit

## R2: Fix Approach

**Decision**: Add `COPY lib/metrics.py /var/task/src/lib/metrics.py` to the SSE
Dockerfile, placed after the existing `COPY lib/timeseries` line.

**Rationale**:
- Minimal change (one line)
- Consistent with the existing selective-copy pattern in the SSE Dockerfile
- The `__init__.py` for `src/lib/` is already created by the `RUN mkdir/touch` step
- `metrics.py` has no transitive imports from other `src.lib.*` modules (verified:
  only imports stdlib, boto3, and aws_lambda_powertools which are installed via pip)

**Alternatives considered**:
- Replace selective copies with `COPY lib /var/task/src/lib`: Simpler but copies
  unnecessary files; would require adding `.dockerignore` to exclude `__pycache__/`
- No-op in Dockerfile, mock metrics in SSE Lambda: Would mask a real dependency

## R3: ADOT Layer Interaction

**Decision**: The metrics.py COPY is independent of the ADOT layer COPY steps.

**Rationale**: The ADOT wildcard COPY pattern (`adot-laye[r]/...`) uses Docker glob
syntax to gracefully skip when the directory is absent. The metrics.py COPY uses a
direct file path which always succeeds (the file always exists in the build context).
These two mechanisms are independent and do not interact.

## R4: Deploy Pipeline ADOT IAM Issue

**Decision**: The ADOT layer download step fails with AccessDeniedException because
the IAM policy granting `lambda:GetLayerVersion` on the public ADOT layer
(`901920570463:layer:aws-otel-collector-*`) has never been deployed to AWS. However,
this step has `continue-on-error: true` and the Dockerfile handles absent ADOT files
gracefully. The actual deploy failure is the smoke test ModuleNotFoundError, not the
ADOT IAM issue.

**Rationale**: Once the metrics.py COPY fix is deployed, the smoke test will pass.
The ADOT layer will be absent (first deploy), but the wildcard COPY handles this.
On the next deploy after the IAM policy takes effect, the ADOT layer will be
downloaded and embedded.
