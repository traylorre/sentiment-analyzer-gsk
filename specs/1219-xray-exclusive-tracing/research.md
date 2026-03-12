# Research: X-Ray Exclusive Tracing

**Feature**: 1219-xray-exclusive-tracing | **Date**: 2026-03-10
**Input**: Unknowns and technology choices from [plan.md](./plan.md) Technical Context

## Research Summary

This feature underwent 26 rounds of specification refinement which resolved most unknowns inline. This document consolidates the key technology decisions and their rationale.

---

## 1. ADOT Extension vs Lambda Layer for OTel

**Decision**: ADOT Extension embedded in Docker container (multi-stage build)

**Rationale**:
- SSE Lambda uses container-based deployment (ECR), not ZIP
- Lambda Layers are incompatible with container-based Lambdas (AWS docs confirmed)
- ADOT Extension runs as sidecar process with independent lifecycle
- Collector-only type (~35MB binary) — no auto-instrumentation (FR-046)

**Alternatives Considered**:
- Lambda Layer ADOT: Rejected — incompatible with container deployment
- Direct X-Ray SDK: Rejected — X-Ray segment closes before streaming begins in RESPONSE_STREAM mode
- Sidecar container: Not available in Lambda (only in ECS/Fargate)

**Canonical Source**: [AWS Lambda Extensions with Container Images](https://docs.aws.amazon.com/lambda/latest/dg/extensions-configuration.html)

---

## 2. OTel SDK Version Selection

**Decision**: `opentelemetry-api==1.39.1`, `opentelemetry-sdk==1.39.1`

**Rationale**:
- Fixes BSP deadlock (opentelemetry-python#3886, fixed v1.33.0+)
- Python 3.13 compatibility verified
- All core packages pinned to identical version for reproducible builds (FR-101)
- Contrib packages (`opentelemetry-instrumentation-aws-lambda==0.45b0`) floor-pinned

**Alternatives Considered**:
- Latest bleeding edge: Rejected — stability required for production Lambda
- v1.33.0 (minimum fix version): Rejected — missing later performance improvements
- v1.28.x (pre-fix): Rejected — BSP deadlock present

**Canonical Source**: [opentelemetry-python changelog](https://github.com/open-telemetry/opentelemetry-python/blob/main/CHANGELOG.md)

---

## 3. Powertools Tracer vs Raw xray_recorder

**Decision**: Powertools Tracer for all 5 standard Lambdas; OTel SDK for SSE Lambda streaming phase

**Rationale**:
- Powertools `@tracer.capture_method` auto-captures exceptions (raw `@xray_recorder.capture` does not)
- Powertools provides consistent patterns: `capture_lambda_handler`, `capture_method`
- SSE Lambda streaming phase requires OTel SDK because X-Ray segment already closed
- `auto_patch=False` on SSE Lambda prevents dual-emission during streaming (FR-060)

**Alternatives Considered**:
- Raw xray_recorder everywhere: Rejected — no auto exception capture, verbose
- OTel SDK everywhere: Rejected — overkill for standard Lambdas, Powertools is AWS-idiomatic
- Mixed raw + Powertools: Rejected — inconsistency, harder to maintain

**Canonical Source**: [AWS Lambda Powertools Tracer](https://docs.powertools.aws.dev/lambda/python/latest/core/tracer/)

---

## 4. SSE Streaming Phase Architecture

**Decision**: OTel SDK → OTLP HTTP → ADOT Extension → X-Ray backend (Two-hop architecture)

**Rationale**:
- Lambda RESPONSE_STREAM returns generator from handler; X-Ray FacadeSegment closes before generator executes
- `begin_segment()` is documented no-op in Lambda (Round 3 discovery)
- ADOT Extension survives handler return, receives Shutdown event, flushes remaining spans
- OTLP HTTP to localhost:4318 (sub-millisecond hop 1); Extension → X-Ray (hundreds of ms hop 2)
- Decouple processor in ADOT config prevents span loss race (FR-075/FR-090)

**Alternatives Considered**:
- Two-Phase X-Ray Architecture (Round 2): INVALID — begin_segment() no-op in Lambda
- Direct X-Ray API calls: Rejected — loses OTel semantic conventions, no BatchSpanProcessor
- Lambda Layer auto-instrumentation: Rejected — container-based, also wraps handler (not streaming)

**Canonical Source**: [AWS ADOT Lambda Extension](https://aws-otel.github.io/docs/getting-started/lambda)

---

## 5. Frontend SSE Client Architecture

**Decision**: `fetch()` + `ReadableStream` replacing `EventSource`

**Rationale**:
- EventSource API (WHATWG spec) does not support custom HTTP headers
- X-Amzn-Trace-Id header propagation requires custom header injection
- CloudWatch RUM FetchPlugin auto-patches `fetch()` to inject trace headers
- Manual reconnection with exponential backoff replaces EventSource auto-reconnect
- TextDecoder with `{stream: true}` for UTF-8 chunk boundary safety (FR-099)

**Alternatives Considered**:
- EventSource with query parameter: Rejected — trace IDs change per request, URL caching issues
- Service worker interceptor: Rejected — adds complexity, doesn't solve header limitation
- Server-generated trace ID only: Rejected — loses browser→backend correlation

**Canonical Source**: [WHATWG Fetch Standard](https://fetch.spec.whatwg.org/), [WHATWG EventSource](https://html.spec.whatwg.org/multipage/server-sent-events.html)

---

## 6. BatchSpanProcessor Tuning for Lambda

**Decision**: `schedule_delay_millis=1000`, `max_queue_size=1500`, `max_export_batch_size=512`

**Rationale**:
- Lambda SSE streaming generates ~225 spans (15 polls/sec × 15s)
- Default 5000ms schedule delay too slow for Lambda lifecycle
- Default 2048 queue size slightly large; 1500 covers peak + margin
- Export timeout 2000ms (OTEL_EXPORTER_OTLP_TRACES_TIMEOUT) prevents indefinite block
- `shutdown_on_exit=False` prevents atexit race with Lambda runtime (FR-077)

**Alternatives Considered**:
- SimpleSpanProcessor: Rejected — synchronous export blocks streaming, high latency
- Default BSP settings: Rejected — 5s delay loses spans on short invocations
- Aggressive 100ms schedule: Rejected — excessive OTLP calls to Extension

**Canonical Source**: [OTel Python SDK BatchSpanProcessor](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html)

---

## 7. force_flush() Timeout Enforcement

**Decision**: 2500ms threading.Thread wrapper around force_flush() (FR-139)

**Rationale**:
- OTel SDK force_flush() timeout parameter is NOT enforced (documented SDK limitation)
- If ADOT Extension hangs, force_flush() blocks indefinitely
- Thread wrapper with join(timeout=2.5) provides hard kill
- Combined with OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2000 for defense-in-depth
- Diagnostic differentiation: ECONNREFUSED (fast fail) vs TCP accept (hung Extension)

**Alternatives Considered**:
- Trust SDK timeout: Rejected — not enforced in practice
- asyncio.wait_for: Rejected — SSE Lambda uses sync context for OTel
- signal.alarm: Rejected — not reliable in Lambda environment

**Canonical Source**: [opentelemetry-python#3886](https://github.com/open-telemetry/opentelemetry-python/issues/3886)

---

## 8. X-Ray Sampling Strategy

**Decision**: 100% sampling in dev/preprod; centralized rules in production

**Rationale**:
- Dev/preprod: Full visibility for debugging, low traffic volume
- Production: Centralized X-Ray sampling rules (not client-driven) per FR-035
- Clients CAN force `Sampled=1` via header — server-side override required for cost control
- API Gateway respects centralized rules; Function URL has no parent sampling context
- FR-161: Daily cost anomaly alarm as safety net

**Alternatives Considered**:
- 100% everywhere: Rejected — production cost amplification risk
- Client-driven sampling: Rejected — cost amplification attack vector (FR-035)
- Per-Lambda sampling rules: Rejected — fragmented management, inconsistent coverage

**Canonical Source**: [X-Ray Sampling Rules](https://docs.aws.amazon.com/xray/latest/devguide/xray-console-sampling.html)

---

## 9. Canary Architecture

**Decision**: Separate Lambda with independent IAM role, cross-region SNS out-of-band alerting

**Rationale**:
- Canary must detect application IAM revocation → needs separate role (FR-051)
- CloudWatch failure must not prevent alert → cross-region SNS (FR-136)
- Piggybacked heartbeat on production put_metric_data (FR-126) — zero extra API calls
- 5-minute EventBridge interval → ≤10-minute worst-case detection latency
- FR-145: Exempted from FR-018 fail-fast (canary must complete even when X-Ray broken)

**Alternatives Considered**:
- Same IAM role as application: Rejected — can't detect own permission revocation
- CloudWatch-only alerting: Rejected — single point of failure
- External monitoring (Datadog, etc.): Rejected — cost, complexity, additional vendor

**Canonical Source**: [X-Ray GetTraceSummaries API](https://docs.aws.amazon.com/xray/latest/api/API_GetTraceSummaries.html)

---

## 10. PII Prevention Strategy

**Decision**: CI-only annotation scanning (FR-184 amended R26); runtime SpanProcessor chain TRIMMED

**Rationale**:
- Original FR-184/FR-191/FR-192 proposed runtime SpanProcessor chain: overengineered
- Data is financial (ticker symbols, sentiment scores) — not personal data
- set_attribute() after span creation bypasses SpanProcessor.on_start() anyway
- CI static analysis gate for set_attribute() calls is sufficient and reliable
- Runtime audit SpanProcessor adds latency and complexity without proportional benefit

**Alternatives Considered**:
- Runtime SpanProcessor chain (original FR-191): Rejected R26 — overengineered, bypassed by set_attribute()
- OTel ReadableSpan filtering in on_end(): Rejected — ReadableSpan is immutable in OTel Python SDK (FR-183)
- No PII protection: Rejected — still need CI gate for annotation key validation

**Canonical Source**: [OTel SpanProcessor API](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html)

---

## 11. Warm Invocation Trace Context

**Decision**: Custom bootstrap reads `Lambda-Runtime-Trace-Id` header and updates `_X_AMZN_TRACE_ID` env var (FR-092)

**Rationale**:
- Lambda runtime sets `_X_AMZN_TRACE_ID` only on COLD start
- Warm invocations reuse the first invocation's trace ID (confirmed code inspection)
- OTel `extract_context()` reads env var → links ALL warm spans to wrong trace
- Custom bootstrap already exists for SSE Lambda RESPONSE_STREAM
- Fix: Read `Lambda-Runtime-Trace-Id` response header per invocation, update env var

**Alternatives Considered**:
- Per-invocation TracerProvider: Rejected — leaks daemon threads, OOM growth (FR-065)
- Environment variable polling: Not reliable in Lambda sandbox
- Accept stale trace IDs: Rejected — fundamentally breaks distributed tracing

**Canonical Source**: [Lambda Runtime API](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html)

---

## 12. CloudWatch Alarm treat_missing_data Classification

**Decision**: Systematic per-alarm-type classification (FR-121/FR-162)

**Rationale**:
- `breaching`: X-Ray cost alarms (missing = no charges = good)
- `notBreaching`: Error count alarms (missing = no errors = good)
- `missing`: Application metric alarms (missing = emission failure = needs investigation)
- `ignore`: Canary heartbeat (expected gaps during maintenance)
- Incorrect classification causes false alarms or missed incidents

**Canonical Source**: [CloudWatch treat_missing_data](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
