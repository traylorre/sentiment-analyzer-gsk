# Context Carryover: X-Ray Exclusive Tracing Specification

Date: 2026-03-03
Branch: B-blind-spot-fixes (terraform-gsk-template repo)
Spec Feature Branch: 1219-xray-exclusive-tracing (sentiment-analyzer-gsk repo)
Last Completed Round: 21
Next Round: 22

---
## Spec Metrics (Post-Round 21)

| Metric | Count |
|---|---|
| Functional Requirements | 177 (FR-001 through FR-177, +FR-156a informational) |
| Success Criteria | 125 (SC-001 through SC-125, +SC-064a/b split) |
| Edge Cases | ~134 |
| Assumptions | ~106 (5 invalidated, 3 corrected, 1 partially invalidated, 1 unverified, 1 retired) |
| User Stories | 11 |
| Emergent Issue Rounds | 20 (Rounds 2-18, 20-21; no Rounds 1, 19) |
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
| Spec | specs/1219-xray-exclusive-tracing/spec.md | ~1150 |
| Requirements Checklist | specs/1219-xray-exclusive-tracing/checklists/requirements.md | ~600 |
| HL Remediation Checklist | docs/x-ray/HL-x-ray-remediation-checklist.md | ~720 |
| Audit Document | docs/audit/2026-02-13-playwright-coverage-observability-blind-spots.md | ~400 |
| Fix Work Orders | docs/x-ray/fix-*.md (17 files) | varies |
| Context Carryover R21 | specs/1219-xray-exclusive-tracing/context-carryover-r21.md | this file |

---
## HL Document Staleness (Post-Round 21)

ALL SECTIONS CURRENT THROUGH ROUND 21:
- Executive Summary: Round 21 ✓
- Risk Assessment table: Round 21 ✓ (13 new R21 risk entries)
- Success Criteria section: Round 21 ✓ (SC-115 through SC-125)
- Component Coverage Map: Round 20 ✓ (no new components in R21)
- Progress Log: Round 21 ✓
- Work Order table: Round 20 ✓ (no new task-to-FR mappings in R21 — FR-165-FR-177 are spec-level/operational, not task-mapped)

---
## TWO Catalogued Span-Loss Vectors (Updated Round 21)

| Vector | FR | Mechanism | Span Fate |
|---|---|---|---|
| ADOT Extension drop race | FR-074 | Collector context canceled before HTTP export completes | ~30% worst-case loss, detected by canary |
| ADOT Extension hang | FR-139 | TCP accept, no OTLP response; thread wrapper aborts at 2500ms | Spans dequeued from BSP, held by exporter, lost in exporter memory |
| ADOT Extension crash (NEW R21) | FR-167 | Extension process crashes (OOM/segfault); NOT restarted within execution environment | 100% span loss on affected sandbox for remaining lifetime (~5-15 min) |

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
- X-Ray PutTraceSegments: ~2,500 TPS/region default (adjustable via Service Quotas)
- X-Ray encryption: Default AWS-managed key; optional CMK via PutEncryptionConfig

---
## Round 21 Additions (Most Recent)

### 13 New FRs (FR-165 through FR-177)

| FR | Priority | Summary |
|---|---|---|
| FR-165 | P0 CRITICAL | BSP deadlock vector RETIRED — opentelemetry-python#3886 fixed in SDK v1.33.0+; structured log label amended to "extension_hang" |
| FR-166 | P0 CRITICAL | SC-040 verification method INVALID — SDK v1.39.1 deque silently drops spans; replacement uses span-count comparison shim |
| FR-167 | P1 HIGH | ADOT Extension non-recovery documented as span-loss vector #3; 100% loss on affected sandbox |
| FR-168 | P1 HIGH | IAM policy drift detection via AWS Config or CloudTrail EventBridge for X-Ray permissions |
| FR-169 | P1 HIGH | Canary dead-man external health check for double-failure detection |
| FR-170 | P1 HIGH | PutTraceSegments TPS corrected to ~2,500 (adjustable); monitoring via UnprocessedTraceSegments alarm |
| FR-171 | P2 MEDIUM | OTLP exporter retry-induced BSP worker block documented (up to 10s) |
| FR-172 | P2 MEDIUM | X-Ray Groups and Sampling Rules quota tracking with CI check at 80% threshold |
| FR-173 | P2 MEDIUM | X-Ray encryption-at-rest documentation (default AWS-managed key; CMK available) |
| FR-174 | P2 MEDIUM | GetTraceSummaries 6-hour time window constraint for FR-163 archival procedure |
| FR-175 | P2 MEDIUM | Centralized sampling rule scope documentation (controls Function URL/EventBridge only) |
| FR-176 | P2 MEDIUM | Lambda Function URL invisible in X-Ray service map documentation |
| FR-177 | P2 MEDIUM | ADOT version upgrade runbook with 8 verification gates |

### 11 New SCs (SC-115 through SC-125)

SC-115 (span-loss vectors = TWO, BSP retired), SC-116 (SC-040 replacement verification), SC-117 (Extension crash persistent metric), SC-118 (IAM drift alarm), SC-119 (external canary heartbeat), SC-120 (PutTraceSegments quota alarm), SC-121 (archival time estimation), SC-122 (Groups/Rules quota CI check), SC-123 (encryption documentation), SC-124 (sampling scope documentation), SC-125 (ADOT upgrade runbook)

### Amended SCs

- SC-064b: Log label changed from "bsp_or_extension_hang" to "extension_hang"
- SC-106: BSP deadlock removed from timeout cause list; label amended to "extension_hang"

### 12 New Assumptions

1. BSP deque silent drop behavior (OTel #4261)
2. ADOT Extension non-restart on crash
3. OTLP HTTP exporter retry behavior (6 retries, exp backoff, blocks BSP worker)
4. X-Ray quotas corrected (PutTraceSegments ~2,500 TPS adjustable, Groups/Rules 25/region adjustable)
5. X-Ray encryption at rest defaults
6. GetTraceSummaries 6-hour window, 30 TPS, 100/page
7. Centralized sampling rules scope (root spans only)
8. Function URL invisible in service map
9. CloudWatch RUM X-Ray header injection confirmed
10. AwsLambdaResourceDetector caches at cold start
11. OTel span attribute limits (128 attrs, no default value length limit, silent truncation)
12. ADOT warm invocation overhead effectively zero

### 1 Corrected Assumption

- BSP deadlock (opentelemetry-python#3886): Was "known open issue" → FIXED in SDK v1.33.0+

---
## Category Gaps Status (Updated Round 21)

| Category | Status | What Exists | What's Still Missing |
|---|---|---|---|
| Security | Addressed (R18, R20, R21) | FR-155 (PII), FR-159 (IAM), FR-168 (drift detection), encryption documented | Automated PII scanning in traces, dependency injection threat model formalization |
| Cost | Addressed (R20, R21) | FR-038 (cost guard), FR-161 (Function URL guard), FR-170 (TPS quota), FR-172 (Groups quota) | Per-environment X-Ray cost attribution, ADOT resource overhead cost quantification |
| Performance | Addressed (R20, R21) | FR-131 (alarms), FR-158 (cold start budget), warm invocation confirmed near-zero | Formal P50/P95/P99 latency budgets for ALL Lambdas, warm invocation with ADOT cold start interaction |
| Scalability | Partially Addressed (R21) | TPS quota corrected and monitoring added (FR-170), quota tracking (FR-172) | Sampling graduation plan for 10x traffic growth, shard key strategy for high-cardinality annotations |
| Process Integrity | Addressed (R20) | FR-132 (detection), FR-154 (enforcement), FR-157 (retroactive), FR-164 (work orders) | GitHub issue for FR-157 not yet verified as created |
| Operational | Addressed (R21) | FR-177 (ADOT upgrade runbook), FR-174 (archival time), FR-175 (sampling scope), FR-176 (service map) | Kill switch activation criteria formalization, partial deployment state detection |

---
## 17 Tasks (All TODO)

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

Work order staleness: Fix files contain only Round 1-6 FRs. 100+ FRs from Rounds 7-21 mapped in HL doc but missing from implementation guides. FR-164 mandates synchronization before implementation.

---
## Key Canonical Sources Confirmed (Round 21)

- OTel Python SDK v1.39.1 `_shared_internal/__init__.py` — BatchProcessor rewrite, deque-based, silent drops
- opentelemetry-python#3886 — BSP deadlock FIXED in v1.33.0
- opentelemetry-python#4261 — Logging in emit() causes infinite recursion
- opentelemetry-python#4568 — force_flush() timeout NOT enforced at BSP level
- AWS Lambda Extensions API — Extensions not restarted on crash
- AWS X-Ray Service Quotas — PutTraceSegments ~2,500 TPS (adjustable, L-AB6D2D9B), Groups 25/region (adjustable, L-F895D63C), Rules 25/region (adjustable, L-B5F5E1ED)
- AWS X-Ray Developer Guide — Encryption at rest (default AWS-managed key)
- X-Ray API Reference — GetTraceSummaries 6-hour window, 30 TPS, 100/page
- OTel SDK sampling.py — ParentBased delegation logic (centralized rules at root only)
- CloudWatch RUM — Confirmed X-Ray header injection with enableXRay: true
- OTLP HTTP exporter — 6 retries, exp backoff, blocks BSP worker, 429 NOT retried
- AwsLambdaResourceDetector — Reads os.environ on detect() but Resource cached at cold start
- OTel BoundedAttributes — Silent truncation, no log on drop, popitem(last=False)

---
## Potential Round 22 Focus Areas

1. **Sampling graduation plan** — No strategy for reducing from 100% sampling as traffic grows beyond current scale; X-Ray ~2,500 TPS limit
2. **Kill switch activation criteria** — FR-059 provides OTEL_SDK_DISABLED but no documented criteria for WHEN to activate it
3. **Partial deployment state detection** — FR-107 defines 6 phases but no mechanism detects incomplete phase deployment
4. **High-cardinality annotation query performance** — X-Ray GetTraceSummaries pagination under high cardinality annotations (session_id, trace_id) untested
5. **Multi-account X-Ray strategy** — Cross-account tracing supported via OAM but not addressed in spec
6. **Automated PII scanning in traces** — FR-155 prohibits PII but relies on code review; no automated runtime scanning
7. **ADOT resource overhead cost quantification** — Memory/CPU cost of ADOT Extension at scale not formally budgeted
8. **Warm invocation with ADOT cold start interaction** — When ADOT Extension restarts (new sandbox), first warm invocation may have different latency profile
9. **Canary test trace interference** — Canary traces appear in production X-Ray data; no mechanism to filter them from operational dashboards
10. **FR-157 GitHub issue verification** — SC-107 requires issue "HL Document Staleness: Missing Round 18" — unclear if created
