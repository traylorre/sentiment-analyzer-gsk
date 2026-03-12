# Task 5: Fix SSE Streaming Lambda Tracing (ADOT Extension)

**Priority:** P1
**Status:** TODO
**Spec FRs:** FR-001, FR-025, FR-026, FR-027, FR-031, FR-037, FR-046, FR-047, FR-052, FR-053, FR-054, FR-055, FR-056, FR-058, FR-059, FR-060
**Depends on:** Task 1 (IAM), Task 14 (tracer standardization — for handler-phase Powertools only)
**Blocks:** Tasks 6, 7, 8

> **Round 5 Update:** Deep research confirmed that OTel-to-X-Ray trace context bridging requires THREE explicit configurations: (1) `AwsXRayLambdaPropagator` to read `_X_AMZN_TRACE_ID`, (2) `AwsXRayIdGenerator` for X-Ray-compatible trace IDs, (3) OTLP exporter endpoint to `localhost:4318`. Additionally, `force_flush()` MUST be called in the generator's `finally` block to prevent span loss on execution environment freeze. Added FR-052 through FR-058.

> **Round 6 Update:** Two critical warm-invocation bugs identified: (1) OTel trace context MUST be extracted per-invocation inside the handler, not at module level — module-level `propagate.extract()` captures only the cold start trace ID, linking all warm invocations' spans to the wrong trace (FR-059), (2) Powertools Tracer MUST use `auto_patch=False` on the SSE Lambda — global botocore patching from `auto_patch=True` creates duplicate X-Ray subsegments alongside OTel spans during the streaming phase (FR-060). Memory validation confirmed 512MB is adequate for ADOT Extension + OTel SDK.

---

## Problem

The SSE Streaming Lambda has only 1 X-Ray subsegment (`stream_status`) despite being the most latency-sensitive component. DynamoDB polling, event dispatch, cache operations, and connection management are all invisible to X-Ray.

### Why This Is Hard

The SSE Lambda uses `RESPONSE_STREAM` invoke mode with Lambda Function URLs. The Lambda runtime creates an X-Ray segment on invocation and closes it when the handler function returns the response generator. But streaming continues AFTER the handler returns — the Lambda bootstrap iterates the generator, sending chunks to the client. All DynamoDB polling, event serialization, and CloudWatch metric calls happen during streaming, after the segment closes.

### Round 2 Approach (INVALIDATED)

~~Round 2 proposed a "Two-Phase Architecture" that creates independent X-Ray segments during streaming using `xray_recorder.begin_segment()` linked to the original trace ID.~~

**This approach is INVALID.** Deep investigation of the X-Ray SDK source code reveals:

1. **`begin_segment()` is a no-op in Lambda.** The SDK detects Lambda via `LAMBDA_TASK_ROOT` env var and replaces the default `Context` with `LambdaContext`. `LambdaContext.put_segment()` silently discards all segments with a log warning (source: `aws_xray_sdk/core/lambda_launcher.py:55-59`).

2. **`FacadeSegment` is immutable.** The Lambda runtime's auto-created segment is a `FacadeSegment` that raises `FacadeSegmentMutationException` on ALL mutation operations: `close()`, `put_annotation()`, `put_metadata()`, `set_aws()`, `add_exception()`, `serialize()`.

3. **X-Ray daemon may shut down after handler returns.** In RESPONSE_STREAM mode, the X-Ray daemon (a Lambda-managed process) may begin its shutdown sequence after the handler returns, making even raw UDP emission to `127.0.0.1:2000` unreliable.

### Round 3 Approach: ADOT Lambda Extension

The corrected approach uses the **AWS Distro for OpenTelemetry (ADOT) Lambda Extension**:

- ADOT runs as a Lambda Extension — a separate process with its own lifecycle (INIT, INVOKE, SHUTDOWN phases)
- The extension continues running after the handler returns, during response streaming
- The OpenTelemetry SDK creates spans freely — no `LambdaContext` restriction
- ADOT exports spans to X-Ray via the OTLP-to-X-Ray exporter
- Spans appear in the X-Ray console with the same trace ID as Lambda-generated segments

**Architecture:**

```
Handler Phase (before return):
  Lambda Runtime → FacadeSegment → subsegments (Powertools Tracer)

Streaming Phase (after handler returns):
  Generator iteration → OTel SDK → spans → OTLP (localhost:4318) → ADOT Extension → X-Ray

ADOT Extension lifecycle:
  INIT → (handler runs) → INVOKE → (streaming) → SHUTDOWN → flush remaining spans
```

---

## Changes Required

### 1. Add ADOT Lambda Extension Layer

Add the ADOT Lambda Extension as a Lambda Layer in Terraform:

- SSE Lambda function configuration in `modules/lambda/sse_streaming.tf`
- Add ADOT layer ARN to `layers` list
- Add environment variable `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`
- Add environment variable `OTEL_SERVICE_NAME=sse-streaming`
- **MUST NOT** set `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler` (FR-046 — Round 4: ADOT auto-instrumentation conflicts with Powertools Tracer; see "ADOT Coexistence Constraints" section below)

### 2. Add OpenTelemetry SDK Dependencies

Add to SSE Lambda's requirements:

- `opentelemetry-api` — core OTel API
- `opentelemetry-sdk` — core SDK (TracerProvider, BatchSpanProcessor)
- `opentelemetry-sdk-extension-aws` — AwsXRayIdGenerator
- `opentelemetry-propagator-aws-xray` — AwsXRayLambdaPropagator (reads _X_AMZN_TRACE_ID)
- `opentelemetry-exporter-otlp-proto-http` — OTLP HTTP exporter to ADOT Extension

### 3. Initialize OTel TracerProvider in Handler

At module level (runs once per cold start):

- Create `TracerProvider` with `OTLPSpanExporter` pointing to `localhost:4318`
- Configure `BatchSpanProcessor` for efficient buffering
- Configure `AwsXRayLambdaPropagator` and `AwsXRayIdGenerator`
- Store the `Tracer` instance for use during streaming

**CRITICAL (FR-059 — Round 6): Per-Invocation Context Extraction.** The `TracerProvider`, `Tracer`, and propagator configuration are module-level (cold start only). However, trace context extraction MUST happen per-invocation inside the handler function. On warm invocations, the Lambda runtime updates `_X_AMZN_TRACE_ID` to the new invocation's trace ID before calling the handler. Module-level `propagate.extract()` captures only the first invocation's context and reuses it for all subsequent warm invocations — linking every streaming-phase span to a stale trace ID. The correct pattern:

```python
# Module level — runs once on cold start
from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.propagators.aws import AwsXRayLambdaPropagator

propagate.set_global_textmap(AwsXRayLambdaPropagator())
provider = TracerProvider(id_generator=AwsXRayIdGenerator())
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
otel_tracer = trace.get_tracer(__name__)

# Handler level — runs on EVERY invocation (cold AND warm)
def handler(event, context):
    # Extract CURRENT invocation's trace context from _X_AMZN_TRACE_ID
    # AwsXRayLambdaPropagator reads os.environ on each call (no caching)
    ctx = propagate.extract(carrier={})  # reads _X_AMZN_TRACE_ID internally

    # Pass ctx to streaming generator — all OTel spans use this context
    return streaming_response(event_generator(ctx))
```

**Why this matters:** This bug is invisible in cold-start-heavy dev testing (every invocation extracts the correct context because every invocation is a cold start). It manifests in production under sustained load where warm invocations dominate — spans from invocation N+1 appear under invocation N's trace, creating cross-invocation trace contamination.

### 4. Instrument Streaming Operations with OTel Spans

Replace the invalidated `begin_segment()` calls with OTel `tracer.start_as_current_span()`:

**In `handler.py` (streaming entry point):**
- Capture trace ID from `_X_AMZN_TRACE_ID` env var before entering streaming loop
- Pass trace context to the streaming generator

**In `polling.py` (DynamoDB poll cycle):**
- Wrap each poll cycle in an OTel span named `dynamodb_poll`
- Add attributes: `item_count`, `changed_count`, `poll_duration_ms`, `sentiment_type`

**In `stream.py` (event dispatch):**
- Wrap each event dispatch in an OTel span named `sse_event_dispatch`
- Add attributes: `event_type`, `latency_ms`, `is_cold_start`

**In `connection.py` (connection lifecycle):**
- Wrap connection acquire/release in OTel spans named `connection_acquire`, `connection_release`
- Add attributes: `connection_id`, `current_count`, `max_connections`

**In CloudWatch metric emission:**
- Wrap `put_metric_data` calls in OTel spans named `cloudwatch_put_metric`

### 5. Async Generator Safety (FR-031)

**MUST NOT** apply `@tracer.capture_method` to any async generator function in the SSE Lambda. Instead, use manual OTel span context managers:

```python
# WRONG — silently captures near-zero time
@tracer.capture_method
async def event_generator():
    async for event in source:
        yield event

# CORRECT — captures full iteration time
async def event_generator():
    with otel_tracer.start_as_current_span("sse_stream") as span:
        count = 0
        async for event in source:
            count += 1
            yield event
        span.set_attribute("events_yielded", count)
```

### 6. AsyncContext Prohibition (FR-037)

**MUST NOT** configure `xray_recorder.configure(context=AsyncContext())` on the SSE Lambda. The default `threading.local()` context:
- DOES propagate through `asyncio.new_event_loop().run_until_complete()` (same thread)
- Is required for Powertools Tracer in the handler phase

`AsyncContext` uses `TaskLocalStorage` which loses context across event loop boundaries (known bugs: aws-xray-sdk-python #164, #310, #446).

### 7. Trace Context Propagation (FR-025 revised)

The trace ID from the Lambda invocation must be propagated to OTel spans created during streaming:

- Extract `_X_AMZN_TRACE_ID` from environment or Lambda context
- Parse into OTel `TraceId` and `SpanId`
- Create OTel `SpanContext` with the extracted trace ID
- Use as parent context for all streaming spans

This ensures all streaming OTel spans appear under the same trace ID in the X-Ray console.

**Round 6 clarification (FR-059):** This extraction MUST occur at handler entry on EVERY invocation, not at module level. See Section 3 for the detailed pattern and rationale.

### 8. auto_patch=False for SSE Lambda (FR-060 — Round 6)

The SSE Lambda MUST initialize Powertools Tracer with `auto_patch=False`:

```python
from aws_lambda_powertools import Tracer

# CORRECT — no global botocore patching
tracer = Tracer(auto_patch=False)

# WRONG — patches botocore globally at import time
# tracer = Tracer()  # auto_patch=True is the default
```

**Why this is required:** Powertools' `auto_patch=True` (the default) patches `botocore.client.BaseClient._make_api_call` at module import time. These patches are GLOBAL — they intercept ALL boto3 calls regardless of execution phase. During SSE streaming (after the handler returns), each DynamoDB query or CloudWatch `put_metric_data` call creates:

1. **An X-Ray subsegment** via the auto-patch — sent to the X-Ray daemon, whose lifecycle during `RESPONSE_STREAM` after handler return is undocumented and may be unreliable
2. **An OTel span** via manual instrumentation — sent to the ADOT Extension, which is reliable during streaming

This dual-emission produces duplicate or inconsistent entries in X-Ray. If the X-Ray daemon continues accepting data, operators see two entries per AWS SDK call. If the daemon stops, only OTel spans appear. The behavior is unpredictable and varies between invocations.

**Handler-phase tracing alternative:** With `auto_patch=False`, handler-phase AWS SDK calls are traced via explicit `@tracer.capture_method` decorators on the specific functions that make boto3 calls during the handler phase. This provides equivalent tracing coverage for the handler phase while eliminating the dual-emission problem during streaming:

```python
@tracer.capture_lambda_handler
def handler(event, context):
    # Handler-phase calls are explicitly traced
    result = process_request(event)
    ctx = propagate.extract(carrier={})
    return streaming_response(event_generator(ctx))

@tracer.capture_method
def process_request(event):
    # This DynamoDB call gets ONE subsegment (from @tracer.capture_method)
    return dynamodb.get_item(...)

async def event_generator(ctx):
    # This DynamoDB call gets ONE span (from OTel, via ADOT)
    # No auto-patch subsegment because auto_patch=False
    with otel_tracer.start_as_current_span("dynamodb_poll", context=ctx):
        items = await poll_dynamodb()
        yield format_event(items)
```

**Interaction with FR-046:** This constraint is complementary to — not redundant with — FR-046 (no ADOT auto-instrumentation). FR-046 prevents ADOT from patching botocore. FR-060 prevents Powertools from patching botocore globally. Both are required to ensure that streaming-phase AWS SDK calls produce exactly one trace entry (the OTel span).

### 9. Memory Validation (Round 6)

The SSE Lambda's current memory allocation of **512MB** is adequate for the ADOT Extension and OTel SDK additions:

| Component | Memory Overhead |
|-----------|----------------|
| ADOT Lambda Extension (sidecar mode) | ~40-60MB |
| OTel SDK packages (FR-057) | ~5-10MB |
| **Total additional** | **~45-70MB** |

With the Lambda's existing application footprint, the total remains well within the 512MB allocation. No memory increase is required. Source: Terraform `infrastructure/terraform/main.tf` — `memory_size = 512`.

---

## Files to Modify

| File | Change |
|------|--------|
| `modules/lambda/sse_streaming.tf` | Add ADOT Extension layer, OTel env vars |
| `src/lambdas/sse_streaming/requirements.txt` | Add opentelemetry-api, opentelemetry-sdk, opentelemetry-sdk-extension-aws, opentelemetry-propagator-aws-xray, opentelemetry-exporter-otlp-proto-http |
| `src/lambdas/sse_streaming/handler.py` | Initialize OTel TracerProvider (module level); extract trace context per-invocation (handler level, FR-059); initialize Tracer with `auto_patch=False` (FR-060); wrap streaming entry in OTel span |
| `src/lambdas/sse_streaming/polling.py` | Wrap poll cycles in OTel spans with attributes |
| `src/lambdas/sse_streaming/stream.py` | Wrap event dispatch in OTel spans with attributes |
| `src/lambdas/sse_streaming/connection.py` | Wrap connection lifecycle in OTel spans with attributes |
| `src/lambdas/sse_streaming/metrics.py` | Wrap CloudWatch put_metric_data in OTel spans |

---

## Verification

1. **Local test:** Deploy SSE Lambda with ADOT Extension to dev environment. Connect to SSE endpoint. Verify X-Ray console shows spans for polling, event dispatch, connection lifecycle — all linked to the same trace ID as the Lambda invocation segment.

2. **Streaming phase test:** Verify that spans created AFTER the handler returns (during generator iteration) appear in X-Ray. This proves the ADOT Extension's independent lifecycle is working.

3. **No orphaned subsegments:** Verify zero `SegmentNotFoundException` errors in Lambda logs. Verify zero subsegments discarded by `LambdaContext.put_segment()`.

4. **Async generator test:** Verify that NO async generator function has `@tracer.capture_method` applied. Verify that manual OTel span context managers capture the full iteration duration, not just creation.

5. **Trace linkage:** Verify that OTel spans (streaming phase) and X-Ray subsegments (handler phase) share the same trace ID in the X-Ray console.

6. **Cold start impact:** Measure cold start with ADOT Extension vs without. Expected: 50-200ms additional, running concurrent with Lambda INIT.

7. **(Round 6) Warm invocation trace isolation:** Trigger 3+ sequential invocations on the same warm execution environment. Verify each invocation's streaming-phase OTel spans carry a DISTINCT trace ID matching that invocation's `_X_AMZN_TRACE_ID` — not the first invocation's trace ID. This validates FR-059 (per-invocation context extraction).

8. **(Round 6) No dual-emission during streaming:** With `auto_patch=False` (FR-060), trigger a streaming invocation that makes DynamoDB calls during the streaming phase. Verify each DynamoDB call produces exactly ONE trace entry (the OTel span via ADOT), not two (OTel span + X-Ray subsegment from auto-patching). Compare against handler-phase DynamoDB calls, which should produce exactly ONE subsegment (from explicit `@tracer.capture_method`).

9. **(Round 6) Memory headroom:** After deploying with ADOT Extension and OTel SDK packages, verify the SSE Lambda's max memory used (from CloudWatch `MaxMemoryUsed` metric) remains below 450MB (leaving ~12% headroom within the 512MB allocation).

---

## Edge Cases

- **ADOT Extension not available:** If the ADOT layer ARN is incorrect or unavailable, the Lambda will fail to start. This is correct fail-fast behavior (FR-018).
- **OTel span export failure:** If the ADOT Extension's OTLP receiver is temporarily unavailable, the `BatchSpanProcessor` will buffer spans and retry. If the extension crashes, spans are lost — the canary (Task 11) will detect this.
- **Trace ID format conversion:** X-Ray trace IDs (`1-{hex_timestamp}-{24_hex}`) must be converted to OTel 128-bit trace IDs. The ADOT X-Ray exporter handles this conversion.
- **Dual instrumentation:** The handler phase uses Powertools Tracer (X-Ray subsegments) while the streaming phase uses OTel spans (via ADOT). Both appear in X-Ray under the same trace ID. The handler-phase subsegments are emitted via the X-Ray daemon; the streaming-phase spans are emitted via ADOT. This is intentional — Powertools works correctly for the handler phase where the facade segment is open.

---

## ADOT Coexistence Constraints (FR-046, FR-047 — Round 4)

The SSE Lambda uniquely runs both Powertools Tracer (handler phase) and ADOT Extension (streaming phase). Research confirmed these coexist safely **only** with the following constraints:

### FR-046: No ADOT Auto-Instrumentation

**MUST NOT** enable `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler` on the SSE Lambda. ADOT auto-instrumentation:

1. **Double-patches botocore** — Powertools Tracer's `auto_patch=True` already patches boto3/botocore. ADOT's auto-instrumentation wraps the same calls again, producing duplicate spans for every AWS SDK call.
2. **Intercepts handler wrapping** — ADOT's wrapper replaces the Lambda handler entry point, interfering with Powertools' `@tracer.capture_lambda_handler` decorator.
3. **Creates context conflicts** — ADOT auto-instrumentation installs its own OTel context propagator at module level, which conflicts with the manual `TracerProvider` initialization in Section 3.

The ADOT Extension MUST run in **sidecar-only mode**: it receives spans via OTLP on `localhost:4318` and exports to X-Ray, but does NOT instrument the Lambda code.

### FR-047: Matching Service Names

The OTel `service.name` resource attribute MUST match the `POWERTOOLS_SERVICE_NAME` environment variable. Both phases must identify as the same service in the X-Ray service map:

```
POWERTOOLS_SERVICE_NAME=sse-streaming
OTEL_SERVICE_NAME=sse-streaming
```

If these diverge, the X-Ray service map shows the SSE Lambda as two disconnected nodes: one for handler-phase subsegments (Powertools) and one for streaming-phase spans (ADOT). This breaks the unified trace view.

### Verification

1. **No `AWS_LAMBDA_EXEC_WRAPPER` env var** present on SSE Lambda configuration in Terraform
2. **Service map coherence**: After deployment, verify X-Ray service map shows a single node for the SSE Lambda, with both handler-phase and streaming-phase traces connected
3. **No duplicate spans**: Verify that a single DynamoDB call during the handler phase produces exactly one subsegment (from Powertools), not two (from Powertools + ADOT auto-instrumentation)

---

## OTel-to-X-Ray Trace Context Bridging (Round 5)

The SSE Lambda uniquely runs two tracing SDKs:
- **Handler phase**: Powertools Tracer (X-Ray SDK) — creates subsegments under the Lambda runtime's facade segment
- **Streaming phase**: OTel SDK — creates spans exported via ADOT Extension to X-Ray

For these to appear as a UNIFIED trace, the OTel SDK MUST be explicitly configured to bridge to the Lambda runtime's X-Ray trace context. Without this bridging, streaming-phase spans create disconnected traces.

### Required Configuration (FR-052, FR-053, FR-054, FR-056)

| Component | Package | Purpose |
|-----------|---------|---------|
| `AwsXRayLambdaPropagator` | `opentelemetry-propagator-aws-xray` | Reads `_X_AMZN_TRACE_ID` env var → extracts trace_id, parent_span_id, sampled flag into OTel context |
| `AwsXRayIdGenerator` | `opentelemetry-sdk-extension-aws` | Generates X-Ray-compatible trace IDs (unix epoch in first 4 bytes) for any new root spans |
| `OTLPSpanExporter` | `opentelemetry-exporter-otlp-proto-http` | Exports spans to ADOT Extension at `http://localhost:4318/v1/traces` |
| `parentbased_always_on` sampler | `opentelemetry-sdk` (built-in, default) | Honors Lambda runtime's `Sampled=0/1` decision — suppresses spans for unsampled invocations |

### force_flush() Requirement (FR-055)

The `BatchSpanProcessor` buffers spans with a 200ms batch timeout. At the end of the streaming generator, any spans created in the final <200ms have not yet been exported. When the execution environment freezes, these spans are suspended in memory. On the NEXT invocation, they're exported with stale trace IDs.

The generator MUST call `force_flush()` in its `finally` block:
- Target: ADOT Extension on localhost (sub-millisecond latency)
- Timeout: 5 seconds (generous for localhost)
- This handles ONLY the final partial batch — intermediate spans are exported incrementally during the 15-second streaming lifecycle

### Segment Document Size Guard (FR-058)

X-Ray's `PutTraceSegments` API rejects documents exceeding 64KB. The X-Ray SDK and OTel SDK both emit subsegments/spans as independent documents, but individual documents with large metadata can still exceed the limit.

Bounds:
- Error messages: truncate to 2,048 characters
- Stack traces: truncate to first 10 frames
- HTTP response bodies: NEVER attach as metadata
- Annotation values: already bounded at 2,048 characters per X-Ray spec

---

## Blind Spots

7. **Stale spans from unflushed BatchSpanProcessor**: Without `force_flush()` at end of generator, spans from invocation N appear during invocation N+1's processing. This is because the execution environment freezes (not terminates) and the BatchSpanProcessor resumes with its previous buffer on thaw.
8. **ADOT Extension SHUTDOWN timeout**: Default 2 seconds. SHUTDOWN is only sent on environment destruction (NOT after each invocation). Configurable up to 10s via `AWS_LAMBDA_EXTENSION_SHUTDOWN_TIMEOUT_MS`. Low risk because `force_flush()` handles per-invocation flush.
9. **OTel RandomIdGenerator breaks X-Ray time indexing**: If `AwsXRayIdGenerator` is not configured, any new root spans have random bytes in the X-Ray epoch field. X-Ray uses this field for time-window queries — traces may not appear in the expected time range.
10. **always_on sampler creates orphan traces**: If the OTel sampler is changed from `parentbased_always_on` to `always_on`, unsampled invocations (Sampled=0) still produce OTel spans. These create root-level traces in X-Ray with no parent facade segment.
11. **(Round 6) Module-level trace context extraction links all warm invocations to wrong trace**: If `propagate.extract()` is called at module level instead of per-invocation in the handler, the extracted context captures the cold start trace ID. Every subsequent warm invocation's streaming-phase spans link to this stale trace ID. This is invisible in dev testing (cold-start-heavy) and only manifests in production under sustained load. The `AwsXRayLambdaPropagator.extract()` method reads `os.environ` on each call with no caching, so the fix is simply to call it at handler entry.
12. **(Round 6) auto_patch=True creates unpredictable dual-emission during streaming**: With Powertools' default `auto_patch=True`, every boto3 call during the streaming phase creates both an X-Ray subsegment (via global botocore patching, sent to X-Ray daemon) and an OTel span (via manual instrumentation, sent to ADOT). Whether the X-Ray daemon accepts subsegments during RESPONSE_STREAM after handler return is undocumented. The behavior may vary by Lambda runtime version, producing inconsistent trace data.
