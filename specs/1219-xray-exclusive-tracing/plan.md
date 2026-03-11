# Implementation Plan: X-Ray Exclusive Tracing

**Branch**: `1219-xray-exclusive-tracing` | **Date**: 2026-03-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1219-xray-exclusive-tracing/spec.md` (Round 26, 204 FRs, 148 SCs)

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

**Note**: FR-202 establishes that `ADOT_LAMBDA_FLUSH_TIMEOUT` is a non-existent env var. The 2s Lambda Extension shutdown window is a platform constraint, not configurable. FR-203 confirms ADOT Extension has ZERO span processors — all processing in Python SDK.

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
├── modules/cloudwatch-alarms/  # Task 17: NEW — ~35 alarm definitions
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

## Implementation Phases (FR-107)

### Phase 1: Foundation (Task 1)
**Goal**: Unblock all subsequent instrumentation work.

| Task | Description | FRs | Complexity | Blocks |
|------|-------------|-----|------------|--------|
| Task 1 | Add X-Ray write permissions to Ingestion, Analysis, Dashboard, Metrics IAM roles | FR-017 | Low | All others |

**Gate**: `xray:PutTraceSegments` permission verified on all 6 Lambda execution roles.

### Phase 2: Instrumentation (Tasks 14, 2, 3, 4, 5, 13)
**Goal**: Full X-Ray trace coverage across all Lambdas and failure paths.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 14 | Standardize all 6 Lambdas on Powertools Tracer (57 decorator migrations) | FR-029, FR-030, FR-031, FR-205, FR-206 | High | Task 1 |
| Task 2 | Instrument Metrics Lambda (currently zero X-Ray) | FR-003, FR-004 | Low | Tasks 1, 14 |
| Task 3 | Verify SNS cross-Lambda trace propagation | FR-013 | Low | Task 1 |
| Task 4 | Instrument 7 silent failure paths with dual X-Ray+CloudWatch | FR-002, FR-005, FR-043 | High | Tasks 1, 14 |
| Task 5 | SSE Lambda ADOT Extension + OTel SDK streaming instrumentation | FR-001, FR-025-027, FR-046-095 | High | Tasks 1, 14 |
| Task 13 | SendGrid explicit subsegment (urllib not auto-patched) | FR-028 | Low | Tasks 1, 14 |

**Gate**: SC-110 (≥95% streaming span retention), FR-160 (preprod verification), SC-087 (SNS propagation).

### Phase 3: Frontend (Task 15)
**Goal**: End-to-end browser-to-backend trace correlation.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 10 | CORS headers + frontend trace header propagation | FR-014, FR-015, FR-016 | Low | Task 1 |
| Task 15 | Migrate SSE client from EventSource to fetch()+ReadableStream | FR-032, FR-033, FR-048 | High | Task 10 |

**Gate**: SC-085 (Playwright: X-Amzn-Trace-Id on all fetch() calls), FR-135.

### Phase 4: Logging Removal (Tasks 6, 7, 9)
**Goal**: Remove replaced custom logging systems after 2-week dual-emit verification.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 6 | Remove latency_logger.py → X-Ray annotations | FR-006, FR-022 | Medium | Task 5, 2-week verification |
| Task 7 | Remove cache_logger.py → X-Ray annotations | FR-007, FR-023 | Medium | Task 5, 2-week verification |
| Task 9 | Remove custom correlation IDs → X-Ray trace IDs | FR-010-012, FR-024 | Low | Tasks 2, 4, 5, 2-week verification |

**Gate**: FR-109 (4 verification gates over 2-week dual-emit period).

### Phase 5: Monitoring (Tasks 8, 16, 17)
**Goal**: Comprehensive alarm coverage and operational monitoring.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 8 | SSE connection/DynamoDB polling annotations | FR-008, FR-009 | Low | Task 5 |
| Task 16 | X-Ray sampling rules and cost guards | FR-034, FR-035, FR-038, FR-039 | Medium | None |
| Task 17 | CloudWatch alarm coverage (~35 alarms). FR-041 two-phase strategy: Phase 1 deploys loose thresholds (80% of timeout); Phase 2 tightens to 2x observed P95 after 2+ weeks ADOT runtime. | FR-040-045, FR-061, FR-121, FR-127, FR-128, FR-131, FR-162 | High | Task 4 |

**Gate**: All alarms firing correctly, dashboard completeness (SC-091).

### Phase 6: Validation (Tasks 11, 12)
**Goal**: Meta-observability canary and final cleanup audit.

| Task | Description | FRs | Complexity | Dependencies |
|------|-------------|-----|------------|--------------|
| Task 11 | X-Ray canary Lambda (meta-observability) | FR-019-021, FR-036, FR-049-051, FR-207 | High | Phase 2 complete |
| Task 12 | Downstream consumer audit (removed systems) | FR-018 | Medium | Tasks 6, 7, 9 |

**CRITICAL SEQUENCING NOTE**: Task 11 (canary) MUST deploy immediately after Phase 2 completes, NOT after Phase 5. FR-109 gate (a) requires the canary to report healthy for 14 consecutive days before Phase 4 (logging removal) can begin. While Task 11 is categorized as Phase 6 per FR-107, it must be deployed early and run in parallel with Phases 3 and 5 to accumulate the required 14-day healthy baseline.

**Gate**: Canary completeness_ratio ≥95% (SC-063), SC-092 (out-of-band alerting verified).

## Critical Path

```
Task 1 (IAM) ──→ Task 14 (Tracer Standardization) ──┬──→ Task 5 (SSE ADOT) ──→ Task 6/7 (Log Removal)
                                                      ├──→ Task 4 (Silent Failures) ──→ Task 17 (Alarms)
                                                      ├──→ Task 2 (Metrics Lambda)
                                                      └──→ Task 13 (SendGrid)

Task 10 (CORS) ──→ Task 15 (Frontend SSE Migration)

[Phase 2 complete] ──→ Task 11 (Canary) ──→ [14 days healthy] ──→ Tasks 6, 7, 9 (Logging Removal) ──→ Task 12 (Audit)
                   └──→ Tasks 8, 16, 17 (Monitoring) — runs in parallel with canary accumulation
```

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| ADOT Extension crash mid-stream (span-loss vector #2) | Span data loss for 5-15 min | FR-196/FR-200: Canary detection + pre-adot-baseline rollback image (FR-110) |
| ADOT exporter backend error (span-loss vector #4) | Spans dropped silently on persistent X-Ray 429/500 | FR-201: Canary detects degraded export state; daily cost anomaly alarm (FR-161) |
| force_flush() hangs indefinitely | Lambda timeout, span loss | FR-139: 2500ms thread wrapper + OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2000 |
| 500 TPS X-Ray quota exceeded | Silent data loss | FR-178: Service Quotas increase request + monitoring alarm |
| Frontend EventSource→fetch migration breaks SSE | User-facing streaming failure | Task 15: Comprehensive reconnection logic + Playwright gate |
| Annotation budget overflow (>50/trace) | Diagnostic data truncated silently | FR-186/FR-193: Budget-aware allocation with 3 reserved exception slots; CI gate for annotation key validation |
| OTel SDK v1.39.1 incompatibility | Build failure | FR-101: Pin all core packages to identical version |
| Dual-emit period too short | Remove logging before X-Ray verified | FR-109: Hard 2-week minimum with 4 verification gates |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|-----------|--------------------------------------|
| SSE Lambda 512→1024MB | ADOT Extension ~80MB overhead | Cannot use Lambda Layers (container-based); no lighter OTel exporter exists |
| Dual tracing framework (Powertools + OTel) | RESPONSE_STREAM closes X-Ray segment before streaming | begin_segment() is no-op in Lambda; no single SDK handles both phases |
| ~35 CloudWatch alarms | 6 Lambdas × (error + latency + memory) + 7 silent failure + canary + cost + ADOT | Individual alarms needed for targeted alerting; composite alarm covers severity tiers |
| Custom bootstrap modification | Warm invocation trace ID propagation | Lambda runtime doesn't update _X_AMZN_TRACE_ID on warm starts |
