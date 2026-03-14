# Feature Specification: X-Ray Instrumentation Hardening

**Feature Branch**: `1220-xray-instrumentation-hardening`
**Created**: 2026-03-14
**Status**: Draft (Rev 2 -- principal engineer review applied)

## Investigation Summary

Code investigation revealed that 3 of 6 originally proposed items are **already implemented**, and the 3 remaining gaps have nuances that change scope:

| Item | Status | Evidence |
|------|--------|----------|
| Container ADOT/OTel | **GAP** | SSE Dockerfile has TODO; only SSE needs ADOT (Analysis/Dashboard use Powertools + Active mode) |
| Frontend trace headers | **GAP** | fetch()+ReadableStream shipped but zero trace ID injection; CORS on Function URLs missing x-amzn-trace-id |
| Fanout silent failures | **GAP** | 5 error handlers in fanout.py with zero metric emission (not 2 as initially reported) |
| Warm invocation trace IDs | **DONE** | extract_trace_context() called per-invocation (FR-059/FR-092) |
| Canary completeness metric | **DONE** | completeness_ratio metric emitted with 0.95 threshold |
| Force flush timeout | **DONE** | safe_force_flush() with 2s timeout (FR-114) |

### Rev 2 Corrections

1. **ADOT scoped to SSE only** -- Analysis/Dashboard use Powertools + Active mode which auto-exports. Adding ADOT to 2GB Analysis image for zero gain is waste.
2. **CORS assumption was false** -- Function URL CORS for SSE and Dashboard missing x-amzn-trace-id. Now a hard prerequisite FR.
3. **EventSource-to-fetch already shipped** -- But incomplete: no trace ID generation, no header injection, misleading comments, test only checks response headers.
4. **Fanout has 5 silent paths, not 2** -- batch write, base update, label counts, conditional high, conditional low.
## User Scenarios & Testing *(mandatory)*

### User Story 1 - SSE Lambda Trace Visibility (Priority: P1)

An on-call engineer investigating a production incident involving the SSE streaming Lambda needs complete X-Ray traces including downstream service calls. The SSE Lambda has a dual-framework architecture: Powertools Tracer for the handler phase (auto-exported via Active mode) and OTel SDK for the streaming phase (exports to ADOT Extension on localhost:4318). Without ADOT in the container, streaming-phase spans silently fail to export.

Analysis and Dashboard Lambdas are **out of scope** -- they use Powertools exclusively with tracing_mode=Active.

**Why this priority**: SSE handles all real-time streaming. Its streaming phase is invisible without ADOT.

**Independent Test**: Deploy SSE Lambda with ADOT Extension. Establish SSE connection and verify streaming-phase OTel spans appear in X-Ray within 60s.

**Acceptance Scenarios**:

1. **Given** ADOT Extension in SSE container, **When** user connects to SSE, **Then** X-Ray shows both handler-phase (Powertools) and streaming-phase (OTel) spans in one trace.
2. **Given** ADOT Extension unavailable (crash/port unreachable), **When** user connects to SSE, **Then** Lambda succeeds with degraded tracing (streaming spans lost, handler traces unaffected).
3. **Given** ADOT Extension in container, **When** cold start occurs, **Then** Extension init adds no more than 500ms.

---

### User Story 2 - Frontend-to-Backend Trace Continuity (Priority: P2)

A platform engineer needs browser-to-Lambda traces. The frontend migrated to fetch()+ReadableStream (commit 886eccf) but **no trace ID injection was implemented**. Lambda Function URL CORS rejects X-Amzn-Trace-Id (not in allow_headers).

Trace path: Browser -> Next.js proxy (/api/sse/[...path]) -> Lambda Function URL. Proxy already forwards X-Amzn-Trace-Id if present. Gap: (a) browser never generates it, (b) CORS blocks it.

**Why this priority**: Last mile from browser to Lambda is invisible. Plumbing exists; only trace generation and CORS missing.

**Independent Test**: Load frontend, trigger SSE, verify via Playwright that outgoing request includes X-Amzn-Trace-Id.

**Acceptance Scenarios**:

1. **Given** user loads dashboard, **When** page initializes, **Then** trace context generated and attached to all fetch requests via X-Amzn-Trace-Id header.
2. **Given** SSE Function URL CORS, **When** preflight includes x-amzn-trace-id, **Then** response allows it and request proceeds.
3. **Given** active SSE connection drops, **When** auto-reconnection occurs, **Then** the same trace ID is reused (consistent session tracing) and previousTraceId from prior response is available in ConnectionInfo for correlation.
4. **Given** trace ID generation fails, **When** fetch made, **Then** request proceeds without header (fail-open).
5. **Given** proxy receives request without X-Amzn-Trace-Id, **When** forwarding, **Then** proxy generates fallback trace ID.

---

### User Story 3 - Fanout Silent Failure Observability (Priority: P3)

Fanout module has **5 error handlers** with zero metrics/X-Ray annotation:
- Batch write (~line 186-196): BatchWriteItem ClientError
- Base field update (~line 281-290): UpdateItem ClientError
- Label counts update (~line 302-312): UpdateItem ClientError
- Conditional high (~line 324-329): Swallows ConditionalCheckFailedException
- Conditional low (~line 341-346): Same

Other 4 modules (circuit_breaker, audit, notification, self_healing) already use the established pattern.

**Why this priority**: Silent data loss with no system indication. Consistency gap.

**Independent Test**: Inject DynamoDB failure, verify SilentFailure/Count metric emitted and X-Ray subsegment marked error.

**Acceptance Scenarios**:

1. **Given** batch write ClientError, **When** caught, **Then** SilentFailure/Count with FailurePath=fanout_batch_write and X-Ray error annotation.
2. **Given** base field update ClientError, **When** caught, **Then** SilentFailure/Count with FailurePath=fanout_base_update.
3. **Given** label counts update ClientError, **When** caught, **Then** SilentFailure/Count with FailurePath=fanout_label_update.
4. **Given** ConditionalCheckFailedException swallowed, **When** caught, **Then** ConditionalCheck/Count with FailurePath=fanout_conditional.
5. **Given** non-conditional ClientError in conditional handlers, **When** re-raised, **Then** SilentFailure/Count emitted before re-raise.
6. **Given** metric emission fails, **When** secondary exception caught, **Then** original error logged, no secondary throw.

---

### Edge Cases

- ADOT crashes mid-invocation: Lambda completes, handler traces unaffected.
- Frontend trace ID generation fails: fail-open, proceed without header.
- Metric emission fails in error handler: log original error, no secondary exception.
- ADOT slow cold start: OTel SDK non-blocking, short timeout.
- Pathological conditional contention (>100/min): ConditionalCheck/Count enables separate alarm.
- Malformed X-Amzn-Trace-Id in proxy: forward as-is, Lambda validates.

## Requirements *(mandatory)*

### Functional Requirements

**P1 -- SSE Lambda ADOT Extension**

- **FR-001**: SSE Lambda container image MUST include ADOT Lambda Extension for OTel SDK streaming-phase span export via localhost:4318.
- **FR-002**: ADOT Extension MUST be embedded via CI build step downloading Lambda Layer archive and copying extensions/ into container.
- **FR-003**: SSE Lambda MUST operate normally if ADOT Extension absent or crashes (graceful degradation in tracing.py).
- **FR-004**: ADOT collector MUST export to X-Ray. The default ADOT Collector Layer config exports to X-Ray and respects server-side sampling rules (no custom collector.yaml needed). Sampling rates (100% dev/preprod, graduated prod) are controlled by existing X-Ray sampling rules in Terraform, not by the collector config.
- **FR-005**: Analysis and Dashboard Dockerfiles MUST NOT include ADOT Extension. Code comment MUST document why (Powertools + Active mode auto-exports).

**P2 -- Frontend Trace Propagation**

- **FR-006**: Lambda Function URL CORS for SSE and Dashboard MUST include x-amzn-trace-id in allow_headers and expose_headers. PREREQUISITE for all other P2 work.
- **FR-007**: Frontend MUST generate X-Ray-format trace IDs (Root=1-timestamp-96bit_hex;Parent=64bit_hex;Sampled=1). Lightweight utility sufficient.
- **FR-008**: Frontend SSE fetch() calls MUST include X-Amzn-Trace-Id header via SSEConnection headers option. REST API client trace injection is deferred (custom headers trigger CORS preflight on every request; REST calls go through API Gateway which already has X-Ray tracing).
- **FR-009**: SSE connections MUST use a consistent trace ID for the lifetime of the connection (including auto-reconnects). The previousTraceId from response headers is captured by SSEConnection and available in ConnectionInfo for server-side correlation. Dynamic trace ID refresh on reconnect is deferred (requires SSEConnection architecture change).
- **FR-010**: If trace ID generation fails, request MUST proceed without header (fail-open).
- **FR-011**: Next.js proxy (/api/sse/[...path]/route.ts) MUST generate fallback trace ID if browser request lacks X-Amzn-Trace-Id.
- **FR-012**: Playwright test MUST verify outgoing REQUEST headers contain X-Amzn-Trace-Id (not just response). Misleading comments in use-sse.ts MUST be corrected.

**P3 -- Fanout Metric Emission**

- **FR-013**: Fanout batch write error handler MUST emit SilentFailure/Count with FailurePath=fanout_batch_write.
- **FR-014**: Fanout base field update error handler MUST emit SilentFailure/Count with FailurePath=fanout_base_update.
- **FR-015**: Fanout label counts update error handler MUST emit SilentFailure/Count with FailurePath=fanout_label_update.
- **FR-016**: Fanout conditional handlers MUST emit ConditionalCheck/Count with FailurePath=fanout_conditional when ConditionalCheckFailedException swallowed.
- **FR-017**: Fanout conditional handlers MUST emit SilentFailure/Count with FailurePath=fanout_conditional_unexpected for non-conditional ClientError.
- **FR-018**: All 5 error handlers MUST annotate X-Ray subsegment with error flag and exception, per established pattern.
- **FR-019**: Metric emission failures MUST be caught and logged without propagating secondary exceptions.

### Key Entities

- **ADOT Lambda Extension**: OTel sidecar for trace export. Only needed for OTel SDK Lambdas; Powertools + Active mode Lambdas do not need it.
- **Trace Context**: X-Ray-format identifier propagated across service boundaries for trace correlation.
- **SilentFailure/Count Metric**: CloudWatch metric for silent failures. Namespace: SentimentAnalyzer/Reliability.
- **ConditionalCheck/Count Metric**: New metric for DynamoDB optimistic locking contention. NOTE: This fires on the normal happy path (value is not a new high/low), so the baseline rate will be high (proportional to write volume). Useful for detecting sudden spikes in contention (concurrent writers) rather than as a failure indicator. Alarm threshold should be rate-of-change based, not absolute.

## Assumptions

- ADOT Lambda Layer downloadable in CI via existing deployer IAM role (may need lambda:GetLayerVersion).
- Next.js supports X-Ray trace ID generation via crypto.getRandomValues() without full RUM SDK.
- Fanout module tracer.provider.in_subsegment() pattern available for error annotation.
- Browser ReadableStream covers target browser matrix (modern browsers only).
- ADOT Extension adds ~200-500ms to SSE Lambda cold start (acceptable).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Canary completeness_ratio for SSE traces remains above 0.95 after ADOT deployment.
- **SC-002**: Browser-to-Lambda traces visible in X-Ray with frontend trace IDs as parent segments. Verified by corrected Playwright test.
- **SC-003**: Fanout DynamoDB failures produce SilentFailure/Count metric within 60s.
- **SC-004**: No Lambda invocation failures from ADOT unavailability.
- **SC-005**: SSE functionality unaffected by trace header injection (existing Playwright sanity tests pass).
- **SC-006**: ConditionalCheck/Count baseline established within 7 days. Alarm should use rate-of-change anomaly detection (not absolute threshold) since this metric fires on normal writes.
