# High-Level X-Ray Remediation Checklist

**Created:** 2026-02-14
**Status:** In Progress
**Branch:** `1219-xray-exclusive-tracing`
**Spec:** `specs/1219-xray-exclusive-tracing/spec.md`
**Audit:** `docs/audit/2026-02-13-playwright-coverage-observability-blind-spots.md` (Section 9.1)

---

## Executive Summary

The X-Ray tracing infrastructure is **partially implemented but fragmented**:
- All 6 Lambda functions have Active tracing enabled in Terraform
- API Gateway and CloudWatch RUM have X-Ray enabled
- Dashboard Lambda has 20+ subsegments (best instrumented)
- **BUT:** Metrics Lambda has zero SDK integration
- **BUT:** SSE Streaming Lambda has only 1 subsegment (status endpoint)
- **BUT:** 7 silent failure paths have no X-Ray subsegments
- **BUT:** Custom logging (latency_logger, cache_logger) duplicates what X-Ray should provide
- **BUT:** Custom correlation IDs create a parallel tracing universe
- **BUT:** Frontend does not propagate `X-Amzn-Trace-Id` headers
- **BUT:** 4 of 6 Lambda roles lack explicit X-Ray IAM permissions

**Round 2 emergent findings:**
- **BUT:** SSE Lambda uses `RESPONSE_STREAM` invoke mode — X-Ray segment closes before streaming begins; all streaming subsegments orphaned
- **BUT:** `asyncio.new_event_loop()` in async-to-sync bridge loses X-Ray context; auto-patched boto3 calls have no parent segment
- **BUT:** SendGrid SDK uses `urllib` (NOT httpx) — NOT auto-patched by X-Ray SDK; email sends invisible
- **BUT:** 57 raw `@xray_recorder.capture` decorators do NOT auto-capture exceptions (only Powertools Tracer does)
- **BUT:** Dashboard Lambda double-patches boto3 (explicit `patch_all()` + Tracer `auto_patch=True`)

**Round 3 emergent findings (3 BLOCKERS + 4 high risks):**
- **BLOCKER:** ~~Round 2 proposed "Two-Phase Architecture" with `begin_segment()`~~ — `begin_segment()` is a **no-op in Lambda**. `LambdaContext.put_segment()` silently discards segments. `FacadeSegment` is immutable. The entire SSE streaming architecture must use ADOT Lambda Extension instead.
- **BLOCKER:** Powertools `@tracer.capture_method` **silently mishandles async generators** — `inspect.isasyncgenfunction()` is never called; falls through to sync wrapper capturing near-zero time
- **BLOCKER:** `EventSource` API **does not support custom HTTP headers** (WHATWG spec) — frontend SSE must migrate to `fetch()` + `ReadableStream` for trace propagation
- **HIGH:** Clients can force 100% sampling via `Sampled=1` header — cost amplification at $5/million traces
- **HIGH:** X-Ray has no "guaranteed capture on error" mode — sampling decided before outcome known
- **HIGH:** X-Ray silently drops data at 2,600 segments/sec region limit — no alert on loss
- **MEDIUM:** X-Ray SDK `AsyncContext` loses context across event loop boundaries — must use default `threading.local()`

**Round 4 emergent findings (7 blind spots from audit gap analysis):**
- **HIGH:** 2 Lambda functions (SSE, Metrics) have ZERO CloudWatch error alarms — operators never alerted to failures that X-Ray traces could diagnose
- **HIGH:** 7 custom metrics emitted without alarms (StuckItems, ConnectionAcquireFailures, EventLatencyMs, MetricsLambdaErrors, HighLatencyAlert, PollDurationMs, AnalysisErrors)
- **HIGH:** X-Ray Groups only operate on already-sampled traces — at <100% sampling, CloudWatch metrics required for 100% error alarming. "X-Ray exclusive" applies to TRACING, not ALARMING (FR-039).
- **HIGH:** CloudWatch `put_metric_data` failure makes `treat_missing_data=notBreaching` alarms false-green — canary must verify CloudWatch emission health via separate IAM role and out-of-band alerting
- **MEDIUM:** ADOT auto-instrumentation (`AWS_LAMBDA_EXEC_WRAPPER`) conflicts with Powertools Tracer — must use sidecar-only mode (FR-046)
- **MEDIUM:** X-Ray has no native span links — SSE reconnection traces need annotation-based correlation (`session_id`, `previous_trace_id`) (FR-048)
- **LOW:** CloudFront removed from architecture (Features 1203-1207) — browser trace propagation not affected

This results in:
- Operators must query X-Ray AND CloudWatch Logs AND custom dashboards to debug issues
- Silent failures (circuit breaker, audit trail, fanout) invisible to tracing
- SSE streaming — the most latency-sensitive path — has near-zero trace visibility, compounded by RESPONSE_STREAM segment lifecycle
- Browser-to-backend traces are disconnected (RUM traces don't link to Lambda traces)
- No mechanism to detect if X-Ray itself is down or silently losing data
- Exception errors not captured as subsegment faults in 5 of 6 Lambdas (FR-005 unachievable with raw xray_recorder)
- No sampling strategy — errors can be untraced; no cost guard
- Frontend EventSource cannot propagate trace headers
- **(R4)** 2 Lambda functions have zero error alarms — SSE and Metrics failures undetectable by operators
- **(R4)** 7 custom metrics silently emitted with no alarm — degradation invisible
- **(R4)** CloudWatch metric emission failure creates system-wide false-green on `notBreaching` alarms
- **(R4)** SSE reconnection produces disconnected traces with no correlation mechanism

---

## Work Order

| # | Task | File | Status | Priority | Spec FRs |
|---|------|------|--------|----------|----------|
| 1 | Fix IAM permissions for X-Ray | [fix-iam-permissions.md](./fix-iam-permissions.md) | [ ] TODO | P0 | FR-017 |
| 2 | Fix Metrics Lambda X-Ray instrumentation | [fix-metrics-lambda-xray.md](./fix-metrics-lambda-xray.md) | [ ] TODO | P0 | FR-003, FR-004 |
| 3 | Verify SNS cross-Lambda trace propagation | [fix-sns-trace-verification.md](./fix-sns-trace-verification.md) | [ ] TODO | P1 | FR-013 |
| 4 | Fix silent failure path subsegments | [fix-silent-failure-subsegments.md](./fix-silent-failure-subsegments.md) | [ ] TODO | P1 | FR-002, FR-005, **FR-043** |
| 5 | **Fix SSE Streaming Lambda tracing (ADOT)** | [fix-sse-subsegments.md](./fix-sse-subsegments.md) | [ ] TODO | P1 | FR-001, FR-025, FR-026, FR-027, FR-031, FR-037, **FR-046, FR-047** |
| 6 | Replace latency_logger with X-Ray annotations | [fix-sse-latency-xray.md](./fix-sse-latency-xray.md) | [ ] TODO | P2 | FR-006, FR-022 |
| 7 | Replace cache_logger with X-Ray annotations | [fix-sse-cache-xray.md](./fix-sse-cache-xray.md) | [ ] TODO | P2 | FR-007, FR-023 |
| 8 | Add SSE connection and polling annotations | [fix-sse-annotations.md](./fix-sse-annotations.md) | [ ] TODO | P2 | FR-008, FR-009 |
| 9 | Consolidate correlation IDs onto X-Ray trace IDs | [fix-correlation-id-consolidation.md](./fix-correlation-id-consolidation.md) | [ ] TODO | P3 | FR-010, FR-011, FR-012, FR-024 |
| 10 | Add frontend trace header propagation (CORS) | [fix-frontend-trace-headers.md](./fix-frontend-trace-headers.md) | [ ] TODO | P2 | FR-014, FR-015, FR-016 |
| 11 | Implement observability canary (X-Ray + CloudWatch health) | [fix-xray-canary.md](./fix-xray-canary.md) | [ ] TODO | P3 | FR-019, FR-020, FR-021, FR-036, **FR-049, FR-050, FR-051** |
| 12 | Audit downstream consumers of removed systems | [fix-downstream-consumer-audit.md](./fix-downstream-consumer-audit.md) | [ ] TODO | P3 | FR-018, edge cases |
| 13 | Add explicit SendGrid X-Ray subsegment | [fix-sendgrid-explicit-subsegment.md](./fix-sendgrid-explicit-subsegment.md) | [ ] TODO | P1 | FR-028 |
| 14 | Standardize on Powertools Tracer (non-streaming Lambdas) | [fix-tracer-standardization.md](./fix-tracer-standardization.md) | [ ] TODO | P0 | FR-029, FR-030 |
| 15 | **Migrate frontend SSE to fetch()+ReadableStream** | [fix-sse-client-fetch-migration.md](./fix-sse-client-fetch-migration.md) | [ ] TODO | P2 | FR-032, FR-033, **FR-048** |
| 16 | **Configure sampling strategy and cost guard** | [fix-sampling-and-cost.md](./fix-sampling-and-cost.md) | [ ] TODO | P1 | FR-034, FR-035, FR-038, **FR-039** |
| 17 | **Add CloudWatch alarm coverage** | [fix-alarm-coverage.md](./fix-alarm-coverage.md) | [ ] TODO | P1 | **FR-040, FR-041, FR-042, FR-044, FR-045** |

**Rationale for order:**
1. **IAM first** — Without permissions, X-Ray SDK calls fail at runtime
2. **Tracer standardization second** (P0, non-streaming Lambdas) — All subsequent non-SSE tasks must use Powertools Tracer; eliminates double-patching; enables automatic exception capture (FR-029/030). **Round 3 update:** SSE Lambda excluded — uses ADOT instead.
3. **Metrics Lambda third** — The monitor-of-monitors is completely dark; fix the most dangerous gap (now uses Powertools Tracer from task 14)
4. **SNS verification fourth** — Confirm cross-Lambda traces link before adding subsegments
5. **SSE ADOT subsegments fifth** — **(Round 3: COMPLETE REWRITE)** Foundation for tasks 6-8. Uses ADOT Lambda Extension for independent lifecycle tracing during RESPONSE_STREAM streaming. Includes async generator safety (FR-031) and AsyncContext prohibition (FR-037).
6. **Silent failures sixth** — Highest operator impact (P1 stories); 7 paths across shared code (now with Powertools auto-exception capture)
7. **Latency → X-Ray seventh** — Depends on SSE ADOT subsegments existing (task 5)
8. **Cache → X-Ray eighth** — Same dependency on task 5
9. **SSE annotations ninth** — Enriches ADOT spans from task 5
10. **Sampling strategy tenth** **(Round 3: NEW)** — Configure per-environment sampling, server-side defense, X-Ray Groups, cost alarms. Independent of instrumentation but should be in place before production deployment.
11. **Correlation IDs eleventh** — Cross-cutting change; safer after subsegments are stable
12. **Frontend headers twelfth** — CORS changes independent of backend
13. **SSE client migration thirteenth** **(Round 3: NEW)** — Replace EventSource with fetch()+ReadableStream for trace header propagation. Independent of backend. Must implement reconnection logic.
14. **SendGrid subsegment fourteenth** — Explicit instrumentation for urllib-based SDK
15. **Canary fifteenth** — Requires all other X-Ray instrumentation to exist first. **(Round 3: ENHANCED)** Now includes data loss detection (FR-036).
16. **Downstream audit last** — Cleanup after all removals (tasks 6, 7, 9) are complete
17. **Alarm coverage seventeenth** **(Round 4: NEW)** — Add missing CloudWatch alarms for SSE/Metrics Lambdas, unalarmed custom metrics, dashboard widget completeness, and `treat_missing_data` alignment. Independent of X-Ray instrumentation — can run in parallel with tracing tasks.

---

## Component Coverage Map

| Component | Current Subsegments | After Fix | Task |
|-----------|-------------------|-----------|------|
| Dashboard Lambda | 20+ (Powertools + xray_recorder) | Powertools only (fix double-patching) | #14 |
| Ingestion Lambda | 6 explicit + auto-patched | Powertools Tracer + 5 silent failure paths | #14, #4 |
| Analysis Lambda | 2 explicit + auto-patched | Powertools Tracer (trace linking via #3) | #14, #3 |
| Notification Lambda | 3 explicit + auto-patched | Powertools Tracer + 1 silent failure + SendGrid subsegment | #14, #4, #13 |
| **Metrics Lambda** | **0 (none)** | **Powertools Tracer + auto-patching** | **#14, #2** |
| **SSE Streaming Lambda** | **1 (stream_status only)** | **ADOT OTel spans for streaming + Powertools for handler** | **#5, #6, #7, #8** |
| Frontend API client | No trace headers | X-Amzn-Trace-Id on all fetch() requests | #10 |
| Frontend SSE client | EventSource (no headers) | **fetch()+ReadableStream with X-Amzn-Trace-Id** | **#15** |
| Custom latency_logger | Custom structured logs | **Deleted** (replaced by X-Ray) | #6 |
| Custom cache_logger | Custom structured logs | **Deleted** (replaced by X-Ray) | #7 |
| Custom correlation IDs | `{source}-{request_id}` | **Deleted** (replaced by X-Ray trace ID) | #9 |
| SendGrid email sends | **Invisible** (urllib not auto-patched) | Explicit X-Ray subsegment | #13 |
| X-Ray canary | Does not exist | New Lambda canary **with data loss detection** | #11 |
| Raw xray_recorder (57 decorators) | No exception auto-capture | **Replaced** with Powertools Tracer (non-streaming) | #14 |
| X-Ray sampling | Default (1/s + 5%) | **Per-environment rules + error Groups + cost guard** | **#16** |
| ADOT Lambda Extension | Not installed | **SSE Lambda Extension for streaming traces** | **#5** |
| **(R4)** CloudWatch Lambda alarms | SSE + Metrics: zero error alarms; 4 Lambdas: no latency alarm | **6/6 Lambdas with error + latency alarms** | **#17** |
| **(R4)** Custom metric alarms | 7 metrics emitted, zero alarms | **All 7 metrics alarmed** | **#17** |
| **(R4)** Silent failure CloudWatch metrics | Zero (X-Ray only) | **Dual instrumentation: X-Ray subsegments + CloudWatch metrics** | **#4** |
| **(R4)** Dashboard alarm widget | Shows 6 of 30+ alarms | **ALL alarms displayed** | **#17** |
| **(R4)** Canary CloudWatch verification | X-Ray health only | **X-Ray + CloudWatch emission health, separate IAM, out-of-band alerting** | **#11** |
| **(R4)** SSE reconnection correlation | No trace linking | **session_id + previous_trace_id annotations** | **#15** |
| **(R5)** OTel-X-Ray trace bridging | Not configured | **AwsXRayLambdaPropagator + AwsXRayIdGenerator + OTLP endpoint** | **#5** |
| **(R5)** OTel span lifecycle | No force_flush() | **force_flush() in generator finally block; parentbased_always_on sampler** | **#5** |
| **(R5)** Segment document size | No bounds checking | **Metadata truncation: 2048 char errors, no response bodies, 10-frame stacks** | **#4, #5** |
| **(R6)** Per-Invocation OTel Context Extraction | SSE Lambda: module-level extraction | **Extract trace context inside handler, not module level (FR-059, SC-026)** | **#5** |
| **(R6)** SSE Lambda auto_patch=False | SSE Lambda: auto_patch=True (Powertools default) | **Disable Powertools global boto3 patching to prevent dual-emission (FR-060)** | **#5** |
| **(R6)** Alarm Threshold Calibration | All Lambdas: thresholds not calibrated | **Review and align existing alarm thresholds to 80-90% standard (FR-061)** | **#17** |

---

## Constraint: Fail-Fast, No Fallbacks

Per FR-018 and project constitution: X-Ray instrumentation errors MUST propagate unhandled. **No try/catch around X-Ray SDK calls.** This applies to ALL tasks. If X-Ray SDK fails, the Lambda fails. This is by design — a broken tracing system should be loud, not silent.

The sole exception is the X-Ray canary (task #11), which by definition must survive X-Ray failures to report them.

---

## Success Criteria

### Trace Coverage
- [ ] 6/6 Lambda functions have auto-instrumented subsegments (SC-003)
- [ ] 7/7 silent failure paths have error-annotated subsegments (SC-004)
- [ ] SSE streaming has traced spans for all operations via ADOT Extension (SC-005, SC-010)
- [ ] Cross-Lambda SNS traces linked under single trace ID (SC-008)
- [ ] SendGrid email sends visible as explicit subsegments (SC-011)

### System Consolidation
- [ ] latency_logger.py deleted with all call sites (SC-009)
- [ ] cache_logger.py deleted with all call sites (SC-009)
- [ ] get_correlation_id() and generate_correlation_id() removed (SC-006)
- [ ] Frontend propagates X-Amzn-Trace-Id headers via fetch()+ReadableStream (SC-001, SC-015)
- [ ] X-Ray canary detects tracing failures AND data loss within 2 intervals (SC-007, SC-014)
- [ ] All non-streaming Lambdas use Powertools Tracer — zero raw xray_recorder.capture decorators (SC-012)
- [ ] SSE Lambda uses ADOT Extension — zero `begin_segment()` calls, zero orphaned subsegments (SC-010)
- [ ] Zero double-patching — each Lambda has exactly one patching mechanism (SC-012)

### Sampling & Cost
- [ ] 100% sampling in dev/preprod; configurable in prod (FR-034)
- [ ] X-Ray Group with error/fault filter generates CloudWatch metrics (SC-013)
- [ ] Server-side sampling rules override client Sampled=1 (FR-035)
- [ ] X-Ray billing alarms at $10/$25/$50 thresholds (SC-016)

### Operational Alarm Coverage (Round 4)
- [ ] 6/6 Lambda functions have CloudWatch error + latency alarms (SC-017)
- [ ] All 7 unalarmed custom metrics have CloudWatch alarms (SC-018)
- [ ] 7/7 silent failure paths emit both X-Ray subsegments AND CloudWatch metrics (SC-019)
- [ ] SSE reconnection traces correlated via session_id annotation (SC-020)
- [ ] Canary detects X-Ray AND CloudWatch metric emission failures (SC-021)
- [ ] Dashboard alarm widget shows ALL alarms (SC-022)
- [ ] OTel streaming-phase spans share same trace ID as Lambda X-Ray facade segment (SC-023)
- [ ] force_flush() called before execution environment freeze — zero stale spans (SC-024)
- [ ] All metadata payloads bounded — zero 64KB document rejections (SC-025)
- [ ] Warm invocation trace ID correctness (SC-026)

### Operator Experience
- [ ] Single-pane tracing: browser → API Gateway → Lambda → DynamoDB (SC-001)
- [ ] Filter by error/fault to find silent failures (SC-002)
- [ ] Filter by latency/cache annotations on SSE traces (SC-005)
- [ ] Exceptions auto-captured as subsegment errors in all Lambdas (FR-029)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| X-Ray SDK breaks Lambda on import error | Low | High | Test in dev first; SDK is stable |
| Annotation limit exceeded (50/subsegment) | Low | Medium | Current design uses <15; documented in edge cases |
| Frontend CORS change breaks existing requests | Medium | High | Add header to allowlist; don't remove existing |
| Removing latency_logger breaks Log Insights queries | Medium | Medium | Task #12 audits downstream consumers first |
| SNS trace propagation doesn't work with current SDK | Low | Medium | Task #3 verifies before building on assumption |
| X-Ray canary false positives during cold start | Medium | Low | Require 2 consecutive failures before alarming |
| ~~RESPONSE_STREAM orphans streaming subsegments~~ | ~~HIGH~~ | ~~HIGH~~ | ~~Two-Phase Architecture~~ **INVALIDATED** → ADOT Extension (Task 5) |
| ~~asyncio.new_event_loop() loses X-Ray context~~ | ~~HIGH~~ | ~~HIGH~~ | threading.local() default propagates correctly; **prohibit AsyncContext** (FR-037) |
| SendGrid urllib calls invisible to X-Ray | Medium | High | Explicit subsegment wrapping SendGrid API call (Task 13) |
| ~~57 xray_recorder decorators don't capture exceptions~~ | ~~High~~ | ~~High~~ | Standardize on Powertools Tracer for non-streaming (Task 14) |
| Dashboard Lambda double-patches boto3 | Low | Medium | Remove explicit patch_all(), keep Tracer auto_patch (Task 14) |
| **(R3)** `begin_segment()` is no-op in Lambda | **CONFIRMED** | **BLOCKER** | Use ADOT Lambda Extension for SSE streaming (Task 5) |
| **(R3)** `@tracer.capture_method` breaks async generators | **CONFIRMED** | **HIGH** | Prohibit decorator on async generators; use manual spans (FR-031) |
| **(R3)** EventSource cannot carry custom headers | **CONFIRMED** | **HIGH** | Migrate to fetch()+ReadableStream (Task 15) |
| **(R3)** Client forces 100% sampling via Sampled=1 | Medium | High | Server-side sampling rules override client (FR-035, Task 16) |
| **(R3)** Errors lost to sampling | Medium | High | 100% sampling + X-Ray Groups for error metrics (FR-034, Task 16) |
| **(R3)** X-Ray silently drops data at throughput limit | Low | High | Canary tracks submitted-vs-retrieved ratio (FR-036, Task 11) |
| **(R3)** ADOT Extension adds cold start overhead | Medium | Low | 50-200ms concurrent with Lambda INIT; acceptable for 15s streaming |
| **(R3)** EventSource→fetch() migration loses auto-reconnect | Medium | Medium | Implement reconnection logic with backoff+jitter (FR-033, Task 15) |
| **(R4)** SSE/Metrics Lambda failures undetected (zero alarms) | **CONFIRMED** | **HIGH** | Add CloudWatch error + latency alarms (FR-040/041, Task 17) |
| **(R4)** 7 custom metrics emitted without alarms | **CONFIRMED** | **HIGH** | Add CloudWatch alarms on all 7 metrics (FR-042, Task 17) |
| **(R4)** X-Ray Groups miss unsampled errors | **CONFIRMED** | **HIGH** | CloudWatch Lambda Errors metric captures 100%; dual instrumentation for silent failures (FR-043, Task 4) |
| **(R4)** CloudWatch `put_metric_data` failure → false-green alarms | **CONFIRMED** | **CRITICAL** | Canary verifies CloudWatch emission; separate IAM role; out-of-band alert (FR-049/050/051, Task 11) |
| **(R4)** ADOT auto-instrumentation conflicts with Powertools | Medium | High | MUST NOT set `AWS_LAMBDA_EXEC_WRAPPER`; sidecar-only mode (FR-046, Task 5) |
| **(R4)** OTel service.name ≠ POWERTOOLS_SERVICE_NAME | Medium | Medium | Names must match for unified service map (FR-047, Task 5) |
| **(R4)** SSE reconnection traces disconnected | Medium | Medium | Annotation-based correlation: session_id + previous_trace_id (FR-048, Task 15) |
| **(R4)** Dashboard alarm widget shows 6 of 30+ alarms | **CONFIRMED** | **MEDIUM** | Widget must display ALL alarms (FR-044, Task 17) |
| **(R5)** OTel spans disconnected from Lambda X-Ray trace | **CONFIRMED** | **BLOCKER** | AwsXRayLambdaPropagator reads _X_AMZN_TRACE_ID (FR-052, Task 5) |
| **(R5)** RandomIdGenerator produces invalid X-Ray timestamps | **CONFIRMED** | **HIGH** | AwsXRayIdGenerator embeds unix epoch (FR-053, Task 5) |
| **(R5)** Spans lost to execution environment freeze | **CONFIRMED** | **HIGH** | force_flush() in generator finally block (FR-055, Task 5) |
| **(R5)** 64KB segment document silently rejected | Medium | HIGH | Metadata truncation guard (FR-058, Tasks 4/5) |
| **(R5)** Orphaned OTel spans from unsampled invocations | Medium | Medium | parentbased_always_on sampler (FR-056, Task 5) |
| **(R6)** Warm invocation stale trace context | **CONFIRMED** | **HIGH** | Module-level extraction links all warm invocations to first trace; FR-059 mandates per-invocation extraction (Task 5) |
| **(R6)** Powertools auto-patching dual-emission | **CONFIRMED** | **HIGH** | auto_patch=True creates X-Ray + OTel duplicates during streaming; FR-060 mandates auto_patch=False (Task 5) |
| **(R6)** Existing alarm thresholds too generous | **CONFIRMED** | **MEDIUM** | analysis_latency_high at 42% of timeout; FR-061 mandates recalibration (Task 17) |

---

## References

- Spec: `specs/1219-xray-exclusive-tracing/spec.md`
- Audit: `docs/audit/2026-02-13-playwright-coverage-observability-blind-spots.md`
- Checklist: `specs/1219-xray-exclusive-tracing/checklists/requirements.md`
- AWS X-Ray SDK: `aws-xray-sdk` (currently v2.15.0 in requirements.txt)
- AWS Lambda Powertools: `aws-lambda-powertools` (currently v3.23.0, Dashboard Lambda only → ALL non-streaming Lambdas after Task 14)
- ADOT Lambda Extension: `aws-otel-python-instrumentation` (SSE Lambda only, Task 5)
- X-Ray SDK lambda_launcher.py: `LambdaContext.put_segment()` is no-op (source: `aws_xray_sdk/core/lambda_launcher.py:55-59`)
- Powertools Tracer async gap: `inspect.isasyncgenfunction()` never called (source: `aws_lambda_powertools/tracing/tracer.py`)
- EventSource limitation: WHATWG HTML Living Standard, Section 9.2
- OTel AWS X-Ray Propagator: `opentelemetry-propagator-aws-xray` (SSE Lambda only, Task 5)
- OTel AWS SDK Extension: `opentelemetry-sdk-extension-aws` (SSE Lambda only, Task 5)
- OTel OTLP HTTP Exporter: `opentelemetry-exporter-otlp-proto-http` (SSE Lambda only, Task 5)

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-02-14 | Document created from spec 1219 and audit findings |
| 2026-02-14 | Round 2 updates: Added tasks 13-14; rewrote task 5 for RESPONSE_STREAM Two-Phase Architecture; updated tasks 2,4,5,6,7 for Powertools Tracer dependency; added 5 new risks; updated component coverage map; added SC-010/011/012 |
| 2026-02-20 | **Round 3 updates:** 3 BLOCKERS invalidated Round 2 architecture. Task 5 REWRITTEN for ADOT Lambda Extension (begin_segment is no-op). Task 14 scoped to non-streaming Lambdas. Added tasks 15-16 (SSE client fetch migration, sampling/cost). Task 11 enhanced with data loss detection. Updated all SSE fix specs for ADOT references. Added FR-031 (async generator safety), FR-032-033 (fetch SSE client), FR-034-035 (sampling), FR-036 (data integrity), FR-037 (AsyncContext prohibition), FR-038 (cost guard). Total: 16 tasks, 38 FRs, 16 SCs. |
| 2026-02-21 | **Round 4 updates:** 7 blind spots from audit gap analysis. Added task 17 (alarm coverage). Updated tasks 4, 5, 11, 15, 16 with new FRs. Task 4 now includes dual instrumentation (X-Ray + CloudWatch metrics). Task 5 adds ADOT coexistence constraints (no auto-instrumentation, matching service names). Task 11 expanded to unified meta-observability canary (X-Ray + CloudWatch emission health, separate IAM role, out-of-band alerting). Task 15 adds SSE reconnection trace correlation annotations. Task 16 adds scope clarification (FR-039: X-Ray exclusive for TRACING, not ALARMING). Added FR-039 through FR-051, SC-017 through SC-022. Total: 17 tasks, 51 FRs, 22 SCs. |
| 2026-02-21 | **Round 5 updates:** 7 ADOT architecture blind spots found (1 BLOCKER). OTel-to-X-Ray trace context bridging requires explicit `AwsXRayLambdaPropagator` + `AwsXRayIdGenerator` + OTLP endpoint configuration — without these, streaming-phase spans are disconnected. Added `force_flush()` requirement for generator `finally` block. Added 64KB segment document size guard. Updated Task 5 dependencies. Added FR-052 through FR-058, SC-023 through SC-025. Total: 17 tasks, 58 FRs, 25 SCs. |
| 2026-02-21 | **Round 6 updates:** Deep blind spot analysis. Identified warm invocation trace context staleness (FR-059), Powertools auto-patching dual-emission (FR-060), and existing alarm threshold gap (FR-061). Added SC-026 for warm invocation verification. 5 new edge cases, 4 new assumptions. Totals: 61 FRs, 26 SCs, 34 edge cases, 26 assumptions. |
