# Specification Quality Checklist: X-Ray Exclusive Tracing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-02-14
**Feature**: [spec.md](../spec.md)
**Validation Iterations**: 11 (initial draft + round 1 review + round 2 deep-dive + round 3 blind spot analysis + round 4 audit gap analysis + round 5 ADOT architecture deep-dive + round 6 blind spot fixes + round 7 ADOT operational lifecycle deep-dive + round 8 container-based deployment blind spot analysis + round 9 four-domain deep research + round 10 canonical-source blind spot analysis)

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

## Notes

- All 91 issues across ten rounds addressed.
- Zero [NEEDS CLARIFICATION] markers in the spec.
- Round 3 added 8 new FRs (FR-031 through FR-038), 4 new SCs (SC-013 through SC-016), 7 new edge cases, 5 new assumptions, and 2 new user stories (US8, US9).
- Round 4 added 13 new FRs (FR-039 through FR-051), 6 new SCs (SC-017 through SC-022), 6 new edge cases, 4 new assumptions, and 2 new user stories (US10, US11).
- Round 5 added 7 new FRs (FR-052 through FR-058), 3 new SCs (SC-023 through SC-025), 6 new edge cases, 4 new assumptions.
- Round 6 added 3 new FRs (FR-059 through FR-061), 1 new SC (SC-026), 5 new edge cases, 4 new assumptions. 7 blind spots identified and resolved.
- Round 7 added 7 new FRs (FR-062 through FR-068), 2 new SCs (SC-027 through SC-028), 7 new edge cases, 6 new assumptions. 9 blind spots analyzed, 7 resolved via new FRs, 2 confirmed as non-risks.
- Round 8 added 5 new FRs (FR-069 through FR-073), 2 new SCs (SC-029, SC-030), 4 new edge cases, 5 new assumptions. FR-062 and FR-063 REWRITTEN. 1 Round 7 assumption INVALIDATED. 7 blind spots analyzed (5 resolved, 1 not a risk, 1 already addressed).
- Round 9 added 11 new FRs (FR-074 through FR-084), 8 new SCs (SC-031 through SC-038), 11 new edge cases, 8 new assumptions (+ 1 corrected). 1 Round 5 assumption CORRECTED (200ms → 5000ms BSP default). 14 blind spots analyzed across 4 research domains (ADOT container deployment, OTel SDK Lambda behavior, X-Ray canary implementation, frontend SSE migration). 12 resolved via new FRs, 2 confirmed as informational/not applicable.
- Round 10 added 7 new FRs (FR-085 through FR-091), 6 new SCs (SC-039 through SC-044), 7 new edge cases, 5 new assumptions (+ 1 corrected). FR-073's `max_queue_size` AMENDED from 512 to 1500 via FR-086. 12 blind spots analyzed from canonical-source deep research, all resolved.
- Three assumptions INVALIDATED (SendGrid auto-patching in Round 2, `begin_segment()` in Round 3, zero Lambda layers in Round 7), 1 CORRECTED (200ms BSP default in Round 5), and 1 AMENDED (BSP queue size in Round 10) marked with strikethrough.
- Three FRs REPLACED in-place (FR-025 revised, FR-026 replaced, FR-027 replaced) with Round 3 annotations.
- Spec is now at 91 FRs, 44 SCs, 63 edge cases, 50 assumptions (3 invalidated, 2 corrected/amended), 11 user stories.
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
