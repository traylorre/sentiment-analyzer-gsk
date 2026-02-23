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

**Round 7 emergent findings (ADOT operational lifecycle deep-dive):**
- **HIGH:** OTel Python SDK `BatchSpanProcessor` silently drops all export failures (`except Exception`) — `force_flush()` returns `True` even on failure. No fail-fast mode available by OTel specification design. Detection relies solely on canary (FR-019/FR-036).
- **HIGH:** `TracerProvider` created per-invocation leaks daemon threads (~1MB each) — FR-059 per-invocation requirement applies ONLY to `propagate.extract()`, not infrastructure objects. Module-level singleton is mandatory.
- **HIGH:** Two ADOT layer types: collector-only (`aws-otel-collector-*`, ~35MB) vs Python SDK (`aws-otel-python-*`, ~80MB). Sidecar mode MUST use collector-only to avoid ~45MB waste and auto-instrumentation activation risk.
- **MEDIUM:** Layer ARN not version-pinned — unpinned layers silently introduce breaking collector changes on `terraform apply`
- **MEDIUM:** Non-standard OTel span attributes become X-Ray metadata (non-indexed, invisible in console). Must use `db.system`, `rpc.service`, `exception.type` semantic conventions.
- **LOW:** `OTEL_PROPAGATORS` env var creates misleading configuration when `set_global_textmap()` overwrites it

**Round 8 emergent findings (container-based deployment blind spot — 1 BLOCKER):**
- **BLOCKER:** SSE Lambda is **container-based** (ECR image with `python:3.13-slim` + custom bootstrap) — Lambda container images CANNOT use Lambda Layers. Round 7's FR-062 "collector-only layer" and FR-063 "version-pinned layer ARN" are **INVALID**. ADOT must be embedded in Docker image via multi-stage build (`COPY --from=adot /opt/extensions/ /opt/extensions/`). FR-062/FR-063 REWRITTEN, FR-069/FR-070 added.
- **HIGH:** OTel `AwsLambdaResourceDetector` does NOT set `service.name` — defaults to `unknown_service`, breaking X-Ray service map. `OTEL_SERVICE_NAME` env var is mandatory (FR-071).
- **HIGH:** `AwsLambdaResourceDetector` not in TracerProvider configuration — missing `cloud.provider`, `cloud.region`, `faas.name` on all spans (FR-072).
- **MEDIUM:** `BatchSpanProcessor` defaults inappropriate for Lambda — 5s delay, 2048 queue oversized (FR-073).

**Round 9 emergent findings (four-domain deep research — 2 HIGH, 7 MEDIUM):**
- **HIGH:** ADOT Extension has KNOWN ~30% span drop rate (aws-otel-lambda#886) — two-hop flush architecture: SDK→Extension (reliable) then Extension→X-Ray (race condition). Decouple processor mitigates. FR-074/FR-075 added.
- **HIGH:** Canary FR-049 does not classify `put_metric_data` errors — IAM revocation silently retried instead of immediately escalated. FR-079 adds error taxonomy with differential handling.
- **MEDIUM:** `BotocoreInstrumentor` not explicitly prohibited on SSE Lambda — FR-076 prohibits it alongside FR-060's `auto_patch=False`
- **MEDIUM:** `TracerProvider(shutdown_on_exit=True)` default causes atexit race on environment recycling — FR-077 requires `shutdown_on_exit=False`
- **MEDIUM:** X-Ray trace propagation delay non-deterministic — FR-078 adds retry-with-backoff (30s then 60s) to canary
- **MEDIUM:** FR-033 assumes server-side Last-Event-ID support — FR-081 requires server check or fallback header
- **MEDIUM:** CORS ExposeHeaders missing `x-amzn-trace-id` — FR-082 mandates it for FR-048 trace correlation
- **MEDIUM:** BSP default is 5000ms, not 200ms — FR-084 corrects Round 5 assumption; FR-073 override unaffected
- **LOW:** Secondary out-of-band alerting channel SHOULD be supported (FR-080)

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
- **(R7)** OTel export failures are SILENT BY DESIGN — force_flush() returns success even when ADOT Extension is down; canary is sole detection mechanism
- **(R7)** TracerProvider lifecycle mismanagement causes OOM on warm execution environments via daemon thread leak
- **(R7)** Wrong ADOT layer type (SDK vs collector-only) wastes 45MB and risks auto-instrumentation activation
- **(R8)** ADOT deployment via Lambda Layers is IMPOSSIBLE for container-based SSE Lambda — requires Dockerfile modification and ECR image rebuild
- **(R8)** SSE Lambda appears as `unknown_service` in X-Ray service map without explicit `OTEL_SERVICE_NAME` environment variable
- **(R9)** ADOT Extension→X-Ray export has known race condition; decouple processor is mitigation, not guarantee; canary provides aggregate detection
- **(R9)** Canary treats all put_metric_data failures uniformly; IAM revocation detection delayed by retry cycles
- **(R9)** Client-side Last-Event-ID propagation hollow without server-side support
- **(R9)** CORS ExposeHeaders missing for trace header reading — FR-048 reconnection correlation blocked

---

## Work Order

| # | Task | File | Status | Priority | Spec FRs |
|---|------|------|--------|----------|----------|
| 1 | Fix IAM permissions for X-Ray | [fix-iam-permissions.md](./fix-iam-permissions.md) | [ ] TODO | P0 | FR-017 |
| 2 | Fix Metrics Lambda X-Ray instrumentation | [fix-metrics-lambda-xray.md](./fix-metrics-lambda-xray.md) | [ ] TODO | P0 | FR-003, FR-004 |
| 3 | Verify SNS cross-Lambda trace propagation | [fix-sns-trace-verification.md](./fix-sns-trace-verification.md) | [ ] TODO | P1 | FR-013 |
| 4 | Fix silent failure path subsegments | [fix-silent-failure-subsegments.md](./fix-silent-failure-subsegments.md) | [ ] TODO | P1 | FR-002, FR-005, **FR-043** |
| 5 | **Fix SSE Streaming Lambda tracing (ADOT)** | [fix-sse-subsegments.md](./fix-sse-subsegments.md) | [ ] TODO | P1 | FR-001, FR-025, FR-026, FR-027, FR-031, FR-037, FR-046, FR-047, **FR-052, FR-053, FR-054, FR-055, FR-056, FR-059, FR-060, FR-062, FR-063, FR-064, FR-065, FR-066, FR-067, FR-068, FR-069, FR-070, FR-071, FR-072, FR-073, FR-074, FR-075, FR-076, FR-077** |
| 6 | Replace latency_logger with X-Ray annotations | [fix-sse-latency-xray.md](./fix-sse-latency-xray.md) | [ ] TODO | P2 | FR-006, FR-022 |
| 7 | Replace cache_logger with X-Ray annotations | [fix-sse-cache-xray.md](./fix-sse-cache-xray.md) | [ ] TODO | P2 | FR-007, FR-023 |
| 8 | Add SSE connection and polling annotations | [fix-sse-annotations.md](./fix-sse-annotations.md) | [ ] TODO | P2 | FR-008, FR-009 |
| 9 | Consolidate correlation IDs onto X-Ray trace IDs | [fix-correlation-id-consolidation.md](./fix-correlation-id-consolidation.md) | [ ] TODO | P3 | FR-010, FR-011, FR-012, FR-024 |
| 10 | Add frontend trace header propagation (CORS) | [fix-frontend-trace-headers.md](./fix-frontend-trace-headers.md) | [ ] TODO | P2 | FR-014, FR-015, FR-016, **FR-082** |
| 11 | Implement observability canary (X-Ray + CloudWatch health) | [fix-xray-canary.md](./fix-xray-canary.md) | [ ] TODO | P3 | FR-019, FR-020, FR-021, FR-036, **FR-049, FR-050, FR-051, FR-078, FR-079, FR-080** |
| 12 | Audit downstream consumers of removed systems | [fix-downstream-consumer-audit.md](./fix-downstream-consumer-audit.md) | [ ] TODO | P3 | FR-018, edge cases |
| 13 | Add explicit SendGrid X-Ray subsegment | [fix-sendgrid-explicit-subsegment.md](./fix-sendgrid-explicit-subsegment.md) | [ ] TODO | P1 | FR-028 |
| 14 | Standardize on Powertools Tracer (non-streaming Lambdas) | [fix-tracer-standardization.md](./fix-tracer-standardization.md) | [ ] TODO | P0 | FR-029, FR-030 |
| 15 | **Migrate frontend SSE to fetch()+ReadableStream** | [fix-sse-client-fetch-migration.md](./fix-sse-client-fetch-migration.md) | [ ] TODO | P2 | FR-032, FR-033, **FR-048, FR-081, FR-082, FR-083** |
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
| **(R7)** ADOT Layer Type | Not specified | **Collector-only layer (`aws-otel-collector-*`), version-pinned ARN** | **#5** |
| **(R7)** TracerProvider Lifecycle | Not specified | **Module-level singleton, per-invocation context extraction only** | **#5** |
| **(R7)** OTel Export Failure Detection | Not specified | **Canary-based (FR-019/FR-036); force_flush() unreliable for detection** | **#5, #11** |
| **(R7)** OTel Semantic Conventions | Not specified | **db.system, rpc.service, exception.type for X-Ray native rendering** | **#5** |
| **(R7)** Propagator Configuration | Not specified | **set_global_textmap() only; no OTEL_PROPAGATORS env var** | **#5** |
| **(R8)** ADOT Container Deployment | N/A (Lambda Layers impossible) | **Multi-stage Dockerfile: COPY from ADOT ECR image to /opt/extensions/** | **#5** |
| **(R8)** ADOT Image Version Pinning | N/A | **Digest-pinned ADOT container image (@sha256:...) in Dockerfile** | **#5** |
| **(R8)** OTel Service Name | Not configured (defaults to unknown_service) | **OTEL_SERVICE_NAME env var matching POWERTOOLS_SERVICE_NAME** | **#5** |
| **(R8)** OTel Resource Detector | Not configured | **AwsLambdaResourceDetector in TracerProvider resource for cloud.*/faas.* attributes** | **#5** |
| **(R8)** BatchSpanProcessor Config | Defaults (5s delay, 2048 queue) | **Lambda-tuned: 1s delay, 256 queue, 64 batch size** | **#5** |
| **(R9)** Two-Hop Flush Architecture | Not documented | **FR-074 acknowledges; FR-075 mandates decouple processor; canary detects aggregate loss** | **#5, #11** |
| **(R9)** BotocoreInstrumentor prohibition | Not prohibited | **Explicit prohibition: MUST NOT call BotocoreInstrumentor().instrument()** | **#5** |
| **(R9)** TracerProvider shutdown_on_exit | Default True (race) | **shutdown_on_exit=False; eliminates atexit race** | **#5** |
| **(R9)** Canary trace retrieval retry | Single-shot query | **Retry-with-backoff: 30s then 60s** | **#11** |
| **(R9)** Canary error classification | Uniform handling | **Differential: immediate escalation for IAM errors, retry for transient** | **#11** |
| **(R9)** Server-side Last-Event-ID | Not specified | **Server MUST check header or respond with X-SSE-Resume-Supported: false** | **#15** |
| **(R9)** CORS ExposeHeaders for trace ID | Not included | **x-amzn-trace-id in ExposeHeaders (hard prerequisite for FR-048)** | **#10, #15** |
| **(R9)** Reconnection close type strategy | Uniform backoff | **Graceful close: short delay; Network error: exponential backoff** | **#15** |

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

### ADOT Operational Lifecycle (Round 7)
- [ ] ADOT collector-only layer used (not Python SDK layer) — FR-062
- [ ] ADOT layer ARN version-pinned in Terraform — FR-063
- [ ] TracerProvider instantiated exactly once per execution environment — SC-027
- [ ] Streaming-phase DynamoDB/CloudWatch spans render as typed nodes in X-Ray service map — SC-028
- [ ] No OTEL_PROPAGATORS environment variable set on SSE Lambda — FR-068
- [ ] OTel semantic conventions used for all streaming-phase spans — FR-067

### Container-Based ADOT Deployment (Round 8)
- [ ] ADOT collector binary at `/opt/extensions/collector` in SSE Lambda container image — SC-029
- [ ] ADOT container image digest-pinned in Dockerfile — FR-070
- [ ] SSE Lambda appears as correct service name (not `unknown_service`) in X-Ray service map — SC-030
- [ ] `AwsLambdaResourceDetector` configured in TracerProvider — FR-072
- [ ] BatchSpanProcessor uses Lambda-tuned parameters — FR-073
- [ ] `OTEL_SERVICE_NAME` env var set in Terraform, matching `POWERTOOLS_SERVICE_NAME` — FR-071

### ADOT Flush Architecture & Canary Hardening (Round 9)
- [ ] ADOT decouple processor configured for SSE Lambda — SC-031
- [ ] BotocoreInstrumentor NOT called on SSE Lambda — SC-032
- [ ] TracerProvider created with shutdown_on_exit=False — SC-033
- [ ] Canary retries trace retrieval with backoff (30s then 60s) — SC-034
- [ ] Canary classifies put_metric_data errors with differential handling — SC-035
- [ ] Server-side Last-Event-ID support checked or fallback header sent — SC-036
- [ ] CORS ExposeHeaders includes x-amzn-trace-id — SC-037
- [ ] SSE reconnection uses close-type-aware backoff strategy — SC-038

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
| **(R7)** OTel export failure silent by design | **CONFIRMED** | **HIGH** | `BatchSpanProcessor._export()` catches all exceptions; `force_flush()` always returns True. Canary is sole detection (FR-019/FR-036) |
| **(R7)** TracerProvider per-invocation memory leak | **CONFIRMED** | **HIGH** | Module-level singleton mandatory (FR-065); per-invocation creates orphaned daemon threads |
| **(R7)** ADOT SDK layer used instead of collector-only | Medium | **HIGH** | FR-062 requires collector-only layer; SDK layer wastes 45MB + auto-instrumentation risk |
| **(R7)** ADOT layer ARN not version-pinned | Medium | **MEDIUM** | FR-063 requires pinned version; unpinned can break collector on terraform apply |
| **(R7)** Non-standard OTel span attributes | Medium | **MEDIUM** | FR-067 requires semantic conventions; non-standard = invisible in X-Ray |
| **(R7)** OTEL_PROPAGATORS env var confusion | Low | **LOW** | FR-068 prohibits env var; set_global_textmap() is single source of truth |
| **(R8)** Container-based Lambda cannot use Lambda Layers | **CONFIRMED** | **BLOCKER** | ADOT embedded via multi-stage Dockerfile build (FR-069/FR-070); FR-062/FR-063 REWRITTEN |
| **(R8)** `service.name` defaults to `unknown_service` | **CONFIRMED** | **HIGH** | `OTEL_SERVICE_NAME` env var required (FR-071); X-Ray uses this for service map node naming |
| **(R8)** `AwsLambdaResourceDetector` missing from TracerProvider | **CONFIRMED** | **HIGH** | FR-072 requires resource detector; provides cloud.*/faas.* metadata |
| **(R8)** BatchSpanProcessor defaults oversized for Lambda | **CONFIRMED** | **MEDIUM** | FR-073 mandates Lambda-tuned config (1s/256/64) |
| **(R8)** SSE Lambda custom runtime + ADOT compatibility | **NOT A RISK** | N/A | Extensions are Lambda service-level; `python:3.13-slim` + custom bootstrap fully compatible |
| **(R9)** ADOT Extension span drop race condition | **CONFIRMED (KNOWN)** | **HIGH** | Decouple processor is mitigation; canary provides aggregate detection (FR-074/FR-075) |
| **(R9)** Canary IAM error not immediately escalated | **CONFIRMED** | **HIGH** | Error classification with differential handling (FR-079) |
| **(R9)** BotocoreInstrumentor accidentally enabled | Medium | **MEDIUM** | Explicit prohibition in FR-076 |
| **(R9)** TracerProvider atexit shutdown race | **CONFIRMED** | **MEDIUM** | shutdown_on_exit=False (FR-077) |
| **(R9)** Canary false negative from propagation delay | **CONFIRMED** | **MEDIUM** | Retry-with-backoff (FR-078) |
| **(R9)** Server ignores Last-Event-ID | Medium | **MEDIUM** | Server-side requirement or fallback header (FR-081) |
| **(R9)** CORS blocks trace header reading | **CONFIRMED** | **MEDIUM** | ExposeHeaders mandate (FR-082) |
| **(R9)** BSP default assumption incorrect (200ms vs 5000ms) | **CONFIRMED** | **MEDIUM** | Corrected in FR-084; runtime unaffected (FR-073 override) |
| **(R9)** Transaction Search breaks BatchGetTraces | Low | **LOW** | Edge case documented; canary tests own retrieval path |

---

## References

- Spec: `specs/1219-xray-exclusive-tracing/spec.md`
- Audit: `docs/audit/2026-02-13-playwright-coverage-observability-blind-spots.md`
- Checklist: `specs/1219-xray-exclusive-tracing/checklists/requirements.md`
- AWS X-Ray SDK: `aws-xray-sdk` (currently v2.15.0 in requirements.txt)
- AWS Lambda Powertools: `aws-lambda-powertools` (currently v3.23.0, Dashboard Lambda only → ALL non-streaming Lambdas after Task 14)
- ADOT Lambda Extension: Container-based deployment via `public.ecr.aws/aws-observability/aws-otel-lambda-extension-amd64` (SSE Lambda only, Task 5)
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
| 2026-02-22 | **Round 7 updates:** ADOT operational lifecycle deep-dive. 7 blind spots analyzed, 7 resolved. Added FR-062 through FR-068. Collector-only layer requirement (FR-062), version pinning (FR-063), collector pipeline verification (FR-064), TracerProvider singleton lifecycle (FR-065), export failure detection gap (FR-066), OTel semantic conventions (FR-067), propagator configuration hygiene (FR-068). Added SC-027 (singleton verification), SC-028 (service map correctness). Totals: 68 FRs, 28 SCs, 41 edge cases, 32 assumptions. |
| 2026-02-22 | **Round 8 updates:** 1 BLOCKER — SSE Lambda is container-based (ECR image), cannot use Lambda Layers. FR-062/FR-063 REWRITTEN for container deployment. Added FR-069 (Dockerfile ADOT embedding), FR-070 (digest pinning), FR-071 (OTEL_SERVICE_NAME), FR-072 (AwsLambdaResourceDetector), FR-073 (BSP Lambda config). Added SC-029 (ADOT in container), SC-030 (service map naming). Round 7 assumption about "zero layers" INVALIDATED. Work order Task 5 FR list updated (14 missing FRs added). Totals: 73 FRs, 30 SCs, 45 edge cases, 37 assumptions. |
| 2026-02-22 | **Round 9 updates:** Four-domain deep research (ADOT container deployment, OTel SDK Lambda behavior, X-Ray canary implementation, frontend SSE migration). 14 blind spots analyzed (12 resolved via FRs, 2 informational). Added FR-074 through FR-084. Added SC-031 through SC-038. Corrected Round 5 BSP default assumption (200ms → 5000ms). Two-hop flush architecture formally acknowledged with decouple processor requirement. Canary error classification added for differential IAM error handling. Server-side Last-Event-ID support required. CORS ExposeHeaders mandate for trace correlation. Totals: 84 FRs, 38 SCs, 56 edge cases, 45 assumptions (3 invalidated, 1 corrected). |
