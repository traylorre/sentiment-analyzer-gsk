# Task 5: Fix SSE Streaming Lambda Tracing (ADOT Extension)

**Priority:** P1
**Status:** TODO
**Spec FRs:** FR-001, FR-025, FR-026, FR-027, FR-031, FR-037, FR-046, FR-047
**Depends on:** Task 1 (IAM), Task 14 (tracer standardization — for handler-phase Powertools only)
**Blocks:** Tasks 6, 7, 8

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
- `opentelemetry-sdk` — TracerProvider, span processors
- `opentelemetry-exporter-otlp-proto-http` — OTLP HTTP exporter to ADOT Extension

### 3. Initialize OTel TracerProvider in Handler

At module level (runs once per cold start):

- Create `TracerProvider` with `OTLPSpanExporter` pointing to `localhost:4318`
- Configure `BatchSpanProcessor` for efficient buffering
- Set the trace ID from the Lambda's `_X_AMZN_TRACE_ID` environment variable so OTel spans link to the same trace
- Store the `Tracer` instance for use during streaming

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

---

## Files to Modify

| File | Change |
|------|--------|
| `modules/lambda/sse_streaming.tf` | Add ADOT Extension layer, OTel env vars |
| `src/lambdas/sse_streaming/requirements.txt` | Add opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http |
| `src/lambdas/sse_streaming/handler.py` | Initialize OTel TracerProvider; capture trace ID; wrap streaming entry in OTel span |
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
