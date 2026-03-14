# Quickstart: X-Ray Instrumentation Hardening

**Feature**: 1220-xray-instrumentation-hardening | **Rev 2**

## P1: SSE Lambda ADOT Extension

### 1. IAM Policy (ci-user-policy.tf)
Add ADOT public layer ARN to Lambda Layers statement resources.

### 2. CI Layer Download (deploy.yml)
Add step BEFORE docker build-push-action. Download layer zip to src/lambdas/sse_streaming/adot-layer/ (inside build context).

### 3. SSE Dockerfile
**CRITICAL**: COPY ADOT files BEFORE the USER lambda switch (before line 66). chmod +x /opt/extensions/collector while still root. Lambda runtime invokes extensions as root.

### 4. Analysis + Dashboard Dockerfiles
Add exclusion comment documenting why ADOT is not needed (Powertools + Active mode).

## P2: Frontend Trace Propagation

### 1. CORS (Terraform) -- PREREQUISITE
Add x-amzn-trace-id to allow_headers and expose_headers on SSE and Dashboard Lambda Function URLs in main.tf.

### 2. Trace ID Utility (NEW: frontend/src/lib/tracing.ts)
~20 line utility using crypto.getRandomValues() for X-Ray format trace IDs.

### 3. SSE Hook (use-sse.ts)
Pass headers with X-Amzn-Trace-Id to SSEConnection constructor. Fix misleading FR-032 comments. sse-connection.ts needs NO changes (already supports headers option).

### 4. Proxy Fallback (route.ts)
~3 lines: generate fallback trace ID if browser request lacks header.

### 5. Playwright Test Fix
Assert X-Amzn-Trace-Id in outgoing REQUEST headers (not just response).

### DEFERRED: REST client (client.ts)
Custom header on all REST calls triggers CORS preflight. Separate follow-up task.

## P3: Fanout Metric Emission

### 0. Verify Import Paths (FIRST)
Confirm src.aws.xray.tracer and src.lib.metrics.emit_metric work from src/lib/timeseries/ module path.

### 1. Add Imports to fanout.py
Import tracer and emit_metric (file currently has zero observability imports).

### 2. Add Pattern to 5 Error Handlers
Copy circuit_breaker.py pattern (lines 343-357): best-effort X-Ray subsegment + emit_metric with FailurePath dimension. For conditional handlers, emit ConditionalCheck/Count when ConditionalCheckFailedException swallowed.

## Verification
- pytest tests/unit/test_fanout_metrics.py -v
- pre-commit run --all-files
- cd frontend && npx playwright test tests/e2e/xray-trace-propagation.spec.ts
- cd infrastructure/terraform && terraform plan
