# OTel SDK Initialization Contract

**Applies to**: SSE Streaming Lambda only
**FR References**: FR-052 through FR-077, FR-092, FR-093, FR-101, FR-108

## TracerProvider Initialization (Module-Level Singleton)

```python
# MUST be module-level — per-invocation creation leaks daemon threads (FR-065)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagators.aws import AwsXRayPropagator
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.sdk.extension.aws.resource import AwsLambdaResourceDetector

resource = Resource.create({
    "service.name": os.environ["OTEL_SERVICE_NAME"],  # FR-071, Amendment 1.15
}).merge(AwsLambdaResourceDetector().detect())  # FR-072

provider = TracerProvider(
    resource=resource,
    id_generator=AwsXRayIdGenerator(),  # FR-053
    sampler=ParentBasedTraceIdRatio(1.0),  # FR-056: parentbased_always_on
    shutdown_on_exit=False,  # FR-077: prevent atexit race
)

exporter = OTLPSpanExporter(
    endpoint="http://localhost:4318/v1/traces",  # FR-054
    timeout=2,  # FR-114: OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2s
)

bsp = BatchSpanProcessor(
    exporter,
    schedule_delay_millis=1000,   # FR-073: Lambda-tuned (default 5000 too slow)
    max_queue_size=1500,          # FR-086: Covers 225 spans + margin
    max_export_batch_size=64,     # FR-073: Lambda-tuned (default 512 too large)
)

provider.add_span_processor(bsp)
trace.set_tracer_provider(provider)
```

## Per-Invocation Context Extraction (FR-059)

```python
# MUST run per-invocation, NOT module-level
# Reads _X_AMZN_TRACE_ID env var (updated by custom bootstrap on warm invocations)
from opentelemetry.propagators.aws.aws_xray_propagator import AwsXRayPropagator

def extract_trace_context():
    """Extract trace context from Lambda runtime environment.

    CRITICAL: Must be called per-invocation. Module-level extraction
    uses stale trace ID on warm invocations (FR-059, FR-092).
    """
    trace_id = os.environ.get("_X_AMZN_TRACE_ID", "")
    propagator = AwsXRayPropagator()
    ctx = propagator.extract(carrier={"X-Amzn-Trace-Id": trace_id})
    return ctx
```

## Required Environment Variables

| Variable | Value | FR | Fail-Fast |
|----------|-------|-----|-----------|
| `OTEL_SERVICE_NAME` | `sentiment-analyzer-sse` | FR-071 | `os.environ["OTEL_SERVICE_NAME"]` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | FR-054 | `os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]` |
| `OTEL_SDK_DISABLED` | `false` | FR-108 | Kill switch (operable without rebuild) |
| `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT` | `2` | FR-114 | Prevents indefinite block |
| `OPENTELEMETRY_COLLECTOR_CONFIG_FILE` | `/opt/collector-config/config.yaml` | FR-095 | ADOT Extension config path |

## Prohibited Patterns

| Pattern | FR | Reason |
|---------|-----|--------|
| `BotocoreInstrumentor().instrument()` | FR-076 | Conflicts with Powertools auto-patch |
| `AsyncContext` | FR-037 | Loses context across event loop boundaries |
| `OTEL_PROPAGATORS` env var | FR-068 | Must use explicit propagator configuration |
| Per-invocation `TracerProvider()` | FR-065 | Leaks daemon threads → OOM |
| `@tracer.capture_method` on async generators | FR-031 | Falls through to sync wrapper silently |

## force_flush() Contract (FR-093, FR-139)

```python
import threading

def safe_force_flush(provider: TracerProvider, timeout_ms: int = 2500) -> bool:
    """Force flush with hard timeout enforcement.

    FR-139: OTel SDK timeout parameter is NOT enforced.
    Thread wrapper provides hard kill on hung Extension.

    Returns True if flush completed, False if timeout.
    """
    success = False

    def _flush():
        nonlocal success
        provider.force_flush(timeout_millis=timeout_ms)
        success = True

    thread = threading.Thread(target=_flush, daemon=True)
    thread.start()
    thread.join(timeout=timeout_ms / 1000)

    if not success:
        # Diagnostic differentiation (FR-156/FR-165):
        # ECONNREFUSED = port-unreachable (fast fail, Extension crashed)
        # TCP accept + timeout = hung Extension (SC-064a vs SC-064b)
        logger.warning("force_flush timeout", extra={
            "flush_timeout_ms": timeout_ms,
            "diagnostic": "extension_hang",  # FR-165 amended label
        })

    return success
```
