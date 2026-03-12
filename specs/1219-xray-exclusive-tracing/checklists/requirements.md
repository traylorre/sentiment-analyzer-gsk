# Specification Quality Checklist: X-Ray Exclusive Tracing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-02-14
**Feature**: [spec.md](../spec.md)
**Validation Iterations**: 20 (initial draft + round 1 review + round 2 deep-dive + round 3 blind spot analysis + round 4 audit gap analysis + round 5 ADOT architecture deep-dive + round 6 blind spot fixes + round 7 ADOT operational lifecycle deep-dive + round 8 container-based deployment blind spot analysis + round 9 four-domain deep research + round 10 canonical-source blind spot analysis + round 11 bootstrap & deadline safety + round 12 deployment safety & operational lifecycle + round 13 deployment safety & migration observability + round 14 export safety & operational completeness + round 15 silent failure instrumentation & alarm calibration + round 16 alarm completeness & frontend verification gates + round 17 OTel error status & canary resilience + round 20 operational reality & process integrity + round 21 span-loss vector reclassification & operational hardening + round 22 sampling graduation, operational procedures & PII prevention)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Review Issues Addressed (Round 1 — Iteration 2)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 1 | BLOCKER | FR-013 prescribed manual SNS MessageAttributes; AWS handles this automatically with Active tracing | Rewrote FR-013 to verify Active tracing on both Lambdas; updated Assumptions section |
| 2 | HIGH | FR-003 prescribed `patch_all()` implementation detail | Rewrote to describe observable outcome (auto-instrumented subsegments) |
| 3 | HIGH | FR-017 named specific IAM managed policy | Rewrote to describe permissions outcome without policy name |
| 4 | HIGH | FR-022/FR-023 offered ambiguous alternatives (delete vs adapter) | Removed adapter option; MUST delete module and call sites |
| 5 | HIGH | FR-018 was untestable code-level constraint | Reframed as observable behavior (errors propagate to runtime) |
| 6 | HIGH | Missing edge case: X-Ray annotation limits | Added edge case with 50/subsegment limit and overflow strategy |
| 7 | MEDIUM | FR-006/FR-007 vs FR-012 contradiction | Clarified FR-012 applies to operational logs that survive; tracing-specific logs removed |
| 8 | MEDIUM | SC items referenced "X-Ray console" tool | Removed tool references; described observable outcomes |
| 9 | MEDIUM | Missing edge case: downstream consumers of removed systems | Added edge case requiring audit of alarms/dashboards/saved queries |
| 10 | MEDIUM | FR-021 scope too broad (implied removing all logging) | Scoped to tracing/correlation mechanisms; operational logging explicitly excluded |
| 11 | MEDIUM | Missing edge case: sampling rate vs coverage claims | Added edge case; qualified SC-001 with "sampled requests"; added sampling config note |
| 12 | MEDIUM | Assumption referenced specific library version | Removed version-specific detail |
| 13 | LOW | Browser vs proxy trace ID generation boundary unclear | Clarified in edge cases: browsers generate, proxies forward |
| 14 | LOW | FR-016 untestable with probabilistic RUM | Added "in test environments where RUM sampling is 100%" qualifier |
| 15 | NITPICK | SC-008 and SC-009 redundant | Merged into single SC-008; renumbered |
| 16 | NITPICK | SC-004 referenced "7 of 7" without enumerating | Enumerated all 7 paths in both FR-002 and SC-004 |

## Emergent Issues Found (Round 2 — Deep-Dive)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 17 | BLOCKER | SSE Lambda uses RESPONSE_STREAM invoke mode; X-Ray segment closes before streaming begins; all streaming subsegments orphaned | Added FR-025/FR-026/FR-027 for independent segment creation during streaming; updated FR-001, US3, edge cases |
| 18 | BLOCKER | `asyncio.new_event_loop()` in async-to-sync bridge loses X-Ray context; auto-patched boto3 calls have no parent segment | Added FR-025 requiring explicit trace context propagation into new event loop; added edge case |
| 19 | HIGH | SendGrid SDK uses `urllib`/`python-http-client`, NOT httpx — `patch_all()` does NOT auto-patch urllib | **Invalidated** Assumption 1; added FR-028 requiring explicit SendGrid subsegment; updated US1 scenario 3 |
| 20 | HIGH | 57 raw `@xray_recorder.capture` decorators do NOT auto-capture exceptions; only Powertools `@tracer.capture_method` does | Added FR-029/FR-030 for tracer standardization; added edge case explaining the gap |
| 21 | HIGH | Dashboard Lambda double-patches boto3 (explicit `patch_all()` + Tracer `auto_patch=True`) | Added FR-030 requiring single patching mechanism per Lambda |
| 22 | MEDIUM | X-Ray annotation types confirmed: str/int/float/bool only; None silently dropped | Added edge case; added assumption documenting valid types |

## Emergent Issues Found (Round 3 — Blind Spot Analysis)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 23 | **BLOCKER** | `begin_segment()` is a no-op in Lambda — `LambdaContext.put_segment()` silently discards segments; `FacadeSegment` raises `FacadeSegmentMutationException` on all mutations. The "Two-Phase Architecture" (Round 2 FR-026/FR-027) is **INVALID** | **Invalidated** Assumption 7; **replaced** FR-026 with independent lifecycle tracing mechanism (Lambda Extension); **replaced** FR-027 with streaming service call capture; updated US3, SC-010, edge cases. Source: `aws_xray_sdk/core/lambda_launcher.py:55-59` |
| 24 | **BLOCKER** | Powertools `@tracer.capture_method` silently mishandles async generators — `inspect.isasyncgenfunction()` is never called; falls through to `_decorate_sync_function()` wrapping creation (near-zero time) not iteration | Added FR-031 prohibiting `@tracer.capture_method` on async generators; added edge case. Source: `aws_lambda_powertools/tracing/tracer.py` |
| 25 | **BLOCKER** | `EventSource` API does not support custom HTTP headers (WHATWG HTML Living Standard Section 9.2); RUM auto-injection only patches `fetch()` not `EventSource` | Added FR-032 (fetch()+ReadableStream SSE client), FR-033 (reconnection logic); updated US4, SC-015; added edge case and assumption |
| 26 | HIGH | Clients can force 100% X-Ray sampling via `Sampled=1` header — cost amplification vector at $5/million traces | Added FR-035 (server-side sampling defense); added edge case |
| 27 | HIGH | X-Ray has no native "guaranteed capture on error" mode — sampling decided before request outcome | Added US8 (Guaranteed Error Trace Capture, P1); added FR-034 (sampling strategy with X-Ray Groups for error filtering); added SC-013 |
| 28 | HIGH | X-Ray silently drops data at 2,600 segments/sec region limit — `UnprocessedTraceSegments` lost, no alert | Added US9 (Trace Data Integrity Protection, P2); added FR-036 (data loss detection via canary); updated FR-019 (batch test traces); added SC-014; added edge case and assumption |
| 29 | MEDIUM | X-Ray SDK `AsyncContext` uses `TaskLocalStorage` that loses context across event loop boundaries; `threading.local()` default works correctly | **Revised** FR-025 (corrected — `threading.local()` DOES propagate, `AsyncContext` DOES NOT); added FR-037 (AsyncContext prohibition); revised edge case. Source: aws-xray-sdk-python issues #164, #310, #446 |
| 30 | MEDIUM | No cost guard for X-Ray at 100% sampling ($5/million traces, scaling linearly) | Added FR-038 (cost budget alarms at $10/$25/$50); added SC-016; added edge case for scaling path (tail-based sampling) |
| 31 | LOW | ADOT Lambda Extension adds 40-60MB + 50-200ms cold start to SSE Lambda | Documented in assumption and edge case; impact acceptable for 15-second streaming lifecycle |

## Emergent Issues Found (Round 4 — Audit Gap Analysis)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 32 | HIGH | SSE Streaming Lambda and Metrics Lambda have ZERO CloudWatch error alarms — operators never alerted to failures (audit Section 4.3) | Added US10 (Operational Alarm Coverage, P1); added FR-040 (error alarms), FR-041 (latency alarms); added SC-017 |
| 33 | HIGH | 7 custom metrics emitted without alarms (StuckItems, ConnectionAcquireFailures, EventLatencyMs, MetricsLambdaErrors, HighLatencyAlert, PollDurationMs, AnalysisErrors) — audit Section 4.2 | Added FR-042 (custom metric alarms); added SC-018 |
| 34 | HIGH | X-Ray Groups only operate on already-sampled traces — at production sampling <100%, error monitoring via trace data misses unsampled errors; unsampled traces permanently lost (Sampled=0 data never sent) | Added FR-039 (scope clarification: X-Ray exclusive for TRACING, not ALARMING); added FR-043 (dual instrumentation: X-Ray + CloudWatch metrics on silent failure paths); added SC-019; added 2 edge cases |
| 35 | HIGH | CloudWatch `put_metric_data` failure makes all `treat_missing_data=notBreaching` alarms false-green — "the single most dangerous blind spot" per audit Section 8.1 | Added US11 (Meta-Observability, P1); added FR-049 (canary verifies CloudWatch emission), FR-050 (out-of-band alerting), FR-051 (separate IAM role); added SC-021. Source: AWS Well-Architected Operational Excellence Pillar |
| 36 | MEDIUM | ADOT auto-instrumentation (`AWS_LAMBDA_EXEC_WRAPPER`) conflicts with Powertools Tracer — double-patches botocore, duplicates handler wrapping and spans | Added FR-046 (no ADOT auto-instrumentation on SSE Lambda), FR-047 (matching service names); added 2 edge cases and 2 assumptions |
| 37 | MEDIUM | X-Ray has no native span links — SSE reconnection creates disconnected traces with no correlation mechanism | Added FR-048 (session_id + previous_trace_id annotations); added SC-020; added edge case |
| 38 | MEDIUM | CloudWatch dashboard alarm widget shows only 6 of 30+ alarms — operators get false "all green" view (audit Section 6.3) | Added FR-044 (widget completeness); added SC-022 |
| 39 | MEDIUM | `treat_missing_data` configuration inconsistency — some absence-indicates-failure alarms may use `notBreaching` | Added FR-045 (audit and correct treat_missing_data across all alarms) |
| 40 | LOW | CloudFront removed from architecture (Features 1203-1207) — Blind Spot 4 from initial gap analysis NOT applicable; documented as edge case if re-introduced | Added edge case and assumption; CloudFront treats `X-Amzn-Trace-Id` as restricted header |
| 41 | LOW | CloudWatch metric ingestion delay (60-120s) affects canary's CloudWatch health check window | Documented in assumption; canary query window must account for delay |

## Emergent Issues Found (Round 5 — ADOT Architecture Deep-Dive)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 42 | **BLOCKER** | OTel SDK on SSE Lambda requires explicit `AwsXRayLambdaPropagator` to read `_X_AMZN_TRACE_ID` — without this, streaming-phase OTel spans carry different trace IDs than the Lambda runtime's X-Ray facade segment, creating disconnected traces (violates SC-010) | Added FR-052 (AwsXRayLambdaPropagator configuration); added SC-023 (unified trace ID verification); added edge case and assumption. Source: `opentelemetry-propagator-aws-xray` package |
| 43 | HIGH | OTel `TracerProvider` MUST use `AwsXRayIdGenerator` — standard `RandomIdGenerator` produces garbage timestamps in X-Ray trace ID epoch field, causing X-Ray to misindex or reject traces by time window | Added FR-053 (AwsXRayIdGenerator requirement); added edge case. Source: `opentelemetry-sdk-extension-aws` package |
| 44 | HIGH | OTel OTLP exporter endpoint (`localhost:4318`) must be explicitly configured — OTel SDK does not auto-discover the ADOT Extension's receiver | Added FR-054 (OTLP endpoint configuration) |
| 45 | HIGH | `BatchSpanProcessor.force_flush()` MUST be called in streaming generator's `finally` block — without it, spans buffered in final batch interval are lost when execution environment freezes, or worse, appear as stale spans in next invocation's traces | Added FR-055 (force_flush requirement); added SC-024 (zero lost spans); added edge case |
| 46 | HIGH | X-Ray segment document size limit is 64KB per `PutTraceSegments` document — large metadata payloads silently rejected with no SDK-level error | Added FR-058 (metadata size guard); added SC-025 (zero rejected documents); added edge case and assumption. Source: AWS X-Ray API Reference |
| 47 | MEDIUM | OTel sampler must be `parentbased_always_on` to honor Lambda runtime's `Sampled=0` — using `always_on` creates orphaned spans for unsampled invocations | Added FR-056 (sampler configuration); added edge case |
| 48 | MEDIUM | 4 specific OTel Python packages required for SSE Lambda streaming instrumentation but not enumerated anywhere in spec or requirements files | Added FR-057 (OTel package enumeration); added assumption for size impact |

## Emergent Issues Found (Round 6 — Blind Spot Fixes)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 49 | HIGH | Warm Lambda invocations reuse execution environment — `_X_AMZN_TRACE_ID` updates per invocation but OTel context extraction only runs at cold start, causing warm invocations to carry stale trace IDs from previous requests | Added FR-059 (per-invocation trace context extraction for warm invocations); added SC-026 (warm invocation trace ID correctness verification); added edge case (warm invocation stale context) and assumption (per-invocation `_X_AMZN_TRACE_ID` update) |
| 50 | HIGH | SSE Lambda with Powertools `auto_patch=True` produces duplicate subsegments — Powertools patches botocore globally and ADOT OTel also instruments botocore, creating double-emission of every AWS SDK call | Added FR-060 (SSE Lambda `auto_patch=False` requirement); added edge case (auto-patching duplicate subsegments) and assumption (Powertools `auto_patch` global persistence) |
| 51 | HIGH | Existing CloudWatch alarms have thresholds set during initial deployment and never recalibrated — traffic patterns changed significantly since original configuration, risking false positives and missed alerts | Added FR-061 (alarm threshold calibration for existing alarms); added edge case (existing alarm threshold inconsistency) |
| 52 | MEDIUM | Lambda execution environment destruction without SHUTDOWN event — Lambda runtime does not guarantee SHUTDOWN lifecycle event; `force_flush()` in generator `finally` block is the only reliable flush mechanism | Added edge case (environment destruction without SHUTDOWN) and assumption (generator `finally` block reliability) |
| 53 | MEDIUM | ADOT OTLP receiver cold start race — ADOT Extension's OTLP receiver may not be ready when Lambda handler sends first spans during cold start, causing early span loss | Added edge case (ADOT cold start race) and assumption (512MB memory adequacy) |

## Emergent Issues Found (Round 7 — ADOT Operational Lifecycle Deep-Dive)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 54 | HIGH | ADOT Lambda Extension has two layer types — collector-only (~35MB) and Python SDK (~80MB); sidecar mode MUST use collector-only to avoid wasting ~45MB on unused auto-instrumentation and risk of accidental activation | Added FR-062 (collector-only layer requirement); added edge case (SDK vs collector-only layer confusion) and assumption (zero current layers) |
| 55 | HIGH | OTel Python SDK `BatchSpanProcessor` silently catches all exporter exceptions (`except Exception`) and `force_flush()` returns `True` regardless of export outcome — no fail-fast mode available by OTel specification design | Added FR-066 (export failure detection gap documentation); added edge case (ADOT Extension crash during streaming) |
| 56 | HIGH | `TracerProvider` created per invocation leaks daemon threads (~1MB each) causing OOM — FR-059 per-invocation requirement ambiguous between context extraction and infrastructure objects | Added FR-065 (TracerProvider singleton lifecycle clarification); added SC-027 (singleton verification); added edge case (per-invocation TracerProvider memory leak) |
| 57 | MEDIUM | ADOT Extension layer ARN not version-pinned — unpinned layers can silently introduce breaking collector schema changes on `terraform apply` | Added FR-063 (version-pinned layer ARN requirement) |
| 58 | MEDIUM | OTel span attributes using non-standard names become non-indexed metadata invisible in X-Ray console default views — DynamoDB and CloudWatch spans would render as generic "unknown remote" nodes | Added FR-067 (OTel semantic conventions for X-Ray mapping); added SC-028 (service map correctness verification) |
| 59 | MEDIUM | ADOT default collector config may include unnecessary components consuming memory | Added FR-064 (collector pipeline verification and custom config option) |
| 60 | LOW | `OTEL_PROPAGATORS` env var creates misleading visible-but-inactive configuration when `set_global_textmap()` overwrites it | Added FR-068 (propagator configuration hygiene); research confirmed `set_global_textmap()` always wins |

## Round 7 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| ADOT collector-only vs SDK layer | **RESOLVED** | FR-062 requires collector-only layer; edge case documents the distinction |
| OTel export failure is silent by design | **RESOLVED** | FR-066 documents the known gap; canary is the detection mechanism |
| TracerProvider singleton lifecycle | **RESOLVED** | FR-065 clarifies module-level singleton; FR-059 scoped to propagate.extract() only |
| ADOT Extension layer version pinning | **RESOLVED** | FR-063 requires version-pinned ARN with per-region mapping |
| OTel semantic conventions for X-Ray | **RESOLVED** | FR-067 specifies required attributes; SC-028 verifies service map rendering |
| ADOT collector pipeline verification | **RESOLVED** | FR-064 requires OTLP receiver + X-Ray exporter verification |
| OTEL_PROPAGATORS env var confusion | **RESOLVED** | FR-068 prohibits setting env var; set_global_textmap() is single source of truth |
| Lambda Layer limit risk | **NOT A RISK** | SSE Lambda uses 0 layers; adding 1 is within 5-layer limit (documented as assumption) |
| X-Ray daemon + ADOT memory budget | **NOT A RISK** | ~76MB combined within 512MB; 15% overhead (documented as assumption) |

## Emergent Issues Found (Round 8 — Container-Based Deployment Blind Spot Analysis)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 61 | **BLOCKER** | SSE Lambda is container-based (ECR image with `python:3.13-slim` + custom bootstrap) — Lambda container images CANNOT use Lambda Layers; FR-062 "collector-only layer" and FR-063 "version-pinned layer ARN" are **INVALID** as written | **REWRITTEN** FR-062 (container-based multi-stage Dockerfile deployment); **REWRITTEN** FR-063 (digest-pinned container image); added FR-069 (Dockerfile ADOT embedding), FR-070 (digest pinning); added SC-029 (ADOT binary in container); added edge case. Round 7 assumption about "zero Lambda layers" and "250MB deployment limit" **INVALIDATED** — SSE Lambda uses 10GB container image limit. Source: AWS Lambda Container Image docs |
| 62 | HIGH | OTel `AwsLambdaResourceDetector` does NOT set `service.name` — defaults to `unknown_service`; X-Ray service map shows all SSE Lambda invocations under `unknown_service` node, breaking SC-028 | Added FR-071 (`OTEL_SERVICE_NAME` env var required, matching `POWERTOOLS_SERVICE_NAME`); added SC-030 (correct service map node naming); added edge case. Source: `opentelemetry-sdk-extension-aws` `AwsLambdaResourceDetector` implementation |
| 63 | HIGH | `AwsLambdaResourceDetector` not specified for `TracerProvider` resource configuration — missing `cloud.provider`, `cloud.region`, `faas.name` resource attributes on all emitted spans | Added FR-072 (resource detector configuration); added assumption. Source: `opentelemetry-python-contrib` SDK extension |
| 64 | MEDIUM | `BatchSpanProcessor` default `schedule_delay_millis=5000` (5 seconds) and `max_queue_size=2048` are designed for long-running servers, not Lambda — oversized configuration wastes memory and increases span-loss window on crash | Added FR-073 (Lambda-tuned BSP configuration); added edge case and assumption. Source: OTel Python SDK v1.39.1 defaults |
| 65 | MEDIUM | Round 7 assumptions about "zero Lambda layers" and "250MB deployment limit" based on WRONG deployment model — SSE Lambda is container-based (ECR) with 10GB limit | **INVALIDATED** Round 7 assumption; corrected in spec. All 3 container-based Lambdas (SSE, Analysis, Dashboard) cannot use layers |

## Round 8 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| Container-based Lambda cannot use Lambda Layers | **RESOLVED (BLOCKER)** | FR-062/FR-063 REWRITTEN for container deployment; FR-069/FR-070 added; SC-029 added |
| `service.name` defaults to `unknown_service` | **RESOLVED** | FR-071 requires `OTEL_SERVICE_NAME` env var; SC-030 verifies service map naming |
| `AwsLambdaResourceDetector` not in TracerProvider config | **RESOLVED** | FR-072 requires resource detector in TracerProvider setup |
| BatchSpanProcessor defaults inappropriate for Lambda | **RESOLVED** | FR-073 mandates Lambda-tuned BSP parameters |
| Round 7 assumptions based on wrong deployment model | **RESOLVED** | Assumption INVALIDATED with correction |
| SSE Lambda custom runtime + ADOT compatibility | **NOT A RISK** | Extensions are Lambda service-level, independent of runtime; `python:3.13-slim` + custom bootstrap fully compatible |
| ADOT Extension lifecycle with RESPONSE_STREAM | **ALREADY ADDRESSED** | Extension remains alive during entire streaming phase; documented in Round 7 edge cases |

## Round 3 Invalidation Summary

| Item | Round 2 Content | Round 3 Status | Reason |
| ---- | -------------- | -------------- | ------ |
| Assumption 7 | `begin_segment()` can create independent segments in Lambda | **INVALIDATED** | SDK's `LambdaContext.put_segment()` silently discards; `FacadeSegment` immutable |
| FR-026 | Create independent X-Ray segments during streaming | **REPLACED** | Independent lifecycle tracing mechanism (Lambda Extension) |
| FR-027 | Auto-patched boto3 calls in independent segments | **REPLACED** | Streaming service call capture via FR-026 mechanism |
| FR-025 | Explicitly propagate trace ID into new event loop | **REVISED** | `threading.local()` default already propagates correctly; issue is `AsyncContext` not default context |
| FR-029 | All Lambdas use consistent approach | **UPDATED** | SSE Lambda has distinct requirements; non-streaming Lambdas consistent; both export to X-Ray |
| SC-010 | Zero orphaned subsegments via independent segments | **REVISED** | Zero orphaned subsegments via independent lifecycle mechanism |
| SC-012 | All Lambdas use single approach | **REVISED** | Non-streaming Lambdas consistent; SSE distinct but unified in X-Ray |

## Round 6 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| Per-invocation OTel context extraction | **RESOLVED** | FR-059 requires trace context extraction on every invocation, not just cold start |
| Powertools `auto_patch=True` dual-emission | **RESOLVED** | FR-060 requires `auto_patch=False` on SSE Lambda to prevent Powertools/ADOT double-patching |
| SSE Lambda needs `auto_patch=False` | **RESOLVED** | FR-060 explicitly sets SSE Lambda patching to ADOT-only |
| Existing alarm thresholds not reviewed | **RESOLVED** | FR-061 requires threshold calibration audit against current traffic baselines |
| SSE Lambda memory validated | **RESOLVED** | Assumption added confirming 512MB adequate for Lambda + ADOT + OTel packages |
| Generator `finally` block reliable | **RESOLVED** | Assumption added; edge case documents SHUTDOWN event unreliability as justification |
| ADOT OTLP receiver cold start race mitigated | **RESOLVED** | Edge case documents race condition; ADOT Extension initializes before handler per AWS lifecycle contract |

## Emergent Issues Found (Round 9 — Four-Domain Deep Research)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 66 | HIGH | ADOT Extension has KNOWN ~30% span drop rate (aws-otel-lambda#886, opentelemetry-lambda#224) — collector context canceled before HTTP exports complete. Spec's force_flush() handles SDK→Extension hop but not Extension→X-Ray backend race | Added FR-074 (two-hop flush architecture acknowledgment), FR-075 (decouple processor requirement); added SC-031; 2 edge cases, 1 assumption. Source: GitHub aws-otel-lambda#886 |
| 67 | HIGH | FR-049 does not classify put_metric_data errors as transient vs permanent — IAM revocation (exact failure FR-051 detects) would be silently retried instead of immediately escalated | Added FR-079 (error classification with differential handling); added SC-035; 1 edge case, 1 assumption. Source: AWS CloudWatch API PutMetricData error reference |
| 68 | MEDIUM | FR-060 does not prohibit OTel BotocoreInstrumentor().instrument() — future implementer could enable it alongside manual spans, recreating double-instrumentation | Added FR-076 (explicit BotocoreInstrumentor prohibition); added SC-033; 1 edge case |
| 69 | MEDIUM | TracerProvider(shutdown_on_exit=True) default registers atexit handler that races with ConcurrentMultiSpanProcessor on environment recycling | Added FR-077 (shutdown_on_exit=False requirement); added SC-032; 1 edge case, 1 assumption. Source: opentelemetry-python#4461 |
| 70 | MEDIUM | X-Ray trace propagation delay is non-deterministic; canary's single-shot query at 30s produces false negatives | Added FR-078 (retry-with-backoff for trace retrieval); added SC-034; 1 edge case, 1 assumption. Source: AWS X-Ray FAQ |
| 71 | MEDIUM | FR-033 assumes SSE Lambda server checks Last-Event-ID — if server ignores it, client-side propagation is hollow | Added FR-081 (server-side Last-Event-ID support requirement); added SC-036; 1 edge case, 1 assumption |
| 72 | MEDIUM | FR-048 requires reading response X-Amzn-Trace-Id but CORS ExposeHeaders doesn't include it — hard prerequisite for reconnection trace correlation | Added FR-082 (CORS ExposeHeaders requirement); added SC-037; 1 edge case |
| 73 | MEDIUM | Spec Round 5 assumption states "default batch timeout of 200ms" — INCORRECT; actual default is 5000ms | Added FR-084 (assumption correction); corrected assumption text; fixed 4 downstream references. Source: OTel Python SDK source |
| 74 | LOW | TracerProvider shutdown_on_exit race on Python 3.13+ | Resolved by FR-077; edge case documents the race condition |
| 75 | LOW | SNS direct publish insufficient during simultaneous CloudWatch + SNS regional failure | Added FR-080 (SHOULD support secondary external webhook channel); documented as SHOULD, not MUST |
| 76 | LOW | Account-level Transaction Search migration could break canary's BatchGetTraces | Added edge case documenting the risk; canary tests its own retrieval path |
| 77 | LOW | Safari SSE frame buffering behavior differences | Added edge case; server-side padding is the workaround |
| 78 | LOW | ReadableStream close type distinction for reconnection strategy | Added FR-083 (differential reconnection by close type); added SC-038; 1 edge case, 1 assumption |
| 79 | INFO | SimpleSpanProcessor recommended by some sources for FaaS | Documented as considered alternative in Round 7 edge case; BSP approach retained with rationale |

## Round 9 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| ADOT Extension span drop race condition | **RESOLVED** | FR-074 acknowledges two-hop flush; FR-075 mandates decouple processor; canary provides aggregate detection |
| CloudWatch error classification for canary | **RESOLVED** | FR-079 classifies errors; immediate escalation for IAM/credential errors |
| OTel BotocoreInstrumentor not prohibited | **RESOLVED** | FR-076 explicitly prohibits BotocoreInstrumentor on SSE Lambda |
| TracerProvider atexit shutdown race | **RESOLVED** | FR-077 requires shutdown_on_exit=False |
| Canary trace retrieval false negatives | **RESOLVED** | FR-078 adds retry-with-backoff (30s then 60s) |
| Server-side Last-Event-ID support | **RESOLVED** | FR-081 requires server check or X-SSE-Resume-Supported header |
| CORS ExposeHeaders for trace correlation | **RESOLVED** | FR-082 mandates x-amzn-trace-id in ExposeHeaders |
| BSP default timeout assumption incorrect | **RESOLVED** | FR-084 corrects assumption; 4 downstream references fixed |
| Reconnection close type distinction | **RESOLVED** | FR-083 specifies differential backoff by close type |
| Secondary out-of-band alerting channel | **RESOLVED** | FR-080 adds SHOULD for external webhook |
| Transaction Search account migration | **RESOLVED** | Edge case documents risk |
| Safari SSE buffering | **RESOLVED** | Edge case documents workaround |
| SimpleSpanProcessor alternative | **NOT APPLICABLE** | Informational; BSP retained with rationale |
| ADOT memory measurement ambiguity | **NOT APPLICABLE** | Low risk; recommend measuring in preprod |

## Emergent Issues Found (Round 10 — Canonical-Source Blind Spot Analysis)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 80 | HIGH | Lambda streaming continues after client disconnect — Python custom runtimes have no standard disconnect detection mechanism; BrokenPipeError is the only signal; SSE Lambda continues DynamoDB polling and span creation for phantom streams | Added FR-085 (BrokenPipeError catch + `client.disconnected=true` annotation); added SC-039; 1 edge case. Source: AWS Lambda Response Streaming docs |
| 81 | HIGH | BatchSpanProcessor `max_queue_size=512` (FR-073) insufficient — ~675 spans per 15s streaming invocation exceeds queue capacity; spans silently dropped via `queue.put_nowait()` Full exception | **AMENDED** FR-073 via FR-086 (`max_queue_size` → 1500); added FR-091 (queue overflow observability); added SC-040; 1 edge case, 1 corrected assumption. Source: OTel Python SDK BatchSpanProcessor.on_end() |
| 82 | HIGH | X-Ray IsPartial flag not checked by canary — partial traces with missing ADOT streaming spans appear "found" to canary (FR-078) | Added FR-087 (IsPartial check with degraded reporting); added SC-041. Source: AWS X-Ray Concepts docs |
| 83 | MEDIUM | SSE `retry:` field not emitted by server — clients use unpredictable implementation-defined reconnection defaults; fetch()+ReadableStream does NOT auto-parse retry: like EventSource | Added FR-088 (server-side retry: emission), FR-089 (client-side retry: parsing); added SC-042. Source: WHATWG HTML Living Standard §9.2 |
| 84 | MEDIUM | Lambda Function URL streaming breaks silently in VPC environments — responses buffered instead of streamed with no error | Added assumption (VPC constraint); added SC-043. Source: AWS Lambda Response Streaming docs |
| 85 | MEDIUM | Decouple processor auto-configuration only applies to Lambda Layer, NOT container-based custom configs — omission reverts to ~30% span drop rate | Added FR-090 (explicit decouple in custom YAML); added SC-044; 1 edge case. Source: ADOT decouple processor README |
| 86 | MEDIUM | OTel streaming semantic conventions undefined — project's span-per-poll-cycle convention has no standard to align to | Added assumption documenting project-specific convention. Source: OTel GenAI Spans semconv |
| 87 | MEDIUM | Python custom runtime required for response streaming — implicit in architecture but not documented as explicit constraint | Added assumption. Source: AWS Lambda Response Streaming docs |
| 88 | MEDIUM | X-Ray new-style segment format rolling out — eliminates Invocation subsegment; customer subsegments attach to Function segment | Added assumption (format-independent OTel parenting). Source: AWS Lambda X-Ray docs |
| 89 | LOW | AwsXRayLambdaPropagator Sampled=0 extraction bug — if Active Tracing disabled, ALL spans silently suppressed | Added edge case. Source: opentelemetry-lambda#1782 |
| 90 | LOW | X-Ray subsegment streaming threshold (100 per segment) — auto_patch=True would count streaming-phase boto3 calls against limit | Added edge case (reinforces FR-060). Source: AWS X-Ray Troubleshooting docs |
| 91 | LOW | X-Ray centralized sampling fallback — OTel sampler falls back to 1 trace/sec when sampling API unreachable; dev/preprod 100% sampling silently degrades | Added edge case. Source: AWS ADOT Remote Sampling docs |

## Round 10 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| Lambda streaming after client disconnect | **RESOLVED** | FR-085 catches BrokenPipeError, annotates spans; SC-039 verifies |
| BSP queue size insufficient | **RESOLVED** | FR-086 amends FR-073 queue to 1500; FR-091 adds overflow observability; SC-040 verifies |
| Canary IsPartial trace check | **RESOLVED** | FR-087 checks IsPartial flag, reports degraded; SC-041 verifies |
| SSE retry: field not emitted | **RESOLVED** | FR-088 (server) + FR-089 (client); SC-042 verifies |
| Function URL VPC streaming limitation | **RESOLVED** | Assumption documents no-VPC constraint; SC-043 verifies |
| Decouple processor in custom config | **RESOLVED** | FR-090 requires explicit inclusion; SC-044 verifies |
| OTel streaming conventions undefined | **RESOLVED** | Assumption documents project-specific convention |
| Python custom runtime requirement | **RESOLVED** | Assumption documents requirement with source |
| X-Ray new-style segment format | **RESOLVED** | Assumption documents format-independent parenting |
| AwsXRayLambdaPropagator Sampled=0 bug | **RESOLVED** | Edge case documents risk if Active Tracing disabled |
| X-Ray subsegment streaming threshold | **RESOLVED** | Edge case reinforces FR-060 (auto_patch=False) |
| X-Ray sampling fallback behavior | **RESOLVED** | Edge case documents 1 trace/sec fallback |

### Round 10 — SSE Streaming Deep-Dive

| # | Type | ID | Description | Status |
|---|------|----|-------------|--------|
| 85 | FR | FR-085 | BrokenPipeError catch + client.disconnected=true span annotation on disconnect | [ ] |
| 86 | FR | FR-086 | BSP max_queue_size amended from 512 → 1500 (2x ~675 spans/invocation) | [ ] |
| 87 | FR | FR-087 | Canary IsPartial trace check — report degraded when IsPartial=true | [ ] |
| 88 | FR | FR-088 | SSE Lambda emits retry: 3000 field in initial SSE frame | [ ] |
| 89 | FR | FR-089 | Frontend parses retry: field from SSE stream | [ ] |
| 90 | FR | FR-090 | Explicit decouple processor in custom ADOT collector YAML | [ ] |
| 91 | FR | FR-091 | BSP queue overflow structured logging + metric filter | [ ] |
| 85 | SC | SC-039 | Client disconnect spans carry client.disconnected=true annotation | [ ] |
| 86 | SC | SC-040 | BSP max_queue_size >= 1350, zero spans dropped in normal operation | [ ] |
| 87 | SC | SC-041 | Canary reports IsPartial traces as degraded (not success) | [ ] |
| 88 | SC | SC-042 | SSE emits retry: 3000 and frontend uses it for reconnection delay | [ ] |
| 89 | SC | SC-043 | SSE Lambda deployed without VPC configuration | [ ] |
| 90 | SC | SC-044 | Custom ADOT YAML includes [decouple, batch] pipeline | [ ] |

### Round 11 — Bootstrap & Deadline Safety

| # | Type | ID | Description | Status |
|---|------|----|-------------|--------|
| 92 | FR | FR-092 | Custom bootstrap reads Lambda-Runtime-Trace-Id and sets _X_AMZN_TRACE_ID on every invocation | [ ] |
| 93 | FR | FR-093 | Deadline-aware proactive force_flush() when remaining time < 3000ms | [ ] |
| 94 | FR | FR-094 | FR-035 scoped: API Gateway sampling override works; Function URL limitation acknowledged | [ ] |
| 95 | FR | FR-095 | OPENTELEMETRY_COLLECTOR_CONFIG_FILE=/opt/collector-config/config.yaml in Terraform | [ ] |
| 96 | FR | FR-096 | Canary 5-minute EventBridge interval, two-phase CloudWatch health check, 60s timeout | [ ] |
| 97 | FR | FR-097 | FR-043 metrics use SentimentAnalyzer/Reliability namespace with FunctionName+FailurePath dims | [ ] |
| 98 | FR | FR-098 | ADOT export failure CloudWatch Logs metric filter on "Exporting failed. Dropping data." | [ ] |
| 99 | FR | FR-099 | Frontend TextDecoder({stream: true}) for UTF-8 chunk boundary safety | [ ] |
| 91 | SC | SC-045 | Bootstrap propagates _X_AMZN_TRACE_ID on warm invocations — correct trace IDs | [ ] |
| 92 | SC | SC-046 | Proactive flush before Lambda timeout — zero span loss on timeout | [ ] |
| 93 | SC | SC-047 | OPENTELEMETRY_COLLECTOR_CONFIG_FILE set in Terraform env vars | [ ] |
| 94 | SC | SC-048 | Canary runs every 5 minutes, <= 10 minute detection latency | [ ] |
| 95 | SC | SC-049 | FR-043 metrics in unified SentimentAnalyzer/Reliability namespace | [ ] |
| 96 | SC | SC-050 | ADOT export failure metric filter fires within 5 minutes | [ ] |
| 97 | SC | SC-051 | Frontend TextDecoder uses stream: true — no UTF-8 corruption | [ ] |

## Emergent Issues Found (Round 12 — Deployment Safety & Operational Lifecycle)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 92 | **CRITICAL** | Post-proactive-flush generator continues creating orphaned spans — FR-093 fires at 3000ms remaining but generator behavior after flush unspecified; new spans created in remaining ~3s either orphaned or permanently lost on timeout SIGKILL | Added FR-100 (graceful stream termination after flush); added SC-052. FR-100 converts potential timeout into normal completion — ADOT Extension gets reliable normal Shutdown instead of timeout Shutdown |
| 93 | HIGH | OTel Python core packages have no version pinning requirement — lockstep enforced by pip resolver but builds non-reproducible across dates; AWS contrib packages need floor pins | Added FR-101 (version pinning strategy); added SC-053. Core packages pinned with `==`, contrib with floor+ceiling |
| 94 | HIGH | SSE Lambda 512MB insufficient — ADOT Extension ~50MB + OTel SDK ~30MB + runtime ~200MB = ~330MB baseline; only ~180MB headroom; cold start at 512MB is ~1200ms vs ~800ms at 1024MB | Added FR-102 (memory increase to 1024MB); added SC-054. Round 6 assumption about 512MB adequacy INVALIDATED. Source: AWS Lambda performance benchmarks |
| 95 | HIGH | Bootstrap passes `None` for Lambda context parameter — handler cannot call `context.get_remaining_time_in_millis()` making FR-093 unimplementable | Added FR-103 (bootstrap deadline propagation); added SC-055. Hard prerequisite for FR-093. Confirmed by code inspection: bootstrap line 157 |
| 96 | MEDIUM | Zero Lambda functions have memory utilization alarms — ADOT memory overhead (~50MB on SSE Lambda) increases OOM risk without advance warning | Added FR-104 (memory alarms at 85%); added SC-056 |
| 97 | MEDIUM | FR-098 metric filter pattern matches only first ADOT export failure variant — misses "Exporting failed. No more retries left. Dropping data." (retries exhausted) | Added FR-105 (pattern amendment); added SC-057. Updated to substring match covering both variants |
| 98 | MEDIUM | OTel SDK initialization failures crash Lambda with unclear error messages — operators cannot diagnose misconfiguration from CloudWatch Logs without reproducing locally | Added FR-106 (init error attribution); error logged with component/error/action before re-raise |
| 99 | NOT A RISK | Concurrent Lambda invocations sharing ADOT Extension — each invocation gets own execution environment with own Extension process; zero cross-invocation span corruption | Documented as assumption. Source: AWS Lambda Execution Environment lifecycle |

## Round 12 Blind Spot Resolution Summary

| Blind Spot | Status | Resolution |
| ---------- | ------ | ---------- |
| Post-proactive-flush generator behavior | **RESOLVED (CRITICAL)** | FR-100 requires graceful termination; converts timeout into normal completion; SC-052 verifies |
| OTel package version pinning | **RESOLVED** | FR-101 mandates lockstep pins for core, floor pins for contrib; SC-053 verifies |
| SSE Lambda memory insufficiency | **RESOLVED** | FR-102 increases to 1024MB; Round 6 assumption INVALIDATED; SC-054 verifies |
| Bootstrap deadline propagation | **RESOLVED** | FR-103 reads Lambda-Runtime-Deadline-Ms; hard prerequisite for FR-093; SC-055 verifies |
| Lambda memory utilization monitoring | **RESOLVED** | FR-104 adds 85% alarms on all 6 Lambdas; SC-056 verifies |
| FR-098 metric filter incompleteness | **RESOLVED** | FR-105 amends pattern to substring match; SC-057 verifies |
| OTel init failure error attribution | **RESOLVED** | FR-106 logs structured error before re-raise; does not violate FR-018 fail-fast |
| Concurrent invocations sharing Extension | **NOT A RISK** | Each invocation gets own execution environment; documented as assumption |
| ADOT-OTel OTLP version compatibility | **NOT A RISK** | OTLP v1 stable since proto 1.0.0; compatible with all ADOT since v0.21.0; documented as assumption |

### Round 12 — Deployment Safety & Operational Lifecycle

| # | Type | ID | Description | Status |
|---|------|----|-------------|--------|
| 100 | FR | FR-100 | Post-proactive-flush graceful stream termination with `event: deadline` SSE event | [ ] |
| 101 | FR | FR-101 | OTel Python core packages pinned to identical version; contrib floor-pinned | [ ] |
| 102 | FR | FR-102 | SSE Lambda memory increased from 512MB to 1024MB | [ ] |
| 103 | FR | FR-103 | Bootstrap reads Lambda-Runtime-Deadline-Ms and propagates deadline to handler | [ ] |
| 104 | FR | FR-104 | All 6 Lambdas have memory utilization alarms at 85% threshold | [ ] |
| 105 | FR | FR-105 | FR-098 metric filter pattern amended to match both ADOT failure variants | [ ] |
| 106 | FR | FR-106 | OTel SDK initialization error attribution with structured logging | [ ] |
| 100 | SC | SC-052 | Generator terminates after flush; ADOT gets normal Shutdown (not timeout) | [ ] |
| 101 | SC | SC-053 | OTel core packages pinned to identical version; builds reproducible | [ ] |
| 102 | SC | SC-054 | SSE Lambda 1024MB; cold start < 1500ms; memory < 80% under streaming | [ ] |
| 103 | SC | SC-055 | Bootstrap provides deadline; handler computes remaining time | [ ] |
| 104 | SC | SC-056 | All 6 Lambdas have memory utilization alarms | [ ] |
| 105 | SC | SC-057 | Metric filter matches both ADOT export failure variants | [ ] |

### Emergent Issues Found (Round 13 — Deployment Safety & Migration Observability)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 100 | **CRITICAL** | No deployment ordering constraint for 17 tasks — upstream-to-downstream instrumentation required | FR-107 adds 6-phase deployment ordering |
| 101 | HIGH | No OTel SDK kill switch for emergency tracing disable | FR-108 adds OTEL_SDK_DISABLED=false explicit env var |
| 102 | HIGH | No migration dual-emit period — logging removal before X-Ray verification | FR-109 adds 2-week dual-emit with 4 verification gates |
| 103 | HIGH | No pre-ADOT rollback container image in ECR | FR-110 requires pre-adot-baseline tagged image |
| 104 | HIGH | X-Ray Groups missing insights_enabled=true — no CloudWatch metrics from Groups | FR-111 requires insights_enabled=true on all Groups |
| 105 | MEDIUM | EventBridge→Lambda permission race on canary deployment | FR-112 adds explicit depends_on in Terraform |
| 106 | MEDIUM | Canary lacks trace completeness ratio metric — detects per-trace partial but not systemic loss | FR-113 adds completeness_ratio metric with 95% threshold |

## Round 13 Blind Spot Resolution Summary

| Blind Spot | Source | Resolution | New FR/SC |
|---|---|---|---|
| Deployment ordering | AWS X-Ray best practices | 6-phase ordering with gates | FR-107, SC-058 |
| OTel kill switch | OTel specification OTEL_SDK_DISABLED | Explicit env var on ADOT Lambdas | FR-108, SC-059 |
| Migration dual-emit | Observability migration patterns | 2-week dual-emit with 4 gates | FR-109, SC-058 |
| Rollback image | Container deployment patterns | pre-adot-baseline ECR image | FR-110, SC-060 |
| X-Ray Groups insights | AWS X-Ray Groups docs | insights_enabled=true | FR-111, SC-061 |
| EventBridge race | AWS EventBridge lifecycle | Terraform depends_on | FR-112, SC-062 |
| Completeness ratio | Canary design patterns | Aggregate completeness metric | FR-113, SC-063 |

### Emergent Issues Found (Round 14 — Export Safety & Operational Completeness)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 107 | **CRITICAL** | `force_flush()` timeout not enforced (OTel #4568) — OTLP exporter blocks indefinitely on ADOT crash; 10s default x 6 retries x 24 batches = potential 24-minute block; FR-093's 3000ms deadline defeated | FR-114 adds `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2` env var |
| 108 | **CRITICAL** | BSP pops spans before export — failed exports permanently destroy spans; `force_flush()` returns `True` regardless | FR-120 annotation budget + documented assumption that return value is NOT a health signal |
| 109 | HIGH | No SSE event-level trace correlation — Audit Section 6 flags "SSE events — Trace IDs not in payloads." HTTP headers correlate at connection level only | FR-115 adds `trace_id` field in SSE event JSON data |
| 110 | HIGH | ADOT collector config not validated pre-deployment — no JSON Schema; malformed YAML crashes Extension silently | FR-116 adds CI validation with ADOT `validate` subcommand |
| 111 | HIGH | FR-109 verification gates abstract — no concrete check definitions; "100 manual spot-checks" unautomated | FR-117 adds formalized executable gates with S3 audit trail |
| 112 | HIGH | ReadableStream error taxonomy missing — 4 error types (TypeError, AbortError, TimeoutError, done:true) with different reconnection strategies; server close vs network drop indistinguishable without sentinel | FR-118 adds error classification + `event: done` sentinel |
| 113 | MEDIUM | CORS preflight from X-Amzn-Trace-Id — not CORS-safelisted; 50-200ms latency per uncached preflight | FR-119 adds `Access-Control-Max-Age: 7200` |
| 114 | MEDIUM | X-Ray 50-annotation limit — OTel attributes count against same limit; exceeding silently drops | FR-120 adds annotation budget allocation (max 25/50 per span) |
| 115 | MEDIUM | treat_missing_data not classified — `notBreaching` on canary alarms defeats their purpose; error-only metrics show false-green when system dies | FR-121 adds systematic classification by alarm type |
| 116 | MEDIUM | Rollback procedure informal — FR-110 preserves image but no trigger criteria, timeline, or verification | FR-122 adds operational procedure with 5/15-minute timelines |
| 117 | MEDIUM | ADOT startup failures unmonitored — config errors produce distinct log patterns not captured by metric filters | FR-123 adds `ADOTCollectorStartupFailure` metric filter |

### Emergent Issues Found (Round 15 — silent failure instrumentation, alarm calibration, cascading false-green)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 118 | **CRITICAL** | 5 code paths (circuit_breaker, audit, notification, self_healing, fanout) catch exceptions, log, but emit NO metric — operators cannot detect DynamoDB persistence failures, SNS publish failures, or batch write partial failures | FR-124 adds unified SilentFailure/Count metric with FailurePath dimension + structured log fallback |
| 119 | **CRITICAL** | put_metric_data itself can fail (throttling, regional degradation) with no backup detection — cascading false-green where treat_missing_data=notBreaching resolves alarms to OK during outage | FR-125 adds CloudWatch Logs metric filter on metric_fallback=true as out-of-band backup |
| 120 | HIGH | Alarm thresholds miscalibrated — analysis_latency_high at 25s (42% of 60s timeout) causes cold-start false positives; error alarms use absolute counts not percentages; collision_rate_low takes 30min to detect | FR-127 percentage-based errors + FR-133 reduced evaluation periods |
| 121 | HIGH | Ingestion and Notification Lambdas have no latency alarms — approaching-timeout degradation invisible to operators | FR-128 adds P95 latency alarms at 80% of timeout |
| 122 | HIGH | Dashboard alarm widget shows 6 of 30+ alarms — operators get incomplete picture; no composite alarm for system health | FR-129 adds severity-tiered widgets + composite alarm |
| 123 | HIGH | SendGrid HTTP calls traverse python_http_client → urllib.request → http.client — only httplib patch captures them; auto-patching verification needed | FR-130 adds integration test for httplib/urllib chain verification |
| 124 | MEDIUM | Canary heartbeat must use same put_metric_data call path as production — separate health check proves nothing about emission pipeline | FR-126 adds piggybacked heartbeat metric |
| 125 | MEDIUM | treat_missing_data=notBreaching on application alarms masks CloudWatch Metrics API degradation; INSUFFICIENT_DATA state suppressed | FR-131 mandates treat_missing_data=missing for application metric alarms |
| 126 | MEDIUM | Work order files (fix-*.md) contain only Round 1-6 FRs — 66+ FRs from Rounds 7-14 missing from implementation guides | FR-132 adds automated work order synchronization validation |
| 127 | MEDIUM | Collision rate alarm evaluation periods too slow — 6×5min=30min for broken dedup detection | FR-133 reduces to 2-3 periods |

#### Round 15 Blind Spot Resolution Summary

| Blind Spot | Source | Resolution | New FR/SC |
| --- | --- | --- | --- |
| Silent failure paths emit no metric | Audit Section 8 (6 silent failure modes) | Unified SilentFailure/Count metric with dimensions | FR-124, SC-074 |
| put_metric_data failure undetectable | Audit Section 8.1 (metrics emission fails silently) | CloudWatch Logs metric filter backup path | FR-125, SC-075 |
| Canary heartbeat separate from production | Amazon Builder's Library health check pattern | Piggybacked on same put_metric_data call | FR-126, SC-076 |
| Error alarms use absolute counts | AWS Observability Best Practices | Percentage-based with minimum invocation guard | FR-127, SC-077 |
| Missing Lambda latency alarms | Audit Section 6.2 (ingestion/notification gaps) | P95 at 80% of timeout per Lambda | FR-128, SC-078 |
| Dashboard alarm widget incomplete | Audit Section 6.3 (6 of 30+ alarms) | Severity-tiered widgets + composite alarm | FR-129, SC-079 |
| SendGrid patching uncertain | Audit Section 7.2 (UNCERTAIN marking) | Integration test for httplib/urllib chain | FR-130, SC-080 |
| treat_missing_data masks degradation | CloudWatch alarm documentation | missing for app metrics, breaching for canary | FR-131, SC-081 |
| Work order files stale | Manual audit of fix-*.md vs HL doc | Automated synchronization validation | FR-132, SC-082 |
| Collision rate detection too slow | CloudWatch Alarms Best Practices | Reduced evaluation periods | FR-133, SC-083 |

## Round 14 Blind Spot Resolution Summary

| Blind Spot | Source | Resolution | New FR/SC |
|---|---|---|---|
| force_flush() timeout not enforced | OTel GitHub #4568 | OTLP exporter timeout env var | FR-114, SC-064 |
| BSP pops spans before export | OTel BSP implementation | Annotation budget + documented assumption | FR-120, SC-070 |
| SSE event-level trace correlation | Audit Section 6 | trace_id field in SSE event JSON | FR-115, SC-065 |
| ADOT collector config validation | ADOT operational patterns | CI validation with ADOT validate subcommand | FR-116, SC-066 |
| FR-109 verification gates abstract | Migration observability patterns | Executable gates with S3 audit trail | FR-117, SC-067 |
| ReadableStream error taxonomy | WHATWG Streams Standard | Error classification + done sentinel | FR-118, SC-068 |
| CORS preflight latency | CORS specification | Access-Control-Max-Age: 7200 | FR-119, SC-069 |
| X-Ray 50-annotation limit | AWS X-Ray limits | Annotation budget allocation (max 25/50) | FR-120, SC-070 |
| treat_missing_data classification | CloudWatch alarm patterns | Systematic classification by alarm type | FR-121, SC-071 |
| Rollback procedure informal | Operational runbook patterns | Procedure with 5/15-minute timelines | FR-122, SC-072 |
| ADOT startup failures unmonitored | ADOT Extension log patterns | ADOTCollectorStartupFailure metric filter | FR-123, SC-073 |

## Emergent Issues Found (Round 17 — OTel Error Status & Canary Resilience)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 130 | **CRITICAL** | Manual OTel spans on SSE Lambda have no requirement to call `span.set_status(StatusCode.ERROR)` — ADOT X-Ray exporter's `makeCause()` is GATED on StatusCode.ERROR; `record_exception()` alone produces invisible exceptions in X-Ray (no fault flag, no cause field, no Group filter match) | Added FR-144 (mandatory dual-call: `set_status(ERROR)` + `record_exception()`); added SC-094; 3 edge cases, 1 assumption. Source: ADOT X-Ray Exporter `cause.go` |
| 131 | HIGH | Canary Lambda exemption from FR-018 fail-fast not formalized — HL doc states "sole exception is the canary" but no FR captures this; implementer following FR-018 makes canary crash on X-Ray failure | Added FR-145 (canary FR-018 exemption with structured error handling); added SC-095. Source: AWS Well-Architected OPS pillar |
| 132 | HIGH | SC-064 tests only port-unreachable ADOT failure — FR-139's hung Extension (TCP accept, no response) is a distinct failure mode NOT exercised by port-unreachable test; ECONNREFUSED fails fast without needing the thread wrapper | SC-064 AMENDED to test both failure modes; no new FR needed |
| 133 | MEDIUM | Canary Lambda is function #7 with contradictory requirements — must be instrumented (FR-029) AND resilient to X-Ray failures (FR-018 exempt); dual role needs explicit scope | Added FR-146 (canary instrumentation scope); added SC-096 |
| 134 | MEDIUM | OTel SpanKind not specified for manual SSE Lambda spans — incorrect SpanKind causes phantom service map nodes (CLIENT) or hidden dependencies (INTERNAL); SC-028 at risk | Added edge case and assumption; no new FR (SC-028 already specifies outcome) |

### Round 17 — OTel Error Status & Canary Resilience

| # | Type | ID | Description | Status |
|---|------|----|-------------|--------|
| 144 | FR | FR-144 | Manual OTel spans MUST call both set_status(ERROR) and record_exception() on error | [ ] |
| 145 | FR | FR-145 | Canary Lambda catches X-Ray/OTel init errors without crashing (FR-018 exemption) | [ ] |
| 146 | FR | FR-146 | Canary Lambda instrumented per FR-029 with FR-145 error wrapping | [ ] |
| 94 | SC | SC-094 | All SSE Lambda error spans have fault=true and populated cause in X-Ray | [ ] |
| 95 | SC | SC-095 | Canary completes health check even when X-Ray init fails | [ ] |
| 96 | SC | SC-096 | Canary traces visible in X-Ray when X-Ray is healthy | [ ] |
| 64a | SC | SC-064 | AMENDED: Tests both port-unreachable AND hung-Extension failure modes | [ ] |

## Round 17 Blind Spot Resolution Summary

| Blind Spot | Source | Resolution | New FR/SC |
|---|---|---|---|
| OTel span error status invisible to X-Ray | ADOT X-Ray Exporter source | Mandatory dual-call requirement | FR-144, SC-094 |
| Canary FR-018 exemption not formalized | HL document design principle | Formalized exemption with structured logging | FR-145, SC-095 |
| SC-064 tests wrong failure mode | FR-139 analysis | SC-064 amended for both modes | SC-064 amended |
| Canary dual-mode operation | Architectural analysis | Explicit instrumentation scope | FR-146, SC-096 |
| SpanKind service map distortion | ADOT X-Ray Exporter source | Edge case + assumption (SC-028 covers outcome) | Edge case only |

## Emergent Issues Found (Round 20 — Operational Reality & Process Integrity)

| # | Severity | Issue | Resolution |
| --- | -------- | ----- | ---------- |
| 135 | **CRITICAL** | OTel Python SDK `BatchSpanProcessor` has documented deadlock bug (opentelemetry-python#3886) — worker thread holds internal lock indefinitely; `force_flush()` hangs; FR-139's thread wrapper terminates call but spans locked in BSP are permanently unrecoverable; THIRD span-loss vector distinct from Extension hang and Extension drop | Added FR-156 (BSP deadlock diagnostic differentiation); added SC-106; 2 edge cases, 1 assumption. Source: opentelemetry-python#3886 |
| 136 | **CRITICAL** | FR-154 staleness enforcement gate never applied — HL document missing 9 FRs (FR-147-155), 9 SCs (SC-097-105), entire Round 18; no GitHub issue created as FR-154 mandates; detection-without-enforcement proven insufficient across Rounds 16-20 | Added FR-157 (retroactive enforcement with explicit deferral + GitHub issue mandate); added SC-107. Source: Observed failure — FR-132 exists since Round 15 but staleness persisted |
| 137 | HIGH | ADOT Lambda Extension cold start latency unmeasured — AWS publishes NO official benchmarks (opentelemetry-lambda#263); community reports 200ms-2000ms+; SSE Lambda is customer-facing with no cold start budget | Added FR-158 (cold start measurement + <2000ms P95 budget); added SC-108; 1 edge case. Source: opentelemetry-lambda#263, aws-otel-lambda#228 |
| 138 | HIGH | ADOT Extension IAM permissions not enumerated — FR-017 says "X-Ray permissions" but missing 3 of 5 required actions (GetSampling*); missing actions cause SILENT fallback to 1 trace/sec | Added FR-159 (5 IAM actions enumerated); added SC-109; 1 edge case, 1 assumption. Source: ADOT permissions docs |
| 139 | HIGH | RESPONSE_STREAM + ADOT Extension lifecycle has NO canonical documentation — foundational assumption unverified by AWS | Added FR-160 (preprod verification gate); added SC-110; 1 edge case, 1 assumption. Source: Absence of AWS documentation |
| 140 | HIGH | Function URL invocations sampled at 100% — no parent context + parentbased_always_on = every invocation is root span at $5/million traces | Added FR-161 (centralized sampling rule + daily anomaly alarm); added SC-111; 1 edge case, 1 assumption. Source: OTel sampler spec, X-Ray pricing |
| 141 | MEDIUM | SC-064 conflates two distinct failure modes (port-unreachable vs hung Extension) with different code paths | SC-064 SUPERSEDED → SC-064a + SC-064b; added FR-156a (informational). Source: Spec analysis |
| 142 | MEDIUM | treat_missing_data not classified per-alarm — FR-121/FR-131 classify by TYPE but 30+ alarms need individual mapping | Added FR-162 (exhaustive classification); added SC-112. Source: CloudWatch docs, AWS Well-Architected REL-06 |
| 143 | MEDIUM | ADOT Extension localhost OTLP accepts unauthenticated traces — Lambda isolation limits risk but attack surface exists | Documented as edge case and assumption (accepted risk). Source: ADOT permissions docs |
| 144 | MEDIUM | X-Ray 30-day retention with no archival — post-incident analysis beyond 30 days loses all data | Added FR-163 (manual archival procedure); added SC-113; 1 edge case. Source: X-Ray quotas |
| 145 | MEDIUM | Work order files (fix-*.md) contain only Round 1-6 FRs — 100+ FRs unmapped | Added FR-164 (synchronization enforcement); added SC-114. Source: Observed failure |

### Round 20 — Operational Reality & Process Integrity

| # | Type | ID | Description | Status |
|---|------|----|-------------|--------|
| 156 | FR | FR-156 | BSP deadlock diagnostic differentiation in force_flush() timeout path | [ ] |
| 157 | FR | FR-157 | FR-154 retroactive staleness enforcement with GitHub issue creation | [ ] |
| 158 | FR | FR-158 | ADOT cold start latency budget: measured P95 < 2000ms at 1024MB | [ ] |
| 159 | FR | FR-159 | ADOT Extension IAM: 5 X-Ray actions enumerated (Put*, GetSampling*) | [ ] |
| 160 | FR | FR-160 | RESPONSE_STREAM + ADOT Extension lifecycle preprod verification gate | [ ] |
| 161 | FR | FR-161 | Function URL sampling cost guard with centralized rule + daily alarm | [ ] |
| 156a | FR | FR-156a | SC-064 split rationale (informational) | [ ] |
| 162 | FR | FR-162 | Exhaustive treat_missing_data per-alarm classification | [ ] |
| 163 | FR | FR-163 | X-Ray trace archival procedure for production incidents | [ ] |
| 164 | FR | FR-164 | Work order file synchronization enforcement | [ ] |
| 165 | FR | FR-165 | BSP deadlock vector RETIRED — structured log label amended to "extension_hang" | [ ] |
| 166 | FR | FR-166 | SC-040 verification method replaced for SDK v1.39.1 deque behavior | [ ] |
| 167 | FR | FR-167 | ADOT Extension non-recovery documented as span-loss vector #3 | [ ] |
| 168 | FR | FR-168 | IAM policy drift detection for X-Ray permissions | [ ] |
| 169 | FR | FR-169 | Canary dead-man external health check for double-failure detection | [ ] |
| 170 | FR | FR-170 | PutTraceSegments TPS corrected and monitoring added | [ ] |
| 171 | FR | FR-171 | OTLP exporter retry-induced BSP worker block documented | [ ] |
| 172 | FR | FR-172 | X-Ray Groups and Sampling Rules quota tracking | [ ] |
| 173 | FR | FR-173 | X-Ray encryption-at-rest documentation | [ ] |
| 174 | FR | FR-174 | GetTraceSummaries 6-hour time window constraint | [ ] |
| 175 | FR | FR-175 | Centralized sampling rule scope documentation | [ ] |
| 176 | FR | FR-176 | Lambda Function URL invisible in X-Ray service map | [ ] |
| 177 | FR | FR-177 | ADOT version upgrade runbook with 8 verification gates | [ ] |
| 178 | FR | FR-178 | PutTraceSegments default TPS corrected from ~2,500 to 500 | [ ] |
| 179 | FR | FR-179 | Sampling graduation plan with 4 phases | [ ] |
| 180 | FR | FR-180 | Kill switch activation criteria with 5 thresholds | [ ] |
| 181 | FR | FR-181 | Lambda env var update operational hazard documentation | [ ] |
| 182 | FR | FR-182 | Deployment version tagging and skew detection | [ ] |
| 183 | FR | FR-183 | OTel Python ReadableSpan immutability constraint | [ ] |
| 184 | FR | FR-184 | Span attribute allow-listing at creation time | [ ] |
| 185 | FR | FR-185 | Canary trace annotation standard and X-Ray Group filter | [ ] |
| 186 | FR | FR-186 | Annotation budget strategy (50/trace limit) | [ ] |
| 187 | FR | FR-187 | ADOT resource overhead formal budget | [ ] |
| 188 | FR | FR-188 | In-flight span loss on sandbox recycle | [ ] |
| 189 | FR | FR-189 | Multi-account X-Ray via OAM documentation | [ ] |
| 190 | FR | FR-190 | FR-157 GitHub issue filing (SC-107 unfulfilled) | [ ] |
| 191 | FR | FR-191 | PII allow-list bypass prevention — CI gate for set_attribute(), runtime audit SpanProcessor, CloudWatch AllowListViolation alarm | [ ] |
| 192 | FR | FR-192 | SpanProcessor registration ordering — allow-list BEFORE BSP BEFORE audit | [ ] |
| 193 | FR | FR-193 | Annotation priority and exception budget — 3 reserved slots per exception, priority-ordered insertion | [ ] |
| 194 | FR | FR-194 | OTel Python SDK upgrade runbook with 7 verification gates | [ ] |
| 195 | FR | FR-195 | Powertools Tracer version pinning strategy | [ ] |
| 196 | FR | FR-196 | ADOT Extension degraded state detection via canary | [ ] |
| 197 | FR | FR-197 | Canary detection latency documentation (5-15 min window) | [ ] |
| 198 | FR | FR-198 | Sampling graduation per-Lambda configuration (API GW vs Function URL split) | [ ] |
| 199 | FR | FR-199 | Deployment version skew tolerance window (15-minute threshold) | [ ] |
| 064a | SC | SC-064a | Port-unreachable ADOT failure: ECONNREFUSED, fast fail, diagnostic log | [ ] |
| 064b | SC | SC-064b | Hung Extension failure: TCP accept, 2500ms timeout, diagnostic log | [ ] |
| 106 | SC | SC-106 | force_flush() resilient to BSP deadlock, diagnostic differentiation | [ ] |
| 107 | SC | SC-107 | GitHub issue "HL Document Staleness: Missing Round 18" created | [ ] |
| 108 | SC | SC-108 | SSE Lambda cold start P95 < 2000ms measured in preprod | [ ] |
| 109 | SC | SC-109 | ADOT IAM: all 5 xray:* actions in execution role | [ ] |
| 110 | SC | SC-110 | Preprod: ≥95% streaming-phase spans in X-Ray across 10 invocations | [ ] |
| 111 | SC | SC-111 | X-Ray sampling rule for Function URL + daily cost anomaly alarm | [ ] |
| 112 | SC | SC-112 | All alarms have explicit treat_missing_data matching classification | [ ] |
| 113 | SC | SC-113 | Operational runbook documents X-Ray trace archival procedure | [ ] |
| 114 | SC | SC-114 | fix-*.md files enumerate all mapped FRs with zero gaps | [ ] |
| 115 | SC | SC-115 | Span-loss vectors = TWO (BSP deadlock RETIRED) | [ ] |
| 116 | SC | SC-116 | SC-040 replacement verification uses span-count comparison | [ ] |
| 117 | SC | SC-117 | ADOT Extension crash produces ADOTExtensionUnavailable metric | [ ] |
| 118 | SC | SC-118 | IAM policy drift alarm fires within 15 minutes of change | [ ] |
| 119 | SC | SC-119 | Canary external heartbeat detects double-failure scenario | [ ] |
| 120 | SC | SC-120 | PutTraceSegments quota utilization monitoring active | [ ] |
| 121 | SC | SC-121 | FR-163 archival runbook accounts for 6-hour time window | [ ] |
| 122 | SC | SC-122 | Terraform CI check for X-Ray quota at 80% threshold | [ ] |
| 123 | SC | SC-123 | X-Ray encryption at rest documented | [ ] |
| 124 | SC | SC-124 | Centralized sampling rule scope documented | [ ] |
| 125 | SC | SC-125 | ADOT version upgrade runbook with 8 verification gates | [ ] |
| 126 | SC | SC-126 | PutTraceSegments quota monitoring distinguishes default vs applied | [ ] |
| 127 | SC | SC-127 | Sampling graduation document with 4 phases exists | [ ] |
| 128 | SC | SC-128 | Kill switch activation runbook with 5 threshold conditions | [ ] |
| 129 | SC | SC-129 | All 6 Lambdas tagged with deploy-sha, skew alarm configured | [ ] |
| 130 | SC | SC-130 | Span attribute allow-list enforced at creation time | [ ] |
| 131 | SC | SC-131 | Canary traces filterable via X-Ray Group | [ ] |
| 132 | SC | SC-132 | Annotation budget ≤50/trace with per-component limits | [ ] |
| 133 | SC | SC-133 | ADOT overhead budget documented with validation gates | [ ] |
| 134 | SC | SC-134 | FR-157 GitHub issue exists in repository | [ ] |
| 135 | SC | SC-135 | CI static analysis gate for set_attribute() + runtime audit SpanProcessor + AllowListViolation metric | [ ] |
| 136 | SC | SC-136 | TracerProvider SpanProcessor registration order verified by unit test | [ ] |
| 137 | SC | SC-137 | Annotation budget accounts for exception attributes (3 slots reserved per exception) | [ ] |
| 138 | SC | SC-138 | OTel Python SDK upgrade runbook with 7 verification gates exists | [ ] |
| 139 | SC | SC-139 | Powertools Tracer version pinned in requirements.txt | [ ] |
| 140 | SC | SC-140 | Canary detects ADOT Extension degraded state (mock Extension test) | [ ] |
| 141 | SC | SC-141 | Canary detection latency documented as 5-15 minutes with runbook | [ ] |
| 142 | SC | SC-142 | Per-Lambda sampling configuration documents API GW vs Function URL split | [ ] |
| 143 | SC | SC-143 | Deployment version skew tolerance window (15-min threshold, CI check) | [ ] |

### Round 24: Assumption Validation & Architecture Corrections

| # | Type | ID | Description | Status |
|---|------|-----|-------------|--------|
| 1 | FR | FR-200 | ADOT recovered panic vector retirement — amend FR-196 from recovered-panic to exporter-backend-error detection | [ ] |
| 2 | FR | FR-201 | ADOT exporter backend error span-loss vector #4 — Extension alive, spans dropped due to X-Ray API persistent 429/500 | [ ] |
| 3 | FR | FR-202 | Lambda platform shutdown window constraint — correct ADOT_LAMBDA_FLUSH_TIMEOUT references, 2s is SIGKILL not configurable | [ ] |
| 4 | FR | FR-203 | ADOT zero-processor architecture — document zero processors, Python SDK sole enforcement point | [ ] |
| 5 | FR | FR-204 | Requirements checklist completeness — backfill all FRs/SCs to 100% tracking coverage | [ ] |
| 6 | SC | SC-144 | OTel Collector source confirms no recover(), span-loss vector catalog updated | [ ] |
| 7 | SC | SC-145 | Canary detects ADOT exporter backend error state (mock 429 test) | [ ] |
| 8 | SC | SC-146 | All ADOT_LAMBDA_FLUSH_TIMEOUT references removed from spec and codebase | [ ] |
| 9 | SC | SC-147 | ADOT zero-processor confirmed, Python SDK documented as sole processing point | [ ] |
| 10 | SC | SC-148 | Requirements checklist contains 100% of spec FRs and SCs with tracking rows | [ ] |

## Round 20 Blind Spot Resolution Summary

| Blind Spot | Source | Resolution | New FR/SC |
|---|---|---|---|
| BSP deadlock span-loss vector | opentelemetry-python#3886 | Diagnostic differentiation in timeout path | FR-156, SC-106 |
| HL document staleness FR-154 violation | Observed failure across Rounds 16-20 | Retroactive enforcement + GitHub issue | FR-157, SC-107 |
| ADOT cold start unmeasured | opentelemetry-lambda#263 (no benchmarks) | Measurement gate + P95 < 2000ms budget | FR-158, SC-108 |
| ADOT Extension IAM gap | ADOT permissions documentation | 5 IAM actions enumerated | FR-159, SC-109 |
| RESPONSE_STREAM Extension lifecycle unverified | Absence of AWS documentation | Preprod verification gate | FR-160, SC-110 |
| Function URL 100% sampling cost risk | OTel sampler spec + X-Ray pricing | Centralized sampling rule + daily alarm | FR-161, SC-111 |
| SC-064 conflated failure modes | Spec analysis | Split into SC-064a + SC-064b | FR-156a, SC-064a/b |
| treat_missing_data per-alarm gap | CloudWatch docs, Well-Architected REL-06 | Exhaustive classification | FR-162, SC-112 |
| ADOT unauthenticated OTLP endpoint | ADOT permissions docs | Accepted risk — Lambda isolation | Edge case + assumption |
| X-Ray 30-day retention no archival | X-Ray quotas | Manual archival procedure | FR-163, SC-113 |
| Work order files stale since Round 7 | Observed failure since FR-132 | Synchronization enforcement | FR-164, SC-114 |

## Notes

- All 119 issues across fifteen rounds addressed (Round 15 requirements tracking added).
- Zero [NEEDS CLARIFICATION] markers in the spec.
- Round 3 added 8 new FRs (FR-031 through FR-038), 4 new SCs (SC-013 through SC-016), 7 new edge cases, 5 new assumptions, and 2 new user stories (US8, US9).
- Round 4 added 13 new FRs (FR-039 through FR-051), 6 new SCs (SC-017 through SC-022), 6 new edge cases, 4 new assumptions, and 2 new user stories (US10, US11).
- Round 5 added 7 new FRs (FR-052 through FR-058), 3 new SCs (SC-023 through SC-025), 6 new edge cases, 4 new assumptions.
- Round 6 added 3 new FRs (FR-059 through FR-061), 1 new SC (SC-026), 5 new edge cases, 4 new assumptions. 7 blind spots identified and resolved.
- Round 7 added 7 new FRs (FR-062 through FR-068), 2 new SCs (SC-027 through SC-028), 7 new edge cases, 6 new assumptions. 9 blind spots analyzed, 7 resolved via new FRs, 2 confirmed as non-risks.
- Round 8 added 5 new FRs (FR-069 through FR-073), 2 new SCs (SC-029, SC-030), 4 new edge cases, 5 new assumptions. FR-062 and FR-063 REWRITTEN. 1 Round 7 assumption INVALIDATED. 7 blind spots analyzed (5 resolved, 1 not a risk, 1 already addressed).
- Round 9 added 11 new FRs (FR-074 through FR-084), 8 new SCs (SC-031 through SC-038), 11 new edge cases, 8 new assumptions (+ 1 corrected). 1 Round 5 assumption CORRECTED (200ms → 5000ms BSP default). 14 blind spots analyzed across 4 research domains (ADOT container deployment, OTel SDK Lambda behavior, X-Ray canary implementation, frontend SSE migration). 12 resolved via new FRs, 2 confirmed as informational/not applicable.
- Round 10 added 7 new FRs (FR-085 through FR-091), 6 new SCs (SC-039 through SC-044), 7 new edge cases, 5 new assumptions (+ 1 corrected). FR-073's `max_queue_size` AMENDED from 512 to 1500 via FR-086. 12 blind spots analyzed from canonical-source deep research, all resolved.
- Round 12 added 7 new FRs (FR-100 through FR-106), 6 new SCs (SC-052 through SC-057), 5 new edge cases, 7 new assumptions (+ 1 invalidated). FR-098 metric filter pattern AMENDED via FR-105. Round 6 assumption about 512MB memory adequacy INVALIDATED. 9 blind spots analyzed (7 resolved via new FRs, 2 confirmed as non-risks).
- Round 13 updates: 1 CRITICAL + 4 HIGH + 2 MEDIUM blind spots found. 7 new FRs (FR-107–FR-113), 6 new SCs (SC-058–SC-063), 7 new edge cases, 5 new assumptions. Focus: deployment ordering, migration safety, rollback capability, X-Ray Groups configuration.
- Round 14 updates: 2 CRITICAL + 4 HIGH + 5 MEDIUM blind spots found. 10 new FRs (FR-114–FR-123), 10 new SCs (SC-064–SC-073), ~8 new edge cases, ~7 new assumptions. Focus: export safety, SSE event correlation, ADOT operational monitoring, annotation budgets, rollback procedures.
- **Round 15**: 2 CRITICAL + 4 HIGH + 4 MEDIUM blind spots found. 10 new FRs (FR-124-FR-133), 10 new SCs (SC-074-SC-083), ~8 new edge cases, ~7 new assumptions. Focus: silent failure path instrumentation, alarm threshold calibration, cascading false-green prevention, work order synchronization.
- Spec is now at 133 FRs, 83 SCs, ~96 edge cases, ~76 assumptions, 11 user stories.
- Four assumptions INVALIDATED (SendGrid auto-patching in Round 2, `begin_segment()` in Round 3, zero Lambda layers in Round 7, 512MB memory adequacy in Round 6/12), 2 CORRECTED (200ms BSP default in Round 5, BSP queue size in Round 10), 1 PARTIALLY INVALIDATED (finally block reliability in Round 11) marked with strikethrough.
- Three FRs REPLACED in-place (FR-025 revised, FR-026 replaced, FR-027 replaced) with Round 3 annotations.
- The most critical Round 3 finding is that the entire SSE streaming tracing architecture from Round 2 was built on a false assumption (`begin_segment()` works in Lambda). The corrected approach uses a Lambda Extension with an independent lifecycle.
- The most critical Round 4 finding is the "X-Ray exclusive for TRACING, not ALARMING" scope clarification (FR-039). X-Ray traces provide diagnostic context; CloudWatch alarms provide 24/7 alerting. Both are required because X-Ray sampling means not all errors have traces, while CloudWatch Lambda metrics capture 100% of invocations.
- Round 4 research confirmed: CloudFront is not in the architecture (Blind Spot 4 eliminated); ADOT sidecar-only mode is safe (Blind Spot 3 mitigated with constraints); X-Ray Groups are post-ingestion only (Blind Spot 2 confirmed — dual instrumentation required); out-of-band alerting is industry best practice for meta-observability (Blind Spot 6).
- The most critical Round 5 finding is that the OTel-to-X-Ray trace context bridging (FR-052) is a BLOCKER without which the entire ADOT streaming architecture produces disconnected traces. The AwsXRayLambdaPropagator is the single required component that reads `_X_AMZN_TRACE_ID` and bridges the Lambda runtime's X-Ray context into the OTel SDK's span hierarchy.
- Round 5 research confirmed: ADOT sidecar-only mode with `parentbased_always_on` sampler correctly honors Lambda sampling decisions (no orphaned spans); `BatchSpanProcessor` exports incrementally during streaming (1000ms batch timeout per FR-073; original 200ms assumption CORRECTED in Round 9); `force_flush()` handles only the final partial batch; X-Ray 64KB document limit is a real constraint requiring metadata truncation.
- The most critical Round 6 finding is the warm invocation stale trace context blind spot (FR-059). Lambda execution environments persist across invocations, but `_X_AMZN_TRACE_ID` updates per invocation. Without per-invocation context extraction, warm invocations inherit the previous request's trace ID, silently corrupting trace lineage across all warm-path requests.
- Round 6 also resolved a significant dual-emission blind spot: Powertools `auto_patch=True` and ADOT OTel both instrument botocore, producing duplicate subsegments for every AWS SDK call on the SSE Lambda. FR-060 explicitly requires `auto_patch=False` to ensure single-source instrumentation via ADOT only.
- The most critical Round 7 finding is that the OTel Python SDK's export failure handling is SILENT BY DESIGN — `force_flush()` returns success even when spans are lost. Combined with TracerProvider singleton lifecycle management (FR-065), these findings close the gap between the spec's architectural decisions and runtime operational reality.
- The most critical Round 8 finding is that the SSE Lambda is container-based (ECR image), not ZIP-deployed. Lambda container images CANNOT use Lambda Layers. FR-062 "collector-only layer" and FR-063 "version-pinned layer ARN" — both added in Round 7 — were built on a false assumption about the deployment model. This mirrors the Round 3 invalidation of `begin_segment()` — a foundational implementation assumption was wrong, requiring the approach to be rewritten. The corrected approach embeds ADOT in the Docker image via multi-stage build.
- The most critical Round 9 finding is the two-hop flush architecture (FR-074/FR-075). The ADOT Extension has a KNOWN ~30% span drop rate under worst-case timing (GitHub aws-otel-lambda#886). The spec's `force_flush()` (FR-055) reliably handles the SDK→Extension hop, but the Extension→X-Ray backend hop has a documented race condition where the collector context is canceled before HTTP exports complete. The decouple processor mitigates this but is not guaranteed. This is the first specification round where a KNOWN, UNFIXABLE limitation of a third-party component was formally documented as accepted risk with explicit detection (canary) rather than attempted workaround.
- Round 9's second critical finding is the canary error classification (FR-079). Without classifying `put_metric_data` errors as transient vs permanent, the canary's separate IAM role (FR-051) would fail to achieve its design purpose — detecting application IAM revocation would be delayed by multiple retry cycles instead of immediately escalated. This is a logic gap where two FRs (FR-049 and FR-051) were individually correct but their interaction was underspecified.
- Round 9 also corrected a factual error that persisted from Round 5: the BatchSpanProcessor default batch timeout was stated as 200ms but is actually 5000ms (FR-084). This caused 4 downstream references to contain incorrect timing calculations. While FR-073 correctly overrides to 1000ms (so runtime behavior was always correct), the incorrect assumption could have caused implementation confusion.
- The most critical Round 10 finding is the BatchSpanProcessor queue size miscalculation (FR-086). FR-073's original `max_queue_size=512` is INSUFFICIENT for the SSE Lambda's actual span throughput (~675 spans per 15-second invocation). The OTel Python SDK silently drops spans when the queue is full — no exception, no metric, only a WARNING log line. This is the third round where a runtime configuration was proven incorrect by throughput analysis (after Round 5's BSP default and Round 8's deployment model). FR-086 amends the queue to 1500 with FR-091 adding independent overflow detection.
- Round 10's second critical finding is the Lambda streaming after client disconnect behavior (FR-085). AWS explicitly states that streaming responses continue after client disconnects, and Python custom runtimes have no standard mechanism to detect disconnect (unlike Node.js). Without explicit BrokenPipeError handling, the SSE Lambda creates spans for phantom streams that inflate success metrics and waste DynamoDB capacity.
- Round 10's third critical finding is the canary IsPartial check gap (FR-087). The canary checks trace existence but not completeness — a trace with `IsPartial=true` may be missing all ADOT streaming-phase spans while appearing "found." This is a logic gap in the existing canary design where the verification is necessary but not sufficient.
- The most critical Round 12 finding is the post-proactive-flush generator behavior (FR-100). FR-093 correctly identified the need for proactive flush but left the generator's post-flush behavior unspecified. Without FR-100, the generator continues creating spans in the final ~3 seconds — these spans are either exported in the next BSP batch (if the Lambda doesn't timeout first) or permanently lost on SIGKILL. FR-100's graceful termination is strictly better than waiting for timeout because it converts a crash (SIGKILL, timeout Shutdown) into a clean exit (normal Shutdown), giving the ADOT Extension a guaranteed 2000ms to export all received spans.
- Round 12's second critical finding is the bootstrap context=None blind spot (FR-103). The SSE Lambda's custom bootstrap passes `None` for the Lambda context parameter, making the standard `context.get_remaining_time_in_millis()` API unavailable. FR-093's proactive flush explicitly references `Lambda-Runtime-Deadline-Ms` but the mechanism for the handler to ACCESS this value was never specified. FR-103 is a hard prerequisite for FR-093 — without it, the generator has no way to know when to flush.
- The most critical Round 14 finding is the `force_flush()` timeout enforcement gap (FR-114). OTel issue #4568 documents that the OTLP exporter blocks indefinitely when the ADOT Extension crashes or becomes unresponsive. The default 10-second timeout is per-retry, and with 6 retries across 24 batches, a worst-case `force_flush()` call could block for up to 24 minutes — far exceeding FR-093's 3000ms deadline budget. The `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2` env var caps per-request timeout at 2 seconds, bounding the worst case to a manageable window.
- Round 14's second critical finding is the BSP span destruction on export failure (FR-120). The BatchSpanProcessor pops spans from its queue BEFORE attempting export — if the export fails, those spans are permanently destroyed. Combined with `force_flush()` returning `True` regardless of export outcome (documented in Round 7 FR-066), this means the return value provides zero signal about data integrity. FR-120 establishes an annotation budget (max 25 of 50 per span) and documents the explicit assumption that `force_flush()` return value is NOT a health signal, reinforcing the canary (FR-078) as the only reliable export verification mechanism.
- Round 14 also closes a significant gap in SSE observability: event-level trace correlation (FR-115). The Round 4 audit flagged that SSE events lack trace IDs in payloads — HTTP headers correlate at connection level only, meaning individual SSE events cannot be tied to specific trace spans. FR-115 adds a `trace_id` field to SSE event JSON data, enabling per-event correlation in debugging workflows.
- Round 15's most impactful finding is the cascading false-green pattern (issues #118-119): when CloudWatch Metrics API experiences regional degradation, put_metric_data fails silently, custom metrics stop publishing, and alarms with treat_missing_data=notBreaching resolve to OK — creating a dashboard that shows all-green while the system is failing. The defense-in-depth solution uses three layers: (1) structured log fallback with CloudWatch Logs metric filter as out-of-band backup, (2) canary heartbeat piggybacked on production put_metric_data calls with treat_missing_data=breaching, and (3) composite alarm detecting INSUFFICIENT_DATA across heartbeat alarms. This pattern is validated by AWS Well-Architected REL-06 and documented in re:Invent 2023 OPS-301 ("Building resilient observability at scale").
- The second systemic finding is alarm threshold miscalibration (issues #120-121, #127): absolute-count error thresholds (>3/5min, >5/5min) are scale-dependent and become meaningless at high invocation volumes, while the analysis Lambda latency alarm at 25s (42% of 60s timeout) fires on healthy cold starts. The fix applies AWS Well-Architected PERF-04's 80%-of-timeout rule and converts all error alarms to percentage-based math expressions with a minimum invocation guard (>10) to prevent division artifacts at low traffic.
- **Round 16**: 2 CRITICAL + 5 HIGH + 3 MEDIUM blind spots found. 10 new FRs (FR-134–FR-143), 10 new SCs (SC-084–SC-093), 9 new edge cases, 6 new assumptions. Focus: alarm completeness for silent failure metrics, frontend trace header verification gates, canary out-of-band channel specification, SNS trace propagation verification, API Gateway latency alarms, force_flush() hard timeout enforcement, ADOT mid-stream crash detection.
- Spec is now at 143 FRs, 93 SCs, ~105 edge cases, ~82 assumptions, 11 user stories.
- Six assumptions still valid but REFINED: CloudWatch RUM FetchPlugin confirmed to inject headers pre-fetch without ReadableStream interference (source: FetchPlugin.ts source inspection); SNS AWSTraceHeader propagation confirmed but rawMessageDelivery mode strips it (source: AWS SNS docs); force_flush() timeout non-enforcement confirmed with 44s worst-case calculation (source: opentelemetry-python#4568, BSP source); sequential batch export confirmed by SDK source.
- Round 16's most critical finding is the alarm gap on FR-124's `SilentFailure/Count` metric (FR-134). FR-124 (Round 15) created a unified metric for 5 silent failure paths, and SC-019 expects CloudWatch alarms on these paths — but no FR actually creates the alarm. The metric is emitted but nobody is watching it. This is a specification-level gap where the metric FR and the alarm expectation (SC) were never connected by an alarm FR. FR-134 closes this gap. Additionally, FR-124's 5-path list conflicts with SC-004's 7-path list (FR-142 aligns them).
- Round 16's second critical finding is the frontend trace header verification gate (FR-135). The audit documented ZERO X-Ray trace header propagation on browser fetch() calls. Research confirmed CloudWatch RUM's FetchPlugin SHOULD inject headers (pre-fetch argument mutation, no ReadableStream interference), but injection silently fails if: (a) `addXRayTraceIdHeader` not configured, (b) URL not in `isUrlAllowed()` filter, (c) CORS rejects the header. No verification gate existed to catch this — the spec assumed it worked. FR-135 adds a Playwright-based Phase 3 deployment gate.
- Round 16 also specifies the canary's out-of-band alerting channel (FR-136) which was referenced 10+ times across 4 rounds but never defined. If the channel were a CloudWatch alarm, CloudWatch degradation would create a circular dependency — the monitoring system for "is monitoring working?" would itself be down. Cross-region SNS direct publish survives primary-region CloudWatch degradation.
- Round 16's force_flush() hard timeout (FR-139) closes a gap where FR-114's OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2 bounds per-REQUEST timeout but NOT total force_flush() duration. With 22 batches exported sequentially (confirmed by OTel SDK source), hung Extension → 44s total block, defeating FR-093's 3000ms proactive flush window. The thread-based wrapper (2500ms join timeout) is the standard Python pattern for enforcing hard timeouts on blocking calls.
- **Round 17**: 1 CRITICAL + 2 HIGH + 2 MEDIUM blind spots found. 3 new FRs (FR-144–FR-146), 3 new SCs (SC-094–SC-096), SC-064 amended, 4 new edge cases, 3 new assumptions. Focus: OTel manual span error status for X-Ray fault rendering (CRITICAL — `record_exception()` without `set_status(ERROR)` is invisible to X-Ray), canary FR-018 fail-fast exemption formalization, canary Lambda instrumentation scope. Research-validated claim: ADOT X-Ray exporter `makeCause()` is gated on `StatusCode.ERROR` (source: ADOT exporter `cause.go`). SC-064 amended to test hung-Extension scenario per FR-139. HL document updated to include Round 16 content that was stale since Round 15.
- Spec is now at 146 FRs, 96 SCs, ~109 edge cases, ~85 assumptions, 11 user stories.
- Five assumptions INVALIDATED (SendGrid auto-patching R2, begin_segment() R3, zero Lambda layers R7, 512MB memory R6/R12, force_flush return value R14), 2 CORRECTED (BSP default R5, BSP queue size R10), 1 PARTIALLY INVALIDATED (finally block reliability R11).
- **Round 18**: 2 CRITICAL + 3 HIGH + 4 MEDIUM blind spots found. 9 new FRs (FR-147–FR-155), 9 new SCs (SC-097–SC-105), 4 new edge cases, 3 new assumptions. Focus: cross-document consistency (FR-124 enumeration contradiction), frontend RUM initialization race condition, post-proactive-flush span orphaning, OTel error handling for caught vs uncaught exceptions, canary warm-invocation re-initialization, gate precedence clarification, scope statement formalization, staleness remediation enforcement, PII data minimization.
- Spec is now at 155 FRs, 105 SCs, ~113 edge cases, ~88 assumptions, 11 user stories.
- Round 18's most critical finding is the FR-124/FR-142 enumeration contradiction (FR-147). FR-124 says "five" silent failure paths but FR-142 corrected to 7 and FR-134 creates 7 alarms. An implementer following FR-124's text creates 5 metrics, leaving 2 alarm ARNs in permanent INSUFFICIENT_DATA. This is a DOCUMENTATION-ONLY fix but has OPERATIONAL impact — dangling alarms produce confusing dashboards where 2 of 7 alarms always show grey/unknown state.
- Round 18's second critical finding is the RUM initialization race (FR-148). FR-135's Playwright deployment gate passes because Playwright controls page load order. Production users with cold caches get non-deterministic `<script>` loading — application fetch() can fire before CloudWatch RUM patches window.fetch, silently dropping the X-Amzn-Trace-Id header on the SSE connection. This is a gate-vs-runtime distinction: the deployment gate verifies the MECHANISM exists but cannot catch the TIMING race.
- Research-validated claims: (1) OTel `start_as_current_span()` defaults `record_exception=True, set_status_on_exception=True` since v0.16b0 — but these ONLY fire for UNCAUGHT exceptions that propagate out of the `with` block; caught exceptions bypass automatic handling (source: OTel Python SDK `use_span()` implementation); (2) RUM FetchPlugin patches synchronously via shimmer but the AwsRum constructor itself loads asynchronously via CDN snippet (source: aws-rum-web FetchPlugin.ts); (3) Python module-level code executes once per process — Lambda warm invocations reuse the process (source: Python Language Reference, AWS Lambda execution model docs).
- Three new assumptions added, zero invalidated. The distinction between caught and uncaught exception handling in OTel context managers is a nuance that affects all 7 silent failure paths — these are ALL caught exceptions by design (they must not crash the SSE generator), so automatic error handling never fires for the most important error paths.
- Meta-observation: FR-132 (staleness tracking, Round 15) exists in a document that is itself stale — the HL document is 2 rounds behind with 13 missing risk entries and 39 missing SCs. FR-154 adds enforcement (GitHub issue creation + round-blocking) because detection-only staleness tracking demonstrably failed. This is the first FR created to fix a specification process failure rather than a system behavior gap.
- **Round 20**: 2 CRITICAL + 4 HIGH + 5 MEDIUM blind spots found. 9 new FRs (FR-156–FR-164, plus FR-156a informational), 9 new SCs (SC-106–SC-114), SC-064 SUPERSEDED and split into SC-064a + SC-064b, 8 new edge cases, 6 new assumptions. Focus: BSP deadlock as third span-loss vector, FR-154 staleness enforcement retroactive application, ADOT cold start measurement gap, ADOT IAM permission enumeration, RESPONSE_STREAM + Extension lifecycle verification, Function URL sampling cost guard, treat_missing_data exhaustive classification, X-Ray trace archival, work order synchronization enforcement.
- Spec is now at 164 FRs (+1 informational FR-156a), 114 SCs (+2 split SC-064a/b), ~121 edge cases, ~94 assumptions, 11 user stories.
- Zero assumptions INVALIDATED in Round 20. One foundational assumption IDENTIFIED as UNVERIFIED: ADOT Extension lifecycle during RESPONSE_STREAM (no canonical source — FR-160 mandates preprod verification).
- Round 20's most critical finding is the PROCESS INTEGRITY gap: FR-132 (detection, Round 15) and FR-154 (enforcement, Round 18) both exist but the HL document they govern is stale, and no GitHub issue was created as FR-154 mandates. This is the spec's first self-referential failure — a requirement about document freshness exists in a document that is itself stale. FR-157 breaks the cycle by requiring a GitHub issue as an external enforcement mechanism outside the spec itself.
- Round 20's second critical finding is the BSP deadlock (FR-156). This is the THIRD distinct span-loss vector: (1) ADOT Extension drop race — FR-074 accepted ~30% worst-case loss; (2) ADOT Extension hang — FR-139 thread wrapper aborts at 2500ms; (3) BSP internal deadlock — opentelemetry-python#3886, same FR-139 mitigation but different span fate (locked vs lost). The spec now explicitly acknowledges three span-loss vectors with distinct failure signatures and detection mechanisms.
- Round 20 UNIQUELY addresses category gaps deferred from previous rounds: Security (FR-159 IAM enumeration, unauthenticated OTLP edge case), Cost (FR-161 Function URL sampling guard), Performance (FR-158 cold start budget), and Operational completeness (FR-162 treat_missing_data, FR-163 archival, FR-164 work order sync). These were identified as gaps in the context carryover but never previously addressed.
- Research methodology: Round 20 used 6 canonical source research topics (ADOT cold start, ADOT IAM, X-Ray limits, BSP SIGKILL behavior, X-Ray sampling, RESPONSE_STREAM + Extension). The ADOT cold start research produced the finding that AWS publishes NO official benchmarks — the absence of data is itself a finding that motivates FR-158's measurement mandate. The RESPONSE_STREAM research produced the finding that AWS documentation does not address Extension lifecycle during streaming — the absence of documentation is itself a finding that motivates FR-160's verification gate. Five assumptions INVALIDATED across all 20 rounds (R2, R3, R7, R6/R12, R14), 2 CORRECTED (R5, R10), 1 PARTIALLY INVALIDATED (R11), 1 UNVERIFIED (R20).
- **Round 21**: 2 CRITICAL + 5 HIGH + 6 MEDIUM blind spots found. 13 new FRs (FR-165–FR-177), 11 new SCs (SC-115–SC-125), SC-064b/SC-106 amended, 12 new assumptions, 1 assumption CORRECTED (BSP deadlock). Focus: span-loss vector reclassification (BSP deadlock RETIRED, ADOT Extension non-recovery promoted), SC-040 verification method invalidation, IAM drift detection, canary dead-man detection, quota corrections.
- Spec is now at 177 FRs (+1 informational FR-156a), 125 SCs (+2 split SC-064a/b), ~134 edge cases, ~106 assumptions, 11 user stories.
- Round 21's most critical finding is the BSP deadlock RETIREMENT (FR-165). The spec's "three catalogued span-loss vectors" was a cornerstone risk model established in Round 20. Source code analysis of the installed OTel Python SDK v1.39.1 (`opentelemetry/sdk/_shared_internal/__init__.py`) revealed that opentelemetry-python#3886 was FIXED in SDK v1.33.0 — the entire `BatchSpanProcessor` was rewritten using `collections.deque` + `threading.Event` instead of the old `threading.Condition` with nested lock acquisition. The Round 20 assumption that the deadlock was a "known open issue" was based on the GitHub issue being open, but the fix was merged in v1.33.0 and the project pins v1.39.1. This reduces the risk model from THREE vectors to TWO — but the REPLACEMENT third vector (ADOT Extension crash non-recovery, FR-167) is arguably more severe: it causes 100% span loss on the affected sandbox for its remaining lifetime, not just a single flush failure.
- Round 21's second critical finding is the SC-040 verification method invalidation (FR-166). SC-040 says to verify zero "Queue is full" log entries during streaming. Source code analysis showed the v1.39.1 `BatchProcessor.emit()` uses `collections.deque([], max_queue_size)` where `appendleft()` silently evicts the oldest span with NO log, NO callback, NO metric. The `emit()` method contains an explicit comment referencing opentelemetry-python#4261: logging in `emit()` causes infinite recursion because log statements can be instrumented by OTel, routing back to `emit()`. This means the verification method specified in SC-040 can NEVER detect span drops on SDK v1.39.1+ — it always "passes" regardless of actual drops. FR-166 provides a replacement method using span-count comparison shims.
- Round 21 uniquely addresses OPERATIONAL HARDENING gaps: IAM drift detection (FR-168 — no AWS-native solution, requires AWS Config or CloudTrail EventBridge), canary dead-man detection (FR-169 — external heartbeat for double-failure scenario), ADOT upgrade runbook (FR-177 — 8 verification gates for container-based upgrades). These are operational concerns that would have surfaced during implementation but are cheaper to specify now.
- Research methodology: Round 21 used 4 parallel canonical source research agents: (1) X-Ray limits/quotas — corrected PutTraceSegments TPS from 2,600 to ~2,500, confirmed Groups/Sampling Rules quotas are adjustable, confirmed 6-hour GetTraceSummaries window, confirmed encryption-at-rest defaults; (2) ADOT Extension behavior — confirmed non-restart on crash, confirmed warm invocation near-zero overhead, confirmed OTLP endpoint unauthenticated; (3) OTel SDK edge cases — confirmed BSP deadlock fix in v1.33.0, confirmed silent deque drops, confirmed force_flush() timeout non-enforcement, confirmed OTLP HTTP exporter retry blocking; (4) Lambda scalability — confirmed one Extension per sandbox, confirmed PutMetricData 500 TPS limit, confirmed RUM X-Ray header injection, confirmed Function URL invisible in service map. Total research: 40+ canonical source citations across 4 domains.
- One assumption CORRECTED in Round 21 (BSP deadlock — was "known open issue", now "fixed in v1.33.0+"). One assumption RETIRED (BSP deadlock span-loss vector). One assumption REMAINS UNVERIFIED from Round 20 (ADOT Extension RESPONSE_STREAM lifecycle — FR-160 preprod gate still required). Zero assumptions INVALIDATED — Round 21 found corrections and documentation gaps rather than fundamental architectural misunderstandings.
- **Round 22**: 2 CRITICAL + 4 HIGH + 7 MEDIUM blind spots found. 13 new FRs (FR-178–FR-190), 9 new SCs (SC-126–SC-134), 8 new edge cases, 8 new assumptions, 1 assumption CORRECTED (PutTraceSegments TPS default). Focus: PutTraceSegments default TPS corrected from ~2,500 to 500 — peak traffic exceeds default quota (FR-178, CRITICAL); FR-157 GitHub issue confirmed non-existent (FR-190, CRITICAL); sampling graduation plan (FR-179); kill switch activation criteria (FR-180); Lambda env var update hazard (FR-181); deployment version skew detection (FR-182); ReadableSpan immutability (FR-183 — PII SpanProcessor impossible); span attribute allow-listing (FR-184); canary trace annotation standard (FR-185); annotation budget strategy (FR-186); ADOT overhead budget (FR-187); in-flight span loss flush window (FR-188); multi-account OAM (FR-189).
- Spec is now at 190 FRs (+1 informational FR-156a), 134 SCs (+2 split SC-064a/b), ~142 edge cases, ~114 assumptions, 11 user stories.
- Round 22 uniquely addresses OPERATIONAL PROCEDURE gaps: sampling graduation plan (FR-179 — no existing strategy for traffic growth), kill switch activation criteria (FR-180 — FR-059 provides mechanism without operational guidance), deployment version skew detection (FR-182 — Terraform partial apply leaves mixed versions undetected). These are operational concerns that would cause production incidents if discovered during implementation rather than specification.
- One assumption CORRECTED in Round 22 (PutTraceSegments TPS: ~2,500 documented in R21 → 500 default per AWS Service Quotas). Two assumptions UNVERIFIED: ADOT Extension collector contrib processor availability; ADOT_LAMBDA_FLUSH_TIMEOUT env var name and max value.
