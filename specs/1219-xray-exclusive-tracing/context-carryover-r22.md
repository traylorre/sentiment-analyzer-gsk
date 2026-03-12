# Context Carryover: X-Ray Exclusive Tracing Specification

Date: 2026-03-03
Branch: B-blind-spot-fixes (terraform-gsk-template repo)
Spec Feature Branch: 1219-xray-exclusive-tracing (sentiment-analyzer-gsk repo)
Last Completed Round: 22
Next Round: 23

---
## Spec Metrics (Post-Round 22)

| Metric | Count |
|---|---|
| Functional Requirements | 190 (FR-001 through FR-190, +FR-156a informational) |
| Success Criteria | 134 (SC-001 through SC-134, +SC-064a/b split) |
| Edge Cases | ~142 |
| Assumptions | ~114 (5 invalidated, 4 corrected, 1 partially invalidated, 1 retired, 2 unverified) |
| User Stories | 11 |
| Emergent Issue Rounds | 21 (Rounds 2-18, 20-22; no Rounds 1, 19) |
| Tasks (work orders) | 17 (all TODO status) |
| Fix work order files | 17 (fix-*.md) |

---
## Design Principles (IMMUTABLE)

1. X-Ray EXCLUSIVE for tracing — one single non-X-Ray method allowed ONLY for "who watches the watcher" validation
2. NO FALLBACKS — fail fast. If X-Ray breaks, Lambda breaks. Sole exception: canary (Task 11) must survive X-Ray failures to report them
3. Traces are CRUCIAL for debugging live issues — they power observability tools
4. Breaking changes are FINE — no backwards compatibility concerns
5. Use canonical sources to validate any new architectural claims

---
## File Paths (All in sentiment-analyzer-gsk repo)

| File | Path | Lines |
|---|---|---|
| Spec | specs/1219-xray-exclusive-tracing/spec.md | ~1300 |
| Requirements Checklist | specs/1219-xray-exclusive-tracing/checklists/requirements.md | ~650 |
| HL Remediation Checklist | docs/x-ray/HL-x-ray-remediation-checklist.md | ~780 |
| Audit Document | docs/audit/2026-02-13-playwright-coverage-observability-blind-spots.md | ~400 |
| Fix Work Orders | docs/x-ray/fix-*.md (17 files) | varies |
| Context Carryover R22 | CONTEXT-CARRYOVER-R22-xray-exclusive-tracing.md | this file |

---
## HL Document Staleness (Post-Round 22)

ALL SECTIONS CURRENT THROUGH ROUND 22:
- Executive Summary: Round 22 ✓ (3 new R22 BUT entries)
- Risk Assessment table: Round 22 ✓ (13 new R22 risk entries)
- Success Criteria section: Round 22 ✓ (SC-126 through SC-134)
- Component Coverage Map: Round 20 ✓ (no new components in R21/R22)
- Progress Log: Round 22 ✓
- Work Order table: Round 20 ✓ (no new task-to-FR mappings in R21/R22 — FR-165-FR-190 are spec-level/operational, not task-mapped)

Spec Status Line: Round 22 ✓ (fixed from stale "Round 20" in this round)
Requirements Checklist: Round 22 ✓ (backfilled R21 FR-165–FR-177/SC-115–SC-125 + added R22 FR-178–FR-190/SC-126–SC-134)

---
## THREE Catalogued Span-Loss Vectors (Unchanged from Round 21)

| Vector | FR | Mechanism | Span Fate |
|---|---|---|---|
| ADOT Extension drop race | FR-074 | Collector context canceled before HTTP export completes | ~30% worst-case loss, detected by canary |
| ADOT Extension hang | FR-139 | TCP accept, no OTLP response; thread wrapper aborts at 2500ms | Spans dequeued from BSP, held by exporter, lost in exporter memory |
| ADOT Extension crash | FR-167 | Extension process crashes (OOM/segfault); NOT restarted within execution environment | 100% span loss on affected sandbox for remaining lifetime (~5-15 min) |

**RETIRED Vector**: BSP internal deadlock (FR-156) — opentelemetry-python#3886 FIXED in SDK v1.33.0+. Project pins v1.39.1. FR-165 amends.

---
## Invalidated/Corrected Assumptions (All Rounds)

1. SendGrid auto-patching (Round 2) — uses urllib not httpx
2. begin_segment() works in Lambda (Round 3) — documented no-op
3. Zero Lambda layers on SSE Lambda (Round 7) — container-based, can't use layers
4. 512MB memory sufficient (Round 6/12) — ADOT overhead requires 1024MB
5. force_flush() return value reliable (Round 14) — returns True regardless of export outcome
6. BSP default batch timeout 200ms (Round 5, corrected Round 9) — actually 5000ms
7. BSP queue size 512 sufficient (Round 10) — needs 1500 for ~675 spans/invocation
8. finally blocks reliably execute (Round 11, partially invalidated) — NOT on Lambda timeout SIGKILL
9. ADOT Extension alive during RESPONSE_STREAM (Round 20, UNVERIFIED) — no canonical source confirms; FR-160 mandates preprod verification
10. BSP deadlock is active span-loss vector (Round 20, CORRECTED Round 21) — FIXED in SDK v1.33.0+; FR-165 retires vector
11. PutTraceSegments ~2,500 TPS default (Round 21, CORRECTED Round 22) — AWS default is 500 TPS; ~2,500 may be account-specific increase

---
## Confirmed Architectural Decisions

- SSE Lambda: Container-based (ECR, NOT ZIP/Layers), custom bootstrap, RESPONSE_STREAM mode
- ADOT: Embedded in Docker image via multi-stage build (NOT Lambda Layer — containers can't use layers)
- OTel SDK: Module-level TracerProvider singleton, per-invocation propagate.extract(), BatchSpanProcessor with queue=1500, batch=64, schedule=1000ms
- Flush: Two-hop (SDK→Extension via OTLP localhost:4318, Extension→X-Ray API). Known ~30% drop rate under worst-case timing (aws-otel-lambda#886)
- Proactive flush: FR-093 at 3000ms remaining, FR-139 thread wrapper at 2500ms hard timeout, FR-100 graceful event:deadline termination
- Sampler: parentbased_always_on (honors Lambda sampling decision)
- Non-streaming Lambdas: Powertools Tracer with auto_patch=True
- SSE Lambda: OTel manual spans with auto_patch=False (prevents dual-emission)
- Canary: Powertools Tracer wrapped in FR-145 error handling, cross-region SNS for alerts, exempt from FR-018 fail-fast
- BSP span drop: SILENT — deque evicts oldest span with no log/callback/metric (OTel design, #4261)
- ADOT Extension: NOT restarted on crash within execution environment
- Centralized sampling rules: Control Function URL/EventBridge Lambdas only; no effect on API Gateway Lambdas
- X-Ray PutTraceSegments: **500 TPS/region default** (adjustable via Service Quotas L-AB6D2D9B; ~2,500 may be account-specific)
- X-Ray encryption: Default AWS-managed key; optional CMK via PutEncryptionConfig
- OTel Python ReadableSpan: IMMUTABLE after end() — PII redaction via SpanProcessor on_end() impossible
- PII prevention: Attribute allow-listing at creation time via SpanProcessor.on_start() (only mutable point)
- Canary trace marking: annotation.synthetic = true with X-Ray Group filter

---
## Round 22 Additions (Most Recent)

### 13 New FRs (FR-178 through FR-190)

| FR | Priority | Summary |
|---|---|---|
| FR-178 | P0 CRITICAL | PutTraceSegments default TPS CORRECTED from ~2,500 to 500 — amends FR-170 |
| FR-179 | P1 HIGH | Sampling graduation plan with 4 phases and threshold-based transitions |
| FR-180 | P1 HIGH | Kill switch activation criteria: 5 threshold conditions documented |
| FR-181 | P1 HIGH | Lambda update-function-configuration REPLACES ALL env vars — hazard documented |
| FR-182 | P1 HIGH | Deployment version tagging with deploy-sha and skew detection alarm |
| FR-183 | P1 HIGH | OTel Python ReadableSpan immutability — PII SpanProcessor impossible |
| FR-184 | P1 HIGH | Span attribute allow-listing at creation via SpanProcessor.on_start() |
| FR-185 | P1 HIGH | Canary trace annotation standard: synthetic=true + X-Ray Group filters |
| FR-186 | P2 MEDIUM | Annotation budget strategy: 50/trace limit with per-component allocation |
| FR-187 | P2 MEDIUM | ADOT resource overhead formal budget: 35-70 MB, 200-500ms cold start |
| FR-188 | P2 MEDIUM | In-flight span loss: 2s default flush window, ADOT_LAMBDA_FLUSH_TIMEOUT=10s |
| FR-189 | P2 MEDIUM | Multi-account X-Ray via CloudWatch OAM documentation (future-state) |
| FR-190 | P0 CRITICAL | FR-157 GitHub issue MUST be filed — SC-107 requirement unfulfilled |

### 9 New SCs (SC-126 through SC-134)

SC-126 (PutTraceSegments default vs applied quota), SC-127 (sampling graduation phases), SC-128 (kill switch activation runbook), SC-129 (deployment version tagging + skew alarm), SC-130 (span attribute allow-list enforcement), SC-131 (canary traces filterable via X-Ray Group), SC-132 (annotation budget ≤50/trace), SC-133 (ADOT overhead budget with validation gates), SC-134 (FR-157 GitHub issue exists)

### 1 Corrected Assumption

- PutTraceSegments TPS "~2,500 default" (Round 21) → CORRECTED to **500 TPS default** (AWS Service Quotas canonical). Account-specific increase to ~2,500 may have been applied.

### 2 UNVERIFIED Assumptions

- ADOT Lambda Extension collector does NOT include contrib processors (e.g., redaction processor) — no canonical source confirms
- ADOT_LAMBDA_FLUSH_TIMEOUT environment variable name and 10s max — from GitHub issues, not official AWS docs

### 8 New Assumptions

1. PutTraceSegments default is 500 TPS per region (AWS Service Quotas L-AB6D2D9B)
2. OTel Python SDK ReadableSpan.attributes is immutable after end()
3. ADOT Lambda Extension collector may not include contrib processors (UNVERIFIED)
4. Lambda update-function-configuration replaces ALL env vars (not merge)
5. ADOT crash → Lambda terminates execution environment (Extensions API)
6. ADOT SHUTDOWN flush window 2s default, 10s max via ADOT_LAMBDA_FLUSH_TIMEOUT (UNVERIFIED)
7. GetTraceSummaries has no MaxResults parameter (service-controlled page size)
8. W3C Trace Context has no synthetic flag (only sampled bit)

### 8 New Edge Cases

1. Sampling rate change during active invocation — sampling decision at span creation, not export
2. Kill switch during active SSE streaming — takes effect on next cold start only
3. PII in auto-captured exception stack traces — exception.message may contain user data
4. Canary annotation not set due to instrumentation error — pollutes production Group
5. 51st annotation on trace — X-Ray silently ignores excess (no error response)
6. Deployment version skew persists through sandbox recycling (~5-15 min window)
7. update-function-configuration with empty Variables map — deletes ALL env vars
8. GetTraceSummaries Sampling=true during archival — returns subset, loses traces

---
## Category Gaps Status (Updated Round 22)

| Category | Status | What Exists | What's Still Missing |
|---|---|---|---|
| Security | Addressed (R18, R20, R21, R22) | FR-155 (PII), FR-159 (IAM), FR-168 (drift), FR-183/FR-184 (ReadableSpan/allow-list) | Runtime PII regex scanning at collector level (ADOT contrib processor availability UNVERIFIED) |
| Cost | Addressed (R20, R21, R22) | FR-038 (cost guard), FR-161 (Function URL), FR-170/FR-178 (TPS quota), FR-187 (ADOT budget) | Per-environment X-Ray cost attribution |
| Performance | Addressed (R20, R21, R22) | FR-131 (alarms), FR-158 (cold start), FR-187 (ADOT overhead budget), warm invocation confirmed near-zero | Formal P50/P95/P99 latency budgets for ALL Lambdas |
| Scalability | Addressed (R22) | FR-178 (TPS corrected), FR-179 (sampling graduation), FR-186 (annotation budget) | Shard key strategy for high-cardinality annotations |
| Process Integrity | Addressed (R20, R22) | FR-132 (detection), FR-154 (enforcement), FR-157 (retroactive), FR-164 (work orders), FR-190 (issue filing) | FR-157 GitHub issue MUST still be filed (FR-190 mandates) |
| Operational | Addressed (R21, R22) | FR-177 (ADOT upgrade), FR-180 (kill switch criteria), FR-181 (env var hazard), FR-182 (skew detection), FR-188 (flush window) | Kill switch activation drill/runbook validation |
| Observability | NEW (R22) | FR-185 (canary annotation), FR-186 (annotation budget) | Canary trace volume impact on X-Ray cost |

---
## 17 Tasks (All TODO — Unchanged)

| Task | File | Description |
|---|---|---|
| 1 | fix-iam-permissions.md | Fix IAM Permissions for X-Ray |
| 2 | fix-metrics-lambda-xray.md | Fix Metrics Lambda X-Ray Instrumentation |
| 3 | fix-sns-trace-verification.md | Verify SNS Cross-Lambda Trace Propagation |
| 4 | fix-silent-failure-subsegments.md | Fix Silent Failure Path Subsegments |
| 5 | fix-sse-subsegments.md | Fix SSE Streaming Lambda Tracing (ADOT Extension) |
| 6 | fix-sse-latency-xray.md | Replace latency_logger with X-Ray Annotations |
| 7 | fix-sse-cache-xray.md | Replace cache_logger with X-Ray Annotations |
| 8 | fix-sse-annotations.md | Add SSE Connection and Polling Annotations |
| 9 | fix-correlation-id-consolidation.md | Consolidate Correlation IDs onto X-Ray Trace IDs |
| 10 | fix-frontend-trace-headers.md | Add Frontend Trace Header Propagation |
| 11 | fix-xray-canary.md | Implement Observability Canary |
| 12 | fix-downstream-consumer-audit.md | Audit Downstream Consumers of Removed Systems |
| 13 | fix-sendgrid-explicit-subsegment.md | Add Explicit SendGrid X-Ray Subsegment |
| 14 | fix-tracer-standardization.md | Standardize on Powertools Tracer |
| 15 | fix-sse-client-fetch-migration.md | Migrate Frontend SSE Client to fetch()+ReadableStream |
| 16 | fix-sampling-and-cost.md | Configure Sampling Strategy and Cost Guard |
| 17 | fix-alarm-coverage.md | CloudWatch Alarm Coverage |

Work order staleness: Fix files contain only Round 1-6 FRs. 120+ FRs from Rounds 7-22 mapped in HL doc but missing from implementation guides. FR-164 mandates synchronization before implementation.

---
## Key Canonical Sources Confirmed (Round 22)

### New in Round 22
- AWS X-Ray Service Quotas — PutTraceSegments default 500 TPS (L-AB6D2D9B, adjustable)
- OTel Python SDK ReadableSpan — immutable after end(), on_end() receives read-only view
- OTel specification — OTEL_SDK_DISABLED creates NoOp providers (zero overhead)
- AWS Lambda API — UpdateFunctionConfiguration replaces ALL env vars (not merge)
- AWS Lambda Extensions API — SHUTDOWN event, 2s default timeout
- W3C Trace Context Level 1 — Section 3.2.2.5: only sampled flag, no synthetic flag
- AWS CloudWatch OAM — cross-account X-Ray via source/sink linking
- OTel Collector contrib — redaction processor for attribute allow-listing/regex blocking
- OTel Python SDK — SpanProcessor.on_start() receives mutable Span; on_end() receives ReadableSpan

### Carried from Round 21
- OTel Python SDK v1.39.1 `_shared_internal/__init__.py` — BatchProcessor rewrite, deque-based, silent drops
- opentelemetry-python#3886 — BSP deadlock FIXED in v1.33.0
- opentelemetry-python#4261 — Logging in emit() causes infinite recursion
- opentelemetry-python#4568 — force_flush() timeout NOT enforced at BSP level
- AWS Lambda Extensions API — Extensions not restarted on crash
- AWS X-Ray Service Quotas — PutTraceSegments 500 TPS default (adjustable, L-AB6D2D9B), Groups 25/region (adjustable, L-F895D63C), Rules 25/region (adjustable, L-B5F5E1ED)
- AWS X-Ray Developer Guide — Encryption at rest (default AWS-managed key)
- X-Ray API Reference — GetTraceSummaries 6-hour window, 30 TPS, 100/page, no MaxResults
- OTel SDK sampling.py — ParentBased delegation logic (centralized rules at root only)
- CloudWatch RUM — Confirmed X-Ray header injection with enableXRay: true
- OTLP HTTP exporter — 6 retries, exp backoff, blocks BSP worker, 429 NOT retried
- AwsLambdaResourceDetector — Reads os.environ on detect() but Resource cached at cold start
- OTel BoundedAttributes — Silent truncation, no log on drop, popitem(last=False)

---
## Potential Round 23 Focus Areas

1. **FR-157 GitHub issue filing** — FR-190 mandates filing but issue not yet created; SC-134 verification pending
2. **ADOT contrib processor availability** — FR-183 constraint assumes ADOT Extension lacks redaction processor; needs canonical verification against ADOT image manifest
3. **ADOT_LAMBDA_FLUSH_TIMEOUT verification** — FR-188 cites 2s default/10s max from GitHub issues; needs verification against official ADOT documentation or source code
4. **Sampling graduation implementation details** — FR-179 defines 4 phases but lacks per-Lambda sampler configuration (API Gateway Lambdas vs Function URL Lambda behave differently per FR-175)
5. **Kill switch activation drill** — FR-180 defines criteria but no operational drill/runbook has been written or tested
6. **Span attribute allow-list per Lambda** — FR-184 requires per-Lambda allow-lists but no concrete key lists have been specified
7. **Annotation budget allocation validation** — FR-186 proposes per-component limits but no validation that current FRs' annotation usage fits within budget
8. **Deployment version skew tolerance window** — FR-182 requires skew detection but rolling updates create transient skew; tolerance window undefined
9. **Formal P50/P95/P99 latency budgets** — Performance category gap persists; no formal latency budget for ALL Lambdas with ADOT overhead factored in
10. **Canary trace volume cost impact** — FR-185 marks canary traces as synthetic but they still consume PutTraceSegments TPS and incur X-Ray charges; cost impact unquantified
