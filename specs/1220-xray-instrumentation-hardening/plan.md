# Implementation Plan: X-Ray Instrumentation Hardening

**Branch**: `1220-xray-instrumentation-hardening` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Status**: Rev 2 -- principal engineer plan review applied

## Summary

Harden X-Ray instrumentation across 3 gaps: (1) embed ADOT Collector sidecar in SSE Lambda container for OTel streaming-phase span export, (2) add frontend trace ID generation + CORS prerequisites for browser-to-Lambda trace continuity, (3) add SilentFailure/Count metrics to 5 fanout error handlers matching the established 4-module pattern.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript/Next.js 14 (frontend), HCL/Terraform 1.5+ (infra)
**Primary Dependencies**: opentelemetry-sdk 1.39.1, aws-lambda-powertools 3.23.0, ADOT Collector Layer v0.102.1
**Storage**: N/A (observability changes only)
**Testing**: pytest (unit), Playwright (E2E), pre-commit hooks
**Target Platform**: AWS Lambda (container), Amplify (frontend), CloudWatch/X-Ray
**Project Type**: Web application (backend Lambda + Next.js frontend + Terraform infra)
**Performance Goals**: ADOT cold start <= 500ms, trace header generation < 1ms, metric emission < 100ms
**Constraints**: No OTel SDK version conflicts, fail-open on all trace paths, no SSE functionality regression
**Scale/Scope**: 3 Dockerfiles, 2 Terraform files, 4 frontend files, 1 backend file, 1 CI workflow

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Unit test accompaniment (s7) | PASS | All changes accompanied by unit tests |
| GPG-signed commits (s8) | PASS | Standard workflow |
| No pipeline bypass (s8) | PASS | Standard workflow |
| External dependency mocking (s7) | PASS | ADOT mocked in unit tests; real in preprod E2E |
| SAST before push (s10) | PASS | make validate includes SAST |
| Tech debt tracking (s9) | PASS | No workarounds; pattern-copy approach |
| Least-privilege IAM (s3) | PASS | Minimal addition: GetLayerVersion for ADOT public layer ARN |
| TLS in transit (s3) | PASS | OTLP over localhost; X-Ray export over HTTPS |

No violations. Complexity Tracking not needed.

## Plan Review Corrections (Rev 2)

1. **CRITICAL: Dockerfile permission model** -- ADOT COPY must happen BEFORE USER switch (line 66) with chmod +x while root. Lambda runtime invokes extensions as root.
2. **sse-connection.ts removed** -- Already accepts headers option (line 46), spreads into fetch (line 148), reads response trace ID (lines 168-171). Zero changes needed.
3. **route.ts downscoped** -- Fallback trace ID is ~3 lines. Low value; browser generation (FR-007) is the real fix.
4. **fanout.py import verification** -- File has ZERO observability imports. Must verify tracer and emit_metric work from src/lib/timeseries/ path.
5. **REST client trace injection deferred** -- Core P2 value is SSE. REST goes through API Gateway (already has CORS). Custom headers on every REST call trigger preflight.
6. **ADOT build context** -- Download to src/lambdas/sse_streaming/adot-layer/ before docker build (context is src/).
7. **CORS rollback** -- Lambda Function URL CORS changes are instant, revertible via single Terraform commit.

## Source Code Changes

```text
# P1: SSE Lambda ADOT Extension
src/lambdas/sse_streaming/Dockerfile       # MODIFY: Embed ADOT (BEFORE USER switch, chmod +x)
src/lambdas/analysis/Dockerfile            # MODIFY: Add exclusion comment (1 line)
src/lambdas/dashboard/Dockerfile           # MODIFY: Add exclusion comment (1 line)
.github/workflows/deploy.yml              # MODIFY: ADOT Layer download step
infrastructure/terraform/ci-user-policy.tf # MODIFY: Add ADOT layer ARN

# P2: Frontend Trace Propagation (SSE only; REST deferred)
infrastructure/terraform/main.tf           # MODIFY: CORS allow/expose headers
frontend/src/lib/tracing.ts                # NEW: X-Ray trace ID generator (~20 lines)
frontend/src/hooks/use-sse.ts              # MODIFY: Pass trace headers + fix comments
frontend/src/app/api/sse/[...path]/route.ts  # MODIFY: Fallback trace ID (~3 lines)
frontend/tests/e2e/xray-trace-propagation.spec.ts  # MODIFY: Assert request headers
# DEFERRED: frontend/src/lib/api/client.ts (REST trace injection)
# NO CHANGE: frontend/src/lib/api/sse-connection.ts (already supports headers)

# P3: Fanout Metric Emission
src/lib/timeseries/fanout.py               # MODIFY: Add imports + metrics to 5 handlers
tests/unit/test_timeseries_fanout.py       # MODIFIED: Added TestFanoutMetricEmission class (6 tests)
```

11 files modified, 1 new file (tracing.ts), 1 deferred (client.ts).

## Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| ADOT COPY after USER switch breaks extension | Critical | COPY before line 66, chmod +x while root |
| ADOT layer outside Docker build context | Medium | Download to src/lambdas/sse_streaming/adot-layer/ before build |
| fanout.py tracer/emit_metric from lib path | High | First task: verify imports; add integration test |
| CORS change breaks existing SSE | Low | Instant; revert via terraform apply |
| REST preflight from custom header | Medium | Deferred to follow-up task |
