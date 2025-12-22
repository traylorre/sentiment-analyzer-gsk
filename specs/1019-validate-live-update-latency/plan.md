# Implementation Plan: Validate Live Update Latency

**Branch**: `1019-validate-live-update-latency` | **Date**: 2024-12-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1019-validate-live-update-latency/spec.md`

## Summary

Validate that live sentiment updates reach the dashboard within 3 seconds of analysis completion (SC-003). This involves:
1. Adding `origin_timestamp` to SSE events for end-to-end latency measurement
2. Logging structured latency metrics to CloudWatch Logs
3. Providing CloudWatch Logs Insights queries for p95 calculation
4. Creating E2E test to validate the 3-second target
5. Documenting the latency breakdown in docs/performance-validation.md

## Technical Context

**Language/Version**: Python 3.13 (Lambda), JavaScript (browser client)
**Primary Dependencies**: Pydantic (models), structlog (logging), pytest-playwright (E2E)
**Storage**: CloudWatch Logs (metrics), DynamoDB (sentiment data)
**Testing**: pytest, pytest-playwright, CloudWatch Logs Insights
**Target Platform**: AWS Lambda (SSE streaming), Browser (dashboard client)
**Project Type**: Web application (backend Lambda + frontend dashboard)
**Performance Goals**: p95 end-to-end latency < 3 seconds
**Constraints**: Latency logging MUST NOT block event delivery
**Scale/Scope**: ~1000s of events/day, continuous monitoring

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Section 6: Structured logging | PASS | FR-003 requires JSON-structured latency logs |
| Section 6: CloudWatch/X-Ray tracing | PASS | Using CloudWatch Logs Insights for metrics |
| Section 7: Deterministic time handling | PASS | Using fixed timestamps in tests, freezegun where needed |
| Section 7: E2E tests in preprod | PASS | E2E test validates p95 against preprod |
| Amendment 1.5: ISO 8601 timestamps | PASS | All timestamps use ISO 8601 format |
| Amendment 1.6: Local SAST | PASS | ruff check before push |

## Project Structure

### Documentation (this feature)

```text
specs/1019-validate-live-update-latency/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── latency-metrics-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/sse_streaming/
├── models.py            # Add origin_timestamp to event models
├── stream.py            # Add latency logging
├── timeseries_models.py # Add origin_timestamp to bucket events
└── latency_logger.py    # NEW: Latency metric logger (non-blocking)

src/dashboard/
├── timeseries.js        # Add client-side latency calculation
└── app.js               # Expose latency metrics to window

docs/
└── performance-validation.md  # NEW: Latency breakdown documentation

tests/e2e/
└── test_live_update_latency.py  # NEW: E2E latency validation test
```

**Structure Decision**: Extends existing SSE streaming Lambda with latency instrumentation. Client-side changes add latency calculation to dashboard JavaScript.

## Phase 0: Research Summary

### RQ1: How to add origin_timestamp without breaking existing clients?

**Decision**: Add `origin_timestamp` field to event models as optional (default=now). Existing clients ignore unknown fields.

**Rationale**: Pydantic models are forward-compatible. The `timestamp` field already exists; `origin_timestamp` is the data creation time vs. `timestamp` which is when SSE event was generated.

**Alternatives Rejected**:
- Renaming `timestamp` to `origin_timestamp`: Breaking change for clients
- Sending separate timing event: Increases message count

### RQ2: How to log latency without blocking event delivery?

**Decision**: Use fire-and-forget async logging with structlog. Log entry is emitted immediately after event serialization but before network send.

**Rationale**: CloudWatch Logs are already used for Lambda logging. structlog JSON format enables Logs Insights queries. Logging is fast (~1ms) and doesn't block.

**Alternatives Rejected**:
- CloudWatch Metrics API: Adds latency, requires IAM permissions for PutMetric
- X-Ray segments: Already used for tracing but not for custom metrics

### RQ3: What CloudWatch Logs Insights query calculates percentiles?

**Decision**: Use `pctile()` aggregation function on `latency_ms` field:
```
fields @timestamp, latency_ms
| filter event_type = "bucket_update"
| stats pctile(latency_ms, 50) as p50, pctile(latency_ms, 90) as p90, pctile(latency_ms, 95) as p95, pctile(latency_ms, 99) as p99
```

**Rationale**: CloudWatch Logs Insights has native percentile support. No custom metric infrastructure needed.

### RQ4: How should client calculate receive latency?

**Decision**: Client calculates `Date.now() - Date.parse(origin_timestamp)` and optionally exposes via `window.lastLatencyMetrics`.

**Rationale**: Matches T064 pattern (window.lastSwitchMetrics). Requires NTP sync assumption documented in spec.

### RQ5: What components contribute to end-to-end latency?

**Decision**: Document 5 components in breakdown:
1. Analysis Lambda processing time (~50-200ms)
2. SNS publish latency (~10-50ms)
3. SQS delivery to SSE Lambda (~50-100ms)
4. SSE Lambda event serialization (~5-10ms)
5. Network delivery to client (~50-500ms variable)

**Rationale**: Understanding each component enables targeted optimization. Total budget: <3s for p95.

## Phase 1: Design Artifacts

### Data Model

See [data-model.md](./data-model.md) for:
- Extended SSE event models with `origin_timestamp`
- LatencyMetric log entry schema
- Client-side latency metrics object

### Contracts

See [contracts/latency-metrics-api.yaml](./contracts/latency-metrics-api.yaml) for:
- CloudWatch Logs Insights query specification
- Log entry JSON schema
- Expected percentile output format

### Quickstart

See [quickstart.md](./quickstart.md) for:
- How to run latency validation locally
- How to query CloudWatch for latency metrics
- Troubleshooting high latency

## Complexity Tracking

No constitution violations. No complexity justification needed.

## Dependencies

- Parent feature: `specs/1009-realtime-multi-resolution` (defines SC-003)
- Related feature: `specs/1018-validate-resolution-switching-perf` (T064 pattern)
- Existing code: `src/lambdas/sse_streaming/` (to modify)
- Existing docs: `docs/` (to extend)
