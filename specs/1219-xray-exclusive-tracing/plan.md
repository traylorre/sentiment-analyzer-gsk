# Implementation Plan: X-Ray Exclusive Tracing

**Branch**: `1219-xray-exclusive-tracing` | **Date**: 2026-03-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1219-xray-exclusive-tracing/spec.md` (Round 26, 208 FRs, 148 SCs)

## Summary

Consolidate all observability onto AWS X-Ray as the exclusive distributed tracing system across the sentiment-analyzer-gsk platform. This replaces custom logging (latency_logger, cache_logger), custom correlation IDs, and partial X-Ray coverage with full end-to-end tracing across 6 Lambda functions, 7 silent failure paths, frontend SSE streaming, and a dedicated canary Lambda. The SSE Streaming Lambda requires ADOT Extension + OTel SDK due to RESPONSE_STREAM lifecycle constraints.

## Technical Context

**Language/Version**: Python 3.13 (pyproject.toml standard)
**Primary Dependencies**:
- `aws-lambda-powertools[tracer]` — standard Lambda tracing (5 of 6 Lambdas)
- `opentelemetry-api==1.39.1`, `opentelemetry-sdk==1.39.1` — SSE Lambda OTel instrumentation
- `opentelemetry-exporter-otlp-proto-http==1.39.1` — OTLP HTTP exporter to ADOT Extension
- `opentelemetry-instrumentation-aws-lambda==0.45b0` — X-Ray propagator, ID generator, resource detector
- ADOT Lambda Extension v0.47.1+ (collector-only, embedded in SSE Lambda container)
**Storage**: DynamoDB (5 tables), S3 (artifacts), CloudWatch Logs/Metrics
**Testing**: pytest 8.0+ (unit/moto, integration/LocalStack, e2e/preprod), Playwright (frontend)
**Target Platform**: AWS Lambda (6 functions + 1 canary), API Gateway, Lambda Function URLs
**Project Type**: Serverless microservices (Python Lambdas + Next.js frontend)
**Performance Goals**: SSE cold start <2000ms P95 (FR-158), ≥95% streaming span retention (FR-160)
**Constraints**: X-Ray 50 annotation/trace limit, 500 TPS default PutTraceSegments quota, 2s Lambda SIGKILL window, ADOT ~80MB overhead
**Scale/Scope**: 6 Lambdas × 7 silent failure paths × 30+ CloudWatch alarms + frontend migration + canary

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.5 — Canonical Source Verification | **APPLIES** | X-Ray SDK docs, OTel SDK docs, ADOT docs, WHATWG Fetch spec required |
| Amendment 1.6 — No Quick Fixes | **PASS** | Spec exists (26 rounds), this IS the speckit workflow |
| Amendment 1.7 — Target Repo Independence | **N/A** | This is the target repo itself |
| Amendment 1.8 — IAM Managed Policy Mandate | **APPLIES** | All X-Ray IAM policies must be `aws_iam_policy` + attachment, no inline |
| Amendment 1.9 — Never Destroy Workspace Files | **APPLIES** | Standard protection |
| Amendment 1.10 — Constitution Loading | **PASS** | Constitution loaded and checked |
| Amendment 1.11 — Clean Workspace | **APPLIES** | Verify clean before each work session |
| Amendment 1.12 — Mandatory Speckit Workflow | **PASS** | Following specify → clarify → plan → clarify → tasks → implement |
| Amendment 1.13 — Drift Reduction | **APPLIES** | Feature must reduce spec↔implementation drift |
| Amendment 1.14 — Validator Usage | **APPLIES** | Run validators before committing |
| Amendment 1.15 — No Fallback Configuration | **APPLIES** | All new env vars must use `os.environ["KEY"]` (fail-fast) |
| Cost Sensitivity | **FLAG** | SSE Lambda 512→1024MB (+$5.40/mo at 10K inv), ADOT overhead, ~45 CloudWatch alarms ($0.10/alarm/mo = ~$4.50/mo), X-Ray $5/million traces |

**Cost Estimate**: ~$15-25/mo incremental (within budget thresholds)

**Note**: FR-202 establishes that `ADOT_LAMBDA_FLUSH_TIMEOUT` is a non-existent env var. The 2s Lambda Extension shutdown window is a platform constraint, not configurable. FR-203 confirms ADOT Extension binary has ZERO processors compiled in (`lambdacomponents/default.go` registers none). The `decouple` processor is an open feature request (`aws-otel-lambda#842`). Collector config MUST use processor-less pipeline: `receivers: [otlp] → exporters: [awsxray]`. All span retention depends on SDK-side `force_flush()` (FR-139).

## Project Structure

### Documentation (this feature)

```text
specs/1219-xray-exclusive-tracing/
├── spec.md              # Feature specification (Round 26, 474KB)
├── plan.md              # This file
├── research.md          # Phase 0 output — technology decisions
├── data-model.md        # Phase 1 output — entity model
├── quickstart.md        # Phase 1 output — developer onboarding
├── contracts/           # Phase 1 output — configuration contracts
│   ├── adot-collector-config.yaml    # ADOT Extension collector pipeline
│   ├── otel-sdk-config.md            # OTel SDK initialization contract
│   ├── cloudwatch-alarms.md          # Alarm definitions contract
│   └── xray-groups-sampling.md       # X-Ray Groups and Sampling Rules
├── checklists/
│   └── requirements.md  # FR/SC tracking checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/lambdas/
├── ingestion/handler.py        # Task 14: Migrate 7 @xray_recorder → Powertools Tracer
├── analysis/handler.py         # Task 14: Migrate decorators + FR-206 deadline flush
├── dashboard/handler.py        # Task 14: Already Powertools; remove redundant patch_all()
├── notification/handler.py     # Task 14: Migrate decorators + Task 13: SendGrid subsegment
├── metrics/handler.py          # Task 2: Add Powertools Tracer (currently zero X-Ray)
├── sse_streaming/
│   ├── handler.py              # Task 5: OTel SDK streaming-phase instrumentation
│   ├── bootstrap               # Task 5: Fix warm invocation _X_AMZN_TRACE_ID (FR-092)
│   └── Dockerfile              # Task 5: Embed ADOT Extension (multi-stage build)
└── canary/                     # Task 11: NEW — X-Ray health canary
    └── handler.py

infrastructure/terraform/
├── modules/iam/main.tf         # Task 1: Add X-Ray permissions to 4 missing roles
├── modules/lambda/main.tf      # Tasks 2-5: Lambda config (memory, env vars, layers)
├── modules/xray/               # Task 16: NEW — X-Ray Groups, Sampling Rules
├── modules/cloudwatch-alarms/  # Task 17: NEW — ~38 alarm definitions
└── main.tf                     # Orchestration

frontend/
└── src/services/sse-client.ts  # Task 15: EventSource → fetch()+ReadableStream

tests/
├── unit/test_xray_*.py         # Per-task unit tests
├── integration/test_xray_*.py  # LocalStack integration tests
├── e2e/helpers/xray.py         # Existing X-Ray query helpers
└── e2e/test_xray_*.py          # Preprod verification gates
```

**Structure Decision**: Existing serverless microservice layout. No new top-level directories. Changes span Lambda handlers, Terraform modules, frontend SSE client, and test suites.

## Superseded Requirements

The following MUST-level FRs and SCs are **impossible to satisfy** because the ADOT Lambda Extension binary has zero processors compiled in (FR-203, `aws-otel-lambda#842`). They are superseded by the processor-less architecture adopted in this plan:

| Requirement | Original Text | Status | Superseded By |
|-------------|---------------|--------|---------------|
| FR-075 | ADOT config MUST include `decouple` processor | **BLOCKED** | FR-203 (ADOT has zero processors) |
| FR-090 | Pipeline order MUST be `[decouple, batch]` | **BLOCKED** | FR-203 |
| FR-074 | Decouple processor is the accepted mitigation | **STALE** | Proactive flush (FR-093) + SDK force_flush (FR-139) are the actual mitigation |
| SC-031 | ADOT pipeline includes decouple processor | **IMPOSSIBLE** | Processor-less pipeline verified instead |
| SC-044 | Custom ADOT YAML includes `decouple` in `[decouple, batch]` order | **IMPOSSIBLE** | Processor-less pipeline verified instead |

**Impact**: Without decouple, the Extension shutdown span-loss race (`aws-otel-lambda#886`, ~30% worst-case) applies to hop 2 (Extension→X-Ray backend). SDK-side `force_flush()` only covers hop 1 (SDK→Extension). Mitigation analysis:

1. **Proactive flush (FR-093)** fires at `remaining_time < 3000ms`, draining the SDK's BSP queue to the Extension well before the Lambda timeout. This gives the Extension the remaining Lambda execution time + 2s shutdown window to export spans to X-Ray.
2. For a 15-second SSE invocation, proactive flush fires at T-3s (T=12s), giving the Extension ~5s (3s remaining + 2s shutdown) to export. With ~675 spans at 64/batch = ~11 OTLP requests, and sub-ms localhost transfer, the Extension receives all spans by ~T-2.9s. The Extension then has ~4.9s to export to X-Ray — far exceeding the ~30% worst-case scenario (which assumes flush happens concurrently with shutdown).
3. **FR-160's ≥95% retention target remains achievable** because the proactive flush temporal separation avoids the shutdown race that causes the ~30% drop. The Phase 2 gate (SC-110) validates this in preprod.

## Implementation Phases (FR-107)

### Phase 1: Foundation (Task 1)
**Goal**: Unblock all subsequent instrumentation work.

| Task | Description | FRs | Complexity | Blocks |
|------|-------------|-----|------------|--------|
| Task 1 | Add X-Ray + ADOT IAM permissions (5 actions) to Ingestion, Analysis, Dashboard, Metrics IAM roles + IAM drift detection | FR-017, FR-159, FR-168 | Low | All others |
| Task 19 | Request PutTraceSegments Service Quotas increase (500→1000 TPS) | FR-178 | Low | None (file early, approval takes days) |

**Gate**: All 6 Lambda execution roles have 5 actions verified: `xray:PutTraceSegments`, `xray:PutTelemetryRecords`, `xray:GetSamplingRules`, `xray:GetSamplingTargets`, `xray:GetSamplingStatisticSummaries` (FR-159). Missing `GetSampling*` causes SILENT fallback to 1 trace/sec. Service Quotas increase request filed (FR-178: projected peak ~520 TPS exceeds 500 default).

### Phase 2: Instrumentation (Tasks 14, 2, 3, 4, 5, 13)
**Goal**: Full X-Ray trace coverage across all Lambdas and failure paths.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 14 | Standardize all 6 Lambdas on Powertools Tracer (57 decorator migrations) | FR-029, FR-030, FR-031, FR-205, FR-206 | High | Task 1 |
| Task 2 | Instrument Metrics Lambda (currently zero X-Ray) | FR-003, FR-004 | Low | Tasks 1, 14 |
| Task 3 | Verify SNS cross-Lambda trace propagation | FR-013 | Low | Task 1 |
| Task 4 | Instrument 7 silent failure paths with dual X-Ray+CloudWatch + metric emission chain | FR-002, FR-005, FR-043, FR-097, FR-124, FR-125, FR-134, FR-142, FR-143, FR-147 | High | Tasks 1, 14 |
| Task 5 | SSE Lambda ADOT Extension + OTel SDK streaming instrumentation (see subtask breakdown below) | FR-001, FR-025-027, FR-046-095, FR-100, FR-103, FR-106, FR-144, FR-149, FR-150, FR-165, FR-166 | High | Tasks 1, 14 |
| Task 13 | SendGrid explicit subsegment (urllib not auto-patched) | FR-028 | Low | Tasks 1, 14 |

**Gate**: SC-110 (≥95% streaming span retention), FR-160 (preprod verification), SC-087 (SNS propagation), FR-158 (SSE cold start P95 <2000ms measured in preprod — SC-108), SC-072 (preprod rollback drill: kill switch <5 min, full image rollback <15 min).

#### Task 5 Subtask Breakdown

Task 5 spans 50+ FRs. Decomposed into 8 ordered subtasks:

| # | Subtask | Key FRs | Notes |
|---|---------|---------|-------|
| 5a | Dockerfile: embed ADOT Extension via multi-stage build + pre-ADOT baseline image | FR-062, FR-069, FR-070, FR-095, FR-110 | COPY from `public.ecr.aws/aws-observability/aws-otel-lambda-extension-amd64@sha256:{digest}` — cannot use Lambda Layers (container-based). Tag current image as `pre-adot-baseline` in ECR before building ADOT image (SC-060: rollback artifact with 90-day retention) |
| 5b | Bootstrap: trace ID + deadline propagation | FR-092, FR-103 | Read `Lambda-Runtime-Trace-Id` AND `Lambda-Runtime-Deadline-Ms` from Runtime API. FR-103 is prerequisite for proactive flush (FR-093) |
| 5c | OTel SDK module-level TracerProvider init | FR-052-065, FR-071-077, FR-101, FR-106, FR-108 | Singleton pattern, `shutdown_on_exit=False`, `OTEL_SDK_DISABLED` kill switch. FR-106: try/except with structured error attribution |
| 5d | Per-invocation trace context extraction | FR-059, FR-092 | `AwsXRayPropagator.extract()` from `_X_AMZN_TRACE_ID` — must run every invocation, not module-level |
| 5e | Streaming-phase span creation | FR-046-055, FR-067, FR-085, FR-086 | ~675 spans/invocation (15 polls/sec × 3 spans/poll × 15s). `auto_patch=False` (FR-060), no `BotocoreInstrumentor` (FR-076) |
| 5f | Three-layer flush pipeline | FR-055, FR-093, FR-100, FR-139, FR-149 | (1) Proactive flush at `remaining_time < 3000ms`, (2) 2500ms thread wrapper, (3) `finally` block. After flush: yield `event: deadline` + return (FR-100). Set `flush_fired` flag to block further span creation (FR-149) |
| 5g | Error handling: dual status + exception recording | FR-144, FR-150 | CRITICAL: every caught exception MUST call BOTH `span.set_status(ERROR)` AND `span.record_exception()`. Without both, X-Ray shows `fault: false`. Context manager for propagating exceptions; manual dual-call for caught exceptions in 7 silent failure paths |
| 5h | Client disconnect: BrokenPipeError handling | FR-085 | Catch `BrokenPipeError`, set `client.disconnected=true` annotation, set span status OK (not ERROR), proceed to `finally` for flush. Lambda does NOT interrupt streaming on disconnect — writes fail silently |

**Dual-phase architecture summary**: Powertools Tracer captures the handler invocation as an X-Ray subsegment (init phase). The handler returns a generator; the streaming phase (generator iteration by bootstrap) runs AFTER Powertools' segment closes. OTel SDK + ADOT Extension cover the streaming phase, with `AwsXRayPropagator` bridging trace context via `_X_AMZN_TRACE_ID`.

### Phase 3: Frontend (Task 15)
**Goal**: End-to-end browser-to-backend trace correlation.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 10 | CORS headers + frontend trace header propagation | FR-014, FR-015, FR-016 | Low | Task 1 |
| Task 15 | Migrate SSE client from EventSource to fetch()+ReadableStream (see subtask breakdown below) | FR-032, FR-033, FR-048, FR-081, FR-083, FR-088, FR-089, FR-099, FR-115, FR-118, FR-148 | High | Task 10 |

**Gate**: SC-085 (Playwright: X-Amzn-Trace-Id on all fetch() calls), FR-135, FR-148 (RUM readiness: fetch() must NOT fire until CloudWatch RUM FetchPlugin has patched `window.fetch`, 5s bounded wait).

#### Task 15 Subtask Breakdown

EventSource provides reconnection, Last-Event-ID, and SSE parsing automatically. `fetch()+ReadableStream` requires manual implementation of all three.

| # | Subtask | Key FRs | Notes |
|---|---------|---------|-------|
| 15a | SSE text protocol parser | FR-088, FR-089 | Parse `retry:`, `data:`, `id:`, `event:` fields per SSE spec. Server emits `retry: 3000\n` as first field (FR-088) |
| 15b | Connection state machine | FR-033, FR-083, FR-118 | States: connected, reconnecting, disconnected, error. FR-118: 4 error categories with distinct strategies — graceful close, abnormal termination, network error, intentional cancellation |
| 15c | Exponential backoff + reconnection | FR-033 | Jitter, `Last-Event-ID` propagation (FR-081), `session_id` generation (FR-048), `connection_sequence` counter, `previous_trace_id` from response headers |
| 15d | Trace header injection | FR-032, FR-148 | `X-Amzn-Trace-Id` on all fetch() calls. CRITICAL: must wait for RUM FetchPlugin patching (5s bounded wait per FR-148) — otherwise first SSE connection races RUM init |
| 15e | TextDecoder streaming mode | FR-099 | `new TextDecoder('utf-8', {stream: true})` for multi-byte UTF-8 boundary handling. Safari-specific buffering (sveltejs/kit#10315) |
| 15f | AbortController integration | — | Standard mechanism for stream cancellation; EventSource has no equivalent |
| 15g | trace_id in SSE payload | FR-115 | Each SSE event includes `trace_id` in JSON data payload for frontend logging |

**Rollback**: If `fetch()` migration causes production streaming failures, revert to `EventSource` via git revert of Task 15 changes. Task 10 CORS changes remain compatible with both implementations.

### Phase 4: Logging Removal (Tasks 6, 7, 9)
**Goal**: Remove replaced custom logging systems after 2-week dual-emit verification.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 18 | Build FR-109 verification gate scripts (automated pass/fail for dual-emit period) | FR-109, FR-117, FR-152 | Medium | Phase 2 complete |
| Task 6 | Remove latency_logger.py → X-Ray annotations | FR-006, FR-022 | Medium | Task 5, Task 18, 2-week verification |
| Task 7 | Remove cache_logger.py → X-Ray annotations | FR-007, FR-023 | Medium | Task 5, Task 18, 2-week verification |
| Task 9 | Remove custom correlation IDs → X-Ray trace IDs | FR-010-012, FR-024 | Low | Tasks 2, 4, 5, Task 18, 2-week verification |

**Gate**: FR-109 (4 verification gates over 2-week dual-emit period), executed by Task 18 scripts.

Task 18 creates 4 executable verification gates (SC-067) + automated trace validation script (SC-102):

| Gate | Script | What It Checks |
|------|--------|----------------|
| (a) Semantic trace comparison | `scripts/verify-trace-structure.py` | X-Ray trace structure matches expected segment topology per Lambda |
| (b) Annotation key set diff | `scripts/verify-annotation-parity.py` | All annotation keys from removed loggers present as X-Ray annotations |
| (c) Service map accuracy | `scripts/verify-service-map.py` | Service map API query shows all 6 Lambdas + canary connected |
| (d) 100-trace spot-check | `scripts/verify-trace-sample.py` | 100 traces spot-checked for minimum expected segment counts (FR-152) |

### Phase 5: Monitoring (Tasks 8, 16, 17)
**Goal**: Comprehensive alarm coverage and operational monitoring.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 8 | SSE connection/DynamoDB polling annotations | FR-008, FR-009 | Low | Task 5 |
| Task 16 | X-Ray sampling rules, cost guards, Groups (insights_enabled=true per FR-111), sampling graduation + kill switch ops | FR-034, FR-035, FR-038, FR-039, FR-111, FR-179, FR-180, FR-181 | Medium | None |
| Task 17 | CloudWatch alarm coverage (~38 alarms). FR-041 two-phase strategy: Phase 1 deploys loose thresholds (80% of timeout); Phase 2 tightens to 2x observed P95 after 2+ weeks ADOT runtime. Includes API Gateway/Function URL alarms (FR-138) and memory utilization alarms (FR-104). | FR-040-045, FR-061, FR-104, FR-121, FR-127, FR-128, FR-131, FR-138, FR-162 | High | Task 4 |

**Gate**: All alarms firing correctly, dashboard completeness (SC-091).

### Phase 6: Validation (Tasks 11, 12)
**Goal**: Meta-observability canary and final cleanup audit.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 11 | X-Ray canary Lambda (meta-observability): EventBridge 5-min schedule, SSM state persistence, cross-region SNS alerting, rollback runbook | FR-019-021, FR-036, FR-049-051, FR-096, FR-110, FR-112, FR-113, FR-122, FR-126, FR-136, FR-145, FR-146, FR-151, FR-169, FR-207 | High | Phase 2 complete |
| Task 12 | Downstream consumer audit (removed systems) | FR-018 | Medium | Tasks 6, 7, 9 |

**CRITICAL SEQUENCING NOTE**: Task 11 (canary) MUST deploy immediately after Phase 2 completes, NOT after Phase 5. FR-109 gate (a) requires the canary to report healthy for 14 consecutive days before Phase 4 (logging removal) can begin. While Task 11 is categorized as Phase 6 per FR-107, it must be deployed early and run in parallel with Phases 3 and 5 to accumulate the required 14-day healthy baseline.

**Gate**: Canary completeness_ratio ≥95% (SC-063), SC-086 (cross-region SNS out-of-band alerting verified).

## Critical Path

```
Task 19 (Service Quotas) ──→ [approval before prod deploy]

Task 1 (IAM, 5 actions) ──→ Task 14 (Tracer Standardization) ──┬──→ Task 5 (SSE ADOT, 8 subtasks) ──→ FR-158 gate
                                                                 ├──→ Task 4 (Silent Failures + metric chain) ──→ Task 17 (Alarms)
                                                                 ├──→ Task 2 (Metrics Lambda)
                                                                 └──→ Task 13 (SendGrid)

Task 10 (CORS) ──→ Task 15 (Frontend SSE, 7 subtasks)

[Phase 2 complete] ──→ Task 11 (Canary) ──→ [14 days healthy] ──┐
                   ├──→ Task 18 (Verification Gate Scripts) ─────┘──→ Tasks 6, 7, 9 (Logging Removal) ──→ Task 12 (Audit)
                   └──→ Tasks 8, 16, 17 (Monitoring) — runs in parallel with canary accumulation
```

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| **ADOT Extension has NO processors compiled in** (decouple, batch absent — `aws-otel-lambda#842` open) | Collector config with `processors: [decouple, batch]` fails at startup; without decouple, hop 2 (Extension→X-Ray) has ~30% worst-case span drop during shutdown (`aws-otel-lambda#886`) | **PARTIALLY MITIGATED**: Removed processors from collector config (pipeline: `otlp → awsxray`). Hop 1 (SDK→Extension) covered by `force_flush()` (FR-139). Hop 2 mitigated by temporal separation: proactive flush (FR-093) drains SDK at T-3s, giving Extension ~5s to export before SIGKILL. See Superseded Requirements section for full analysis. FR-075/FR-090/SC-031/SC-044 declared BLOCKED |
| ADOT Extension crash mid-stream (span-loss vector #2) | Span data loss for 5-15 min | FR-200 (amends FR-196): Canary detection + pre-adot-baseline rollback image (FR-110, SC-060) |
| ADOT exporter backend error (span-loss vector #4) | Spans dropped silently on persistent X-Ray 429/500 | FR-201: Canary detects degraded export state; daily cost anomaly alarm (FR-161) |
| force_flush() hangs indefinitely | Lambda timeout, span loss | FR-139: 2500ms thread wrapper + OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2000 |
| **500 TPS X-Ray quota exceeded** | Silent data loss from day one (projected peak ~520 TPS > 500 default) | **BLOCKER**: Task 19 files Service Quotas increase request pre-production. Monitoring alarm tracks `UnprocessedTraceSegments` |
| Frontend EventSource→fetch migration breaks SSE | User-facing streaming failure | Task 15 subtask breakdown: SSE parser, reconnection state machine, 4-category error classification (FR-118), Playwright gate. Rollback: git revert Task 15 |
| Annotation budget overflow (>50/trace) | Diagnostic data truncated silently | FR-186/FR-193: Budget-aware allocation with 3 reserved exception slots; CI gate for annotation key validation |
| OTel SDK v1.39.1 incompatibility | Build failure | FR-101: Pin all core packages to identical version |
| Dual-emit period too short | Remove logging before X-Ray verified | FR-109: Hard 2-week minimum with 4 verification gates. Task 18 builds executable gate scripts |
| FR-144 error status omission | X-Ray shows `fault: false` for real errors — invisible failures | Subtask 5g: mandatory dual-call pattern (`set_status` + `record_exception`). CI gate (SC-100) greps for `except` blocks missing both calls |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-----------|--------------------------------------|
| SSE Lambda 512→1024MB | ADOT Extension ~80MB overhead | Cannot use Lambda Layers (container-based); no lighter OTel exporter exists |
| Dual tracing framework (Powertools + OTel) | RESPONSE_STREAM closes X-Ray segment before streaming | begin_segment() is no-op in Lambda; no single SDK handles both phases |
| ~38 CloudWatch alarms | 6 Lambdas × (error + latency + memory) + 7 silent failure + canary + cost + ADOT + API GW/Function URL | Individual alarms needed for targeted alerting; composite alarm covers severity tiers |
| Custom bootstrap modification | Warm invocation trace ID + deadline propagation (FR-092, FR-103) | Lambda runtime doesn't update _X_AMZN_TRACE_ID on warm starts; deadline needed for proactive flush |
| Processor-less ADOT collector config | `decouple` and `batch` processors not compiled into ADOT Lambda Extension binary | `aws-otel-lambda#842` open; pipeline is direct `otlp → awsxray`. Span retention depends on SDK `force_flush()` |
