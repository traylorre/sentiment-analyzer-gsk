# Specification Quality Checklist: X-Ray Exclusive Tracing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-02-14
**Feature**: [spec.md](../spec.md)
**Validation Iterations**: 5 (initial draft + round 1 review + round 2 deep-dive + round 3 blind spot analysis + round 4 audit gap analysis)

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

## Notes

- All 41 issues across four rounds addressed.
- Zero [NEEDS CLARIFICATION] markers in the spec.
- Round 3 added 8 new FRs (FR-031 through FR-038), 4 new SCs (SC-013 through SC-016), 7 new edge cases, 5 new assumptions, and 2 new user stories (US8, US9).
- Round 4 added 13 new FRs (FR-039 through FR-051), 6 new SCs (SC-017 through SC-022), 6 new edge cases, 4 new assumptions, and 2 new user stories (US10, US11).
- Two assumptions INVALIDATED (SendGrid auto-patching in Round 2, `begin_segment()` in Round 3) marked with strikethrough.
- Three FRs REPLACED in-place (FR-025 revised, FR-026 replaced, FR-027 replaced) with Round 3 annotations.
- Spec is now at 51 FRs, 22 SCs, 26 edge cases, 18 assumptions (2 invalidated), 11 user stories.
- The most critical Round 3 finding is that the entire SSE streaming tracing architecture from Round 2 was built on a false assumption (`begin_segment()` works in Lambda). The corrected approach uses a Lambda Extension with an independent lifecycle.
- The most critical Round 4 finding is the "X-Ray exclusive for TRACING, not ALARMING" scope clarification (FR-039). X-Ray traces provide diagnostic context; CloudWatch alarms provide 24/7 alerting. Both are required because X-Ray sampling means not all errors have traces, while CloudWatch Lambda metrics capture 100% of invocations.
- Round 4 research confirmed: CloudFront is not in the architecture (Blind Spot 4 eliminated); ADOT sidecar-only mode is safe (Blind Spot 3 mitigated with constraints); X-Ray Groups are post-ingestion only (Blind Spot 2 confirmed — dual instrumentation required); out-of-band alerting is industry best practice for meta-observability (Blind Spot 6).
