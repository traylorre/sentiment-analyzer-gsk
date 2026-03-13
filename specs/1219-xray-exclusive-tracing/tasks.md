# Tasks: X-Ray Exclusive Tracing

**Input**: Design documents from `/specs/1219-xray-exclusive-tracing/`
**Prerequisites**: plan.md (19 tasks, 6 phases), spec.md (Round 26, 209 FRs, ~150 SCs), data-model.md, contracts/ (4 contracts), research.md, quickstart.md
**Clarifications Applied**: Session 2026-03-12 (5 Q&As: sampling attack, deploy granularity, dual-emit policy, canary scope, testing strategy)

**Organization**: Tasks follow the plan's deployment phase ordering (technical dependencies) with user story tags for traceability. Each plan task is an independently deployable PR (clarification Q2). Tests included where spec defines explicit SCs with test criteria (Q5: shared unit test pattern for Powertools migration, dedicated integration for Tasks 4/13).

**User Stories** (from spec.md):
- **US1** (P1): End-to-end request tracing
- **US2** (P1): Silent failure diagnostics
- **US3** (P2): SSE streaming latency/cache in X-Ray
- **US4** (P2): Browser-to-backend trace correlation
- **US5** (P3): Replace custom correlation IDs
- **US6** (P3): X-Ray canary health validation
- **US7** (P2): Metrics Lambda instrumentation
- **US8** (P1): Guaranteed error trace capture
- **US9** (P2): Trace data integrity protection
- **US10** (P1): Alerting for all failure modes
- **US11** (P1): Meta-observability for monitoring infrastructure

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in same phase (different files, no dependencies)
- **[Story]**: User story this task satisfies (US1-US11)
- Plan task references in section headers for traceability

---

## Phase 1: Setup

**Purpose**: Feature branch, dependencies, clean state verification

- [x] T001 Create feature branch `1219-xray-exclusive-tracing` from latest origin/main and verify clean state (`make validate`)
- [x] T002 [P] Add `aws-lambda-powertools[tracer]` to pyproject.toml dependencies if not already present; run `pip install -e ".[dev]"` to verify
- [x] T003 [P] Add OTel SDK dependencies to src/lambdas/sse_streaming/requirements.txt: `opentelemetry-api==1.39.1`, `opentelemetry-sdk==1.39.1`, `opentelemetry-exporter-otlp-proto-http==1.39.1`, `opentelemetry-instrumentation-aws-lambda==0.45b0`, `opentelemetry-propagator-aws-xray==1.0.2`, `opentelemetry-sdk-extension-aws==2.0.2` (FR-101: all core packages pinned to identical version)

---

## Phase 2: Foundation -- Plan Tasks 1, 19

**Purpose**: IAM permissions and Service Quotas -- BLOCKS all instrumentation work

**CRITICAL**: No instrumentation task can proceed until X-Ray IAM permissions are deployed. Missing `GetSampling*` actions cause SILENT fallback to 1 trace/sec (FR-159).

- [x] T004 [US1] Create `aws_iam_policy` resource for X-Ray permissions in infrastructure/terraform/modules/iam/main.tf: 5 actions (`xray:PutTraceSegments`, `PutTelemetryRecords`, `GetSamplingRules`, `GetSamplingTargets`, `GetSamplingStatisticSummaries`) with `Resource = "*"` per contracts/xray-groups-sampling.md (Amendment 1.8: managed policy, no inline)
- [x] T005 [US1] Add `aws_iam_role_policy_attachment` for X-Ray policy to Ingestion, Analysis, Dashboard, Metrics Lambda execution roles in infrastructure/terraform/modules/iam/main.tf (4 attachments)
- [ ] T006 [P] [US9] File AWS Service Quotas increase request for `xray:PutTraceSegments` 500 to 1000 TPS in target region (FR-178: projected peak ~520 TPS exceeds 500 default). Can be Terraform `aws_servicequotas_service_quota` or manual console request
- [ ] T007 [US1] Run `terraform plan` on infrastructure/terraform/ to validate IAM changes -- verify 4 roles gain 5 X-Ray actions with zero permission regressions

**Gate**: All 4 existing Lambda execution roles verified with 5 X-Ray actions (FR-159).

---

## Phase 3: Tracer Standardization -- Plan Task 14

**Purpose**: Migrate all `@xray_recorder.capture()` decorators to Powertools `@tracer.capture_method` across 12 source files, 6 Lambdas. Foundation for all per-Lambda instrumentation.

**User Stories Served**: US1 (end-to-end tracing), US2 (subsegment error annotations), US7 (Metrics Lambda)

**Independent PR**: task-14-powertools-standardization

### Ingestion Lambda

- [x] T008 [P] [US1] Migrate src/lambdas/ingestion/handler.py: replace `from aws_xray_sdk.core import xray_recorder` with `from aws_lambda_powertools import Tracer`; init `tracer = Tracer(service="sentiment-analyzer-ingestion")`; add `@tracer.capture_lambda_handler` on handler; migrate all `@xray_recorder.capture()` to `@tracer.capture_method`
- [x] T009 [P] [US1] Migrate xray_recorder decorators in src/lambdas/ingestion/self_healing.py to `@tracer.capture_method`

### Analysis Lambda

- [x] T010 [P] [US1] Migrate src/lambdas/analysis/handler.py: replace xray_recorder with `Tracer(service="sentiment-analyzer-analysis")`; migrate all decorators; add FR-206 deadline-aware early return between resolution iterations -- check remaining time, close current subsegment with `flush_reason = "deadline"` annotation if remaining < threshold, then return

### Dashboard Lambda

- [x] T011 [P] [US1] Clean up src/lambdas/dashboard/handler.py: Powertools Tracer already initialized -- REMOVE redundant `patch_all()` call (FR-030: eliminates double-patching of boto3 and requests)
- [x] T012 [P] [US1] Migrate xray_recorder decorators in src/lambdas/dashboard/auth.py, src/lambdas/dashboard/alerts.py, src/lambdas/dashboard/notifications.py, src/lambdas/dashboard/quota.py to `@tracer.capture_method`

### Notification Lambda

- [x] T013 [P] [US1] Migrate src/lambdas/notification/handler.py: replace xray_recorder with `Tracer(service="sentiment-analyzer-notification")`; migrate all decorators
- [x] T014 [P] [US1] Migrate xray_recorder decorators in src/lambdas/notification/alert_evaluator.py to `@tracer.capture_method`

### SSE Streaming Lambda

- [x] T015 [P] [US1] Configure Tracer in src/lambdas/sse_streaming/handler.py: `Tracer(service="sentiment-analyzer-sse", auto_patch=False)` per FR-060 -- `auto_patch=False` prevents BotocoreInstrumentor conflict with OTel SDK in streaming phase

### Shared Middleware

- [x] T016 [P] [US1] Migrate xray_recorder decorators in src/lambdas/shared/middleware/auth_middleware.py to `@tracer.capture_method`

### Verification

- [x] T017 [US1] Create shared unit test at tests/unit/test_xray_tracer_standardization.py: verify all 6 Lambda handlers initialize Powertools Tracer (SC-012), verify zero `xray_recorder.capture()` imports remain, verify zero `patch_all()` calls (FR-030), verify exceptions auto-captured by `@tracer.capture_method`
- [x] T018 [US1] Run full-codebase grep to confirm zero remaining raw xray_recorder usage: `grep -r "xray_recorder" src/lambdas/ --include="*.py"` must return zero results (SC-012)

**Checkpoint**: All 6 Lambdas use Powertools Tracer exclusively. Phase 4 instrumentation can now begin.

---

## Phase 4: Per-Lambda Instrumentation -- Plan Tasks 2, 3, 4, 5, 13

**Purpose**: Full X-Ray trace coverage across all Lambdas, silent failure paths, and SSE streaming

**Each task below is an independent PR deployable after Phase 3. All [P] relative to each other.**

### Task 2: Metrics Lambda Instrumentation (US7)

**Independent PR**: task-02-metrics-lambda-xray

- [x] T019 [P] [US7] Add Powertools Tracer to src/lambdas/metrics/handler.py (currently zero X-Ray SDK): `Tracer(service="sentiment-analyzer-metrics")`, `@tracer.capture_lambda_handler` on handler, `@tracer.capture_method` on DynamoDB query and `put_metric_data` functions; add annotations per data-model.md Metrics Lambda schema: `metric_count` (int), `query_duration_ms` (int) (FR-003, FR-004)

### Task 3: SNS Trace Propagation Verification (US1)

**Independent PR**: task-03-sns-propagation-verification

- [ ] T020 [P] [US1] Create preprod verification test at tests/e2e/test_xray_sns_propagation.py: trigger Ingestion Lambda, verify X-Ray trace ID propagates through SNS to Analysis Lambda -- both Lambda segments + SNS connecting segment appear under single trace ID in service map. Use retry-with-backoff (30s then 60s) for X-Ray indexing delay. Blocks Phase 4 deployment on failure (SC-087). Note: `rawMessageDelivery` confirmed disabled (clarification R26)

### Task 13: SendGrid Explicit Subsegment (US1)

**Independent PR**: task-13-sendgrid-subsegment

- [x] T021 [P] [US1] Add explicit X-Ray subsegment for SendGrid API calls in src/lambdas/notification/sendgrid_service.py: wrap urllib/httplib call with `@tracer.capture_method` or manual subsegment, add annotations per data-model.md Notification Lambda schema: `recipient_count` (int), `template_name` (string), `sendgrid_status` (int). SendGrid uses urllib (NOT httpx) -- NOT auto-patched by X-Ray SDK (FR-028)
- [x] T022 [P] [US1] Create integration test at tests/integration/test_xray_sendgrid_subsegment.py: verify SendGrid API call produces subsegment with destination URL containing `api.sendgrid.com` (SC-080)

### Task 4: Silent Failure Path Instrumentation (US2, US10)

**Independent PR**: task-04-silent-failure-instrumentation

Each silent failure path gets: (1) X-Ray error subsegment with exception details, (2) CloudWatch `SilentFailure/Count` metric with `SentimentAnalyzer/Reliability` namespace and `FailurePath` dimension (FR-043, FR-097, FR-142). Both MUST fire on every failure regardless of X-Ray sampling (SC-019).

- [x] T023 [P] [US2] Add X-Ray error subsegment + CloudWatch metric to `circuit_breaker_load` and `circuit_breaker_save` failure paths in src/lambdas/shared/circuit_breaker.py: subsegments named per FR-142 disambiguated names, mark as error with exception, emit `SilentFailure/Count` with `FailurePath` dimension
- [x] T024 [P] [US2] Add X-Ray error subsegment + metric to `audit_trail` failure path in src/lambdas/ingestion/audit.py
- [x] T025 [P] [US2] Add X-Ray error subsegment + metric to `notification_delivery` failure path in src/lambdas/ingestion/notification.py (SNS publish failure)
- [x] T026 [P] [US2] Add X-Ray error subsegment + metric to `fanout_partial_write` failure path in src/lambdas/ingestion/storage.py (BatchWriteItem unprocessed items after retries -- annotation includes count of unprocessed items and affected resolutions)
- [x] T027 [P] [US2] Add X-Ray error subsegment + metric to `self_healing_fetch` failure path in src/lambdas/ingestion/self_healing.py (annotation includes failed source_id)
- [x] T028 [P] [US2] Add X-Ray error subsegment + metric to `parallel_fetcher_aggregate` failure path in src/lambdas/ingestion/parallel_fetcher.py
- [x] T029 [US2] Create integration tests at tests/integration/test_xray_silent_failures.py: inject DynamoDB throttle on circuit breaker table, verify (1) error subsegment present in trace (SC-004), (2) CloudWatch metric emitted with correct namespace and dimensions (SC-019, SC-049)

### Task 5: SSE Lambda ADOT Extension + OTel SDK (US3, US1)

**Independent PR**: task-05-sse-adot-otel

PR scope: 8 subtasks (5a-5h) per plan. Most complex task -- ~675 spans per 15s invocation. Dual tracing framework: Powertools (handler phase) + OTel SDK (streaming phase).

#### Subtask 5a: Dockerfile -- ADOT Extension Embed

- [ ] T030 [US3] Tag current SSE Lambda ECR image as `pre-adot-baseline` with 90-day retention for rollback artifact (SC-060, FR-110)
- [x] T031 [US3] Add ADOT Extension multi-stage build to src/lambdas/sse_streaming/Dockerfile: `COPY --from=public.ecr.aws/aws-observability/aws-otel-lambda-extension-amd64@sha256:{digest} /opt/extensions/ /opt/extensions/` -- collector-only binary at /opt/extensions/collector (FR-062, FR-069, FR-070)
- [x] T032 [P] [US3] Create ADOT collector config at src/lambdas/sse_streaming/collector-config.yaml per contracts/adot-collector-config.yaml: processor-less pipeline (otlp receivers to awsxray exporters), HTTP endpoint `0.0.0.0:4318`. COPY to `/opt/collector-config/config.yaml` in Dockerfile
- [x] T033 [US3] Add `OPENTELEMETRY_COLLECTOR_CONFIG_FILE=/opt/collector-config/config.yaml` env var to Dockerfile or Lambda config

#### Subtask 5b: Bootstrap -- Trace ID + Deadline Propagation

- [x] T034 [US3] Modify src/lambdas/sse_streaming/bootstrap: read `Lambda-Runtime-Trace-Id` header from Runtime API response and update `_X_AMZN_TRACE_ID` env var on EVERY invocation -- warm invocations use stale trace ID without this (FR-092)
- [x] T035 [US3] Modify src/lambdas/sse_streaming/bootstrap: read `Lambda-Runtime-Deadline-Ms` header from Runtime API response and export as env var for proactive flush deadline calculation (FR-103)

#### Subtask 5c: OTel SDK TracerProvider Init

- [x] T036 [US3] Create OTel tracing module at src/lambdas/sse_streaming/tracing.py: module-level TracerProvider singleton per contracts/otel-sdk-config.md -- `AwsXRayIdGenerator`, `AwsLambdaResourceDetector().detect()`, `BatchSpanProcessor(schedule_delay_millis=1000, max_queue_size=1500, max_export_batch_size=64)`, `shutdown_on_exit=False` (FR-052-065, FR-077). Use `os.environ["OTEL_SERVICE_NAME"]` fail-fast (Amendment 1.15)
- [x] T037 [US3] Add `OTEL_SDK_DISABLED` kill switch check in src/lambdas/sse_streaming/tracing.py: if `os.environ.get("OTEL_SDK_DISABLED") == "true"`, skip TracerProvider init entirely -- operable without rebuild (FR-108)
- [x] T038 [US3] Add try/except with structured error attribution around TracerProvider init in src/lambdas/sse_streaming/tracing.py (FR-106)
- [x] T039 [US3] Add `safe_force_flush()` with 2500ms thread wrapper in src/lambdas/sse_streaming/tracing.py per contracts/otel-sdk-config.md force_flush contract: `threading.Thread` with `join(timeout=2.5)`, diagnostic differentiation for ECONNREFUSED vs TCP hang (FR-139, FR-165)

#### Subtask 5d: Per-Invocation Context Extraction

- [x] T040 [US3] Add `extract_trace_context()` function in src/lambdas/sse_streaming/tracing.py per contracts/otel-sdk-config.md: `AwsXRayPropagator.extract()` from `_X_AMZN_TRACE_ID` env var -- MUST run per-invocation, NOT module-level (FR-059, FR-092)
- [x] T041 [US3] Call `extract_trace_context()` at start of handler in src/lambdas/sse_streaming/handler.py; pass returned context to streaming generator for span parenting

#### Subtask 5e: Streaming-Phase Span Creation

- [x] T042 [US3] Add OTel span for DynamoDB poll cycle in src/lambdas/sse_streaming/polling.py: span named `dynamodb_poll` with `SpanKind.CLIENT`, annotations: `item_count`, `changed_count`, `poll_duration_ms`. Add `cache_hit` boolean per-lookup annotation on poll-cycle span (clarification R25: annotate existing span, NOT new subsegment -- avoids ~180 extra subsegments)
- [x] T043 [P] [US3] Add OTel span for SSE event dispatch in src/lambdas/sse_streaming/stream.py: span named `sse_event_dispatch` with `SpanKind.INTERNAL`, annotations: `event_type`, `latency_ms`
- [x] T044 [P] [US3] Add OTel span for CloudWatch put_metric_data in src/lambdas/sse_streaming/metrics.py: span named `cloudwatch_put_metric` with `SpanKind.CLIENT`
- [x] T045 [US3] Verify `auto_patch=False` on Powertools Tracer (T015) and NO `BotocoreInstrumentor` anywhere in SSE Lambda -- prevents dual-emission during streaming phase (FR-060, FR-076)

#### Subtask 5f: Three-Layer Flush Pipeline

- [x] T046 [US3] Add proactive flush to streaming generator in src/lambdas/sse_streaming/stream.py: on each poll cycle, check remaining time < 3000ms from deadline env var; if true, call `safe_force_flush()`, yield `event: deadline` SSE event with reason, set `flush_fired = True` flag, return. After flush_fired, block further span creation (FR-093, FR-100, FR-149)
- [x] T047 [US3] Add `safe_force_flush()` call in src/lambdas/sse_streaming/handler.py `finally` block: defense-in-depth for non-timeout exits (normal completion, BrokenPipeError). Retained alongside proactive flush (FR-055, FR-139)

#### Subtask 5g: Error Handling -- Dual Status + Exception Recording

- [x] T048 [US3] Add mandatory dual-call error pattern to all 7 SSE silent failure try/except blocks in src/lambdas/sse_streaming/: every caught exception MUST call BOTH `span.set_status(StatusCode.ERROR, str(exception))` AND `span.record_exception(exception)` as first two statements in except block. Without both, X-Ray shows `fault: false` (FR-144, FR-150)
- [x] T049 [US3] Create CI gate at scripts/check-dual-error-pattern.sh: grep all `except` blocks within OTel span context in src/lambdas/sse_streaming/ for both `set_status` and `record_exception` calls (SC-100)

#### Subtask 5h: BrokenPipeError Handling

- [x] T050 [US3] Add BrokenPipeError catch in streaming generator in src/lambdas/sse_streaming/stream.py: set `client.disconnected = true` annotation on current span, set span status `OK` (NOT ERROR -- client disconnect is not server fault), proceed to `finally` block for flush (FR-085, SC-039)

#### SSE Infrastructure Changes

- [x] T051 [US3] Update SSE Lambda config in infrastructure/terraform/modules/lambda/main.tf: memory 512 to 1024MB (ADOT Extension ~80MB overhead), add env vars: `OTEL_SERVICE_NAME=sentiment-analyzer-sse`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`, `OTEL_SDK_DISABLED=false`, `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2` per contracts/otel-sdk-config.md
- [x] T052 [US3] Add X-Ray IAM policy attachment for SSE Lambda execution role in infrastructure/terraform/modules/iam/main.tf if not already covered by T005

#### SSE Tests

- [x] T053 [US3] Create unit tests at tests/unit/sse_streaming/test_xray_otel_tracing.py: verify TracerProvider singleton across multiple invocations (SC-027), verify per-invocation context extraction uses current trace ID not stale (SC-026), verify span names and attributes match data-model.md schema, verify `flush_fired` flag blocks new span creation (FR-149), verify `OTEL_SDK_DISABLED=true` skips all tracing
- [x] T054 [US3] Create integration test at tests/integration/test_xray_sse_flush.py: mock OTLP endpoint on :4318 (simple HTTP server accepting protobuf), verify `safe_force_flush()` delivers all buffered spans within 2500ms timeout, verify created-vs-exported span count match (SC-040 amended)

**Gate**: SC-110 (>=95% streaming span retention in preprod), FR-158 (SSE cold start P95 <2000ms at 1024MB -- SC-108), SC-072 (preprod rollback drill: kill switch <5 min, full image rollback <15 min)

---

## Phase 5: Frontend Migration -- Plan Tasks 10, 15

**Purpose**: Browser-to-backend trace correlation via fetch()+ReadableStream

**NOTE**: This phase is INDEPENDENT of Phases 3-4. Can start after Phase 2 (Foundation). Task 10 (CORS) has no dependency on Powertools migration.

### Task 10: CORS Headers (US4)

**Independent PR**: task-10-cors-trace-headers

- [x] T055 [P] [US4] Add `X-Amzn-Trace-Id` to `Access-Control-Allow-Headers` for API Gateway in infrastructure/terraform/modules/api_gateway/ (FR-014)
- [x] T056 [P] [US4] Add `X-Amzn-Trace-Id` to `Access-Control-Allow-Headers` for Lambda Function URL in infrastructure/terraform/modules/lambda/ (FR-015)
- [x] T057 [P] [US4] Add `X-Amzn-Trace-Id` to `Access-Control-Expose-Headers` in both API Gateway and Function URL -- allows frontend to read response trace ID (FR-016)

### Task 15: Frontend SSE Client Migration (US4)

**Independent PR**: task-15-frontend-sse-fetch-migration

**Rollback**: If fetch() migration causes streaming failures, revert Task 15 changes via `git revert`. Task 10 CORS changes remain compatible with both EventSource and fetch() implementations.

#### Subtask 15a: SSE Text Protocol Parser

- [x] T058 [US4] Create SSE text protocol parser at frontend/src/lib/api/sse-parser.ts: parse `retry:`, `data:`, `id:`, `event:` fields per SSE spec. Server emits `retry: 3000\n` as first field (FR-088, FR-089)

#### Subtask 15b: Connection State Machine

- [x] T059 [US4] Create connection state machine at frontend/src/lib/api/sse-connection.ts: states `connected`, `reconnecting`, `disconnected`, `error`; 4 error categories per FR-118 (graceful close, abnormal termination, network error, intentional cancellation) with distinct strategies per category

#### Subtask 15c: Reconnection with Exponential Backoff

- [x] T060 [US4] Add exponential backoff + jitter reconnection in frontend/src/lib/api/sse-connection.ts: `Last-Event-ID` header propagation (FR-081), `session_id` generation (FR-048), `connection_sequence` counter, `previous_trace_id` extracted from response headers (FR-033)

#### Subtask 15d: Trace Header Injection

- [x] T061 [US4] Add `X-Amzn-Trace-Id` header to all SSE fetch() calls in frontend/src/lib/api/sse.ts (FR-032). Check if CloudWatch RUM is deployed before implementing FR-148 (5s FetchPlugin wait): if no `window.cwr` global or no RUM CDN script, skip wait entirely (YAGNI per plan)

#### Subtask 15e-f: TextDecoder + AbortController

- [x] T062 [P] [US4] Add TextDecoder streaming mode in frontend/src/lib/api/sse.ts: `new TextDecoder('utf-8', {stream: true})` for multi-byte UTF-8 chunk boundary handling (FR-099)
- [x] T063 [P] [US4] Add AbortController for stream cancellation in frontend/src/lib/api/sse.ts: pass `AbortSignal` to fetch() for clean teardown on component unmount or navigation

#### Subtask 15g: trace_id in SSE Payload

- [x] T064 [US4] Add `trace_id` field to SSE event JSON data payload in src/lambdas/sse_streaming/stream.py: include current X-Ray trace ID in each SSE event for frontend logging correlation (FR-115)

#### Frontend Integration

- [ ] T065 [US4] Migrate frontend/src/hooks/use-sse.ts from EventSource API to new fetch()+ReadableStream SSE client: wire up parser, state machine, reconnection, and AbortController
- [ ] T066 [US4] Update frontend/src/lib/api/sse.ts: replace existing EventSource usage with fetch()+ReadableStream implementation, preserving existing API surface for consumers
- [ ] T067 [US4] Update frontend/src/app/api/sse/ route handler: propagate `X-Amzn-Trace-Id` header from incoming request to upstream SSE Lambda Function URL call
- [ ] T068 [US4] Create Playwright test for frontend trace propagation: verify `X-Amzn-Trace-Id` header present on all SSE fetch() calls (SC-085)

**Gate**: SC-085 (Playwright: X-Amzn-Trace-Id on all fetch() calls), FR-135 (frontend trace correlation verified)

---

## Phase 6: Post-Instrumentation -- Plan Tasks 11, 16, 17, 8

**Purpose**: Canary deployment (starts 14-day clock), monitoring infrastructure, SSE annotations

**CRITICAL**: Task 11 (canary) MUST deploy immediately after Phase 4 to start the 14-day healthy baseline required by FR-109 before logging removal can begin. Do NOT delay canary for alarm perfectionism.

**All tasks below are [P] relative to each other** -- independent PRs, independent infrastructure.

### Task 16: X-Ray Groups, Sampling Rules, Cost Guards (US8, US9)

**Independent PR**: task-16-xray-groups-sampling

- [x] T069 [P] [US8] Create Terraform module at infrastructure/terraform/modules/xray/main.tf: define 5 X-Ray Groups per contracts/xray-groups-sampling.md -- `sentiment-errors` (`fault = true OR error = true`), `production-traces` (`!annotation.synthetic`), `canary-traces` (`annotation.synthetic = true`), `sentiment-sse` (`service("sentiment-analyzer-sse")`), `sse-reconnections` (`annotation.previous_trace_id BEGINSWITH "1-"`) -- all with `insights_enabled = true` (FR-111)
- [x] T070 [P] [US8] Add X-Ray sampling rules in infrastructure/terraform/modules/xray/main.tf per contracts/xray-groups-sampling.md: dev/preprod `reservoir=1, rate=1.0` (100%), prod rules `sentiment-prod-apigw` (priority 100, rate 0.10), `sentiment-prod-fnurl` (priority 200, rate 0.05), `sentiment-prod-default` (priority 9000, rate 0.10) (FR-034, FR-161)
- [x] T071 [P] [US8] Create infrastructure/terraform/modules/xray/variables.tf: parameterize `reservoir_size` and `fixed_rate` per environment for sampling graduation (FR-179: 4-phase plan)
- [x] T072 [P] [US8] Create infrastructure/terraform/modules/xray/outputs.tf: expose group ARNs and sampling rule names for alarm references
- [x] T073 [US8] Wire xray module into infrastructure/terraform/main.tf: add module call with environment-specific sampling variables

### Task 17: CloudWatch Alarms -- Phase 1 (US10)

**Independent PR**: task-17-cloudwatch-alarms-phase1

Phase 1: ~18 high-signal alarms ($1.80/mo). Phase 2 adds ~20 more post-dual-emit (see T111).

- [ ] T074 [P] [US10] Create Terraform module at infrastructure/terraform/modules/cloudwatch-alarms/main.tf: 6x Lambda error alarms per contracts/cloudwatch-alarms.md Category 1 -- one per Lambda, `Errors > threshold`, `treat_missing_data = "missing"` (FR-040, FR-162)
- [ ] T075 [P] [US10] Add 6x Lambda latency P95 alarms in infrastructure/terraform/modules/cloudwatch-alarms/main.tf: Phase 1 thresholds at 80% of timeout per contracts/cloudwatch-alarms.md Category 2 (FR-041, FR-128)
- [ ] T076 [P] [US10] Add specialty alarms in infrastructure/terraform/modules/cloudwatch-alarms/main.tf: canary heartbeat (`treat_missing_data = "breaching"`, FR-121), X-Ray cost anomaly (FR-161), composite `SilentFailure/Count` `SUM > 0` (FR-134), ADOT export failure metric filter (FR-098), API Gateway IntegrationLatency P99 (FR-138), SSE memory utilization 85% (FR-104)
- [ ] T077 [P] [US10] Create composite alarm combining all Critical-tier alarms (FR-129)
- [ ] T078 [P] [US10] Add dashboard alarm status widget with severity-tiered layout in infrastructure/terraform/modules/monitoring/ (FR-129, FR-141)
- [ ] T079 [US10] Create infrastructure/terraform/modules/cloudwatch-alarms/variables.tf: parameterize all thresholds for Phase 2 tightening (FR-041)
- [ ] T080 [US10] Wire cloudwatch-alarms module into infrastructure/terraform/main.tf

### Task 11: X-Ray Canary Lambda (US6, US9, US11)

**Independent PR**: task-11-xray-canary

All 17 FRs kept as MUST (clarification Q4). Implementation ordered: core then CloudWatch health then cross-region then hardening.

#### Core Canary

- [ ] T081 [US6] Create src/lambdas/canary/__init__.py and src/lambdas/canary/handler.py: `Tracer(service="sentiment-analyzer-canary")`, submit test traces, query GetTraceSummaries, calculate completeness_ratio (FR-019, FR-113)
- [ ] T082 [US6] Add canary health metric emission: CloudWatch put_metric_data for CanaryHealth and completeness_ratio, `synthetic = true` annotation (FR-036, FR-185)
- [ ] T083 [US6] Add retry logic with backoff for GetTraceSummaries (FR-078)

#### CloudWatch Health Check

- [ ] T084 [US11] Add CloudWatch put_metric_data + GetMetricData verification loop (FR-049, FR-050)

#### Cross-Region SNS Alerting

- [ ] T085 [P] [US11] Create cross-region SNS topic for out-of-band canary alerting (FR-136)

#### Canary Infrastructure

- [ ] T086 [US6] Create canary IAM role SEPARATE from application Lambda roles in infrastructure/terraform/modules/iam/main.tf (FR-051)
- [ ] T087 [US6] Add EventBridge 5-minute schedule rule in infrastructure/terraform/modules/eventbridge/ (FR-122)
- [ ] T088 [US6] Add canary Lambda resource in infrastructure/terraform/modules/lambda/main.tf

#### Operational Hardening

- [ ] T089 [US6] Add SSM parameter state persistence for consecutive failure tracking (FR-112, FR-146)
- [ ] T090 [US6] Add canary exemption from FR-018 fail-fast -- must complete even when X-Ray broken (FR-145)
- [ ] T091 [US6] Add API Gateway probe: HTTP GET to Dashboard endpoint, validate trace structure (FR-207)
- [ ] T092 [US6] Create rollback runbook at docs/x-ray/runbook-rollback.md (FR-110, SC-072)

### Task 8: SSE Connection/DynamoDB Annotations (US3)

**Independent PR**: task-08-sse-annotations (depends on Task 5)

- [x] T093 [US3] Add connection_id, session_id, previous_trace_id, connection_sequence annotations in src/lambdas/sse_streaming/connection.py (FR-008)
- [x] T094 [US3] Add cache_hit_rate aggregate annotation in src/lambdas/sse_streaming/polling.py (FR-009)

---

## Phase 7: Verification & Logging Removal -- Plan Tasks 18, 6, 7, 9, 12

**CRITICAL**: CANNOT begin until canary reports healthy for 14 consecutive days (FR-109). Gate failure resets clock (clarification Q3).

### Task 18: Verification Gate Scripts (US1)

- [x] T095 [US1] Create scripts/verify-dual-emit.py with 4 gate functions: verify_trace_structure(), verify_annotation_parity(), verify_service_map(), verify_trace_sample() (FR-109, FR-152)
- [x] T096 [US1] Add `make verify-dual-emit` target in Makefile
- [x] T097 [US1] Add accumulation tracking with clock reset on gate failure (clarification Q3)

### Task 6: Remove latency_logger.py (US5)

- [ ] T098 [US5] Delete src/lambdas/sse_streaming/latency_logger.py and all references (FR-022)
- [ ] T099 [US5] Verify zero remaining references via grep

### Task 7: Remove cache_logger.py (US5)

- [ ] T100 [US5] Delete src/lambdas/sse_streaming/cache_logger.py and all references (FR-023)
- [ ] T101 [US5] Verify zero remaining references via grep

### Task 9: Remove Custom Correlation IDs (US5)

- [ ] T102 [US5] Remove get_correlation_id() and generate_correlation_id() from src/lib/metrics.py (FR-024)
- [ ] T103 [US5] Update src/lib/deduplication.py to use X-Ray trace ID
- [ ] T104 [US5] Verify zero remaining references via grep

### Task 12: Downstream Consumer Audit (US1)

- [ ] T105 [US1] Audit all downstream consumers of removed systems (FR-018)
- [ ] T106 [US1] Update CloudWatch Logs Insights queries and dashboards

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T107 [P] Add CI gate scripts/check-annotation-pii.sh (FR-184)
- [x] T108 [P] Add CI gate scripts/check-annotation-budget.sh (FR-193)
- [ ] T109 [P] Run quickstart.md validation
- [ ] T110 [P] Run `make validate`
- [ ] T111 [US10] Add Phase 2 CloudWatch alarms (~20 additional) with tightened thresholds (FR-042, FR-044)
- [x] T112 [P] Add Makefile targets for annotation CI gates

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  |
  v
Phase 2 (Foundation) ----+----> Phase 3 (Tracer) ----> Phase 4 (Instrumentation) ----> Phase 6 (Canary+Monitoring)
                          |                                                                    |
                          +----> Phase 5 (Frontend)                                    [14 days healthy]
                                                                                               |
                                                                                               v
                                                                                Phase 7 (Removal) ----> Phase 8 (Polish)
```

### Critical Path

```
T001 -> T004-T005 -> T008-T018 -> T030-T054 (SSE ADOT) -> T081-T092 (Canary) -> [14 days] -> T098-T106 (Removal)
```

### User Story Dependencies

| Story | Can Start After | Depends On |
|-------|----------------|------------|
| US1 | Phase 2 | None |
| US2 | Phase 3 | US1 |
| US3 | Phase 3 | US1 |
| US4 | Phase 2 | None (independent frontend track) |
| US5 | Phase 7 (14-day gate) | US1, US2, US3 |
| US6 | Phase 4 | US1 |
| US7 | Phase 3 | US1 |
| US8 | Phase 2 | None |
| US9 | Phase 4 | US6 |
| US10 | Phase 4 | US2 |
| US11 | Phase 4 | US6, US9 |

---

## Implementation Strategy

### MVP First (US1)
1. Phases 1-3 + Task 2,3 -> end-to-end tracing works

### Incremental Delivery
1. MVP -> US1
2. +Task 4 -> US2 (silent failures)
3. +Task 5 -> US3 (SSE streaming)
4. +Tasks 10,15 -> US4 (frontend)
5. +Tasks 16,17 -> US8, US10 (sampling, alarms)
6. +Task 11 -> US6, US9, US11 (canary) -- starts 14-day clock
7. +Tasks 18,6,7,9,12 -> US5 (cleanup after 14 days)

### Cost: ~$8.78/mo total (10% SSE sampling)

## Notes

- Each plan task = independent PR (clarification Q2)
- Gate failure resets 14-day clock (clarification Q3)
- All 17 canary FRs MUST (clarification Q4)
- Test strategy: shared unit + dedicated integration for Tasks 4/13 (clarification Q5)
- Superseded FRs: FR-075, FR-090, FR-074, SC-031, SC-044 (ADOT processor-less)
- ~75 implementation-design FRs are guidance, not hard acceptance tests
