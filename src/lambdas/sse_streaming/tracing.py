"""OTel SDK tracing module for SSE Streaming Lambda.

Module-level TracerProvider singleton per FR-052 through FR-077.
Per-invocation TracerProvider creation is PROHIBITED (FR-065: daemon thread OOM).

Dual tracing framework:
- Powertools Tracer: Handler phase (request/response, annotations)
- OTel SDK: Streaming phase (DynamoDB polls, SSE events, CloudWatch puts)

Architecture:
    handler.py → extract_trace_context() per invocation
             → OTel spans during streaming
             → safe_force_flush() on exit
             → ADOT Extension (port 4318) → X-Ray
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

# Module-level state
_tracer = None
_provider = None
_otel_disabled = False


def _init_tracer_provider():
    """Initialize OTel TracerProvider as module-level singleton.

    MUST be called once at module load. Per-invocation creation
    leaks daemon threads and causes OOM (FR-065).

    FR-037: Kill switch via OTEL_SDK_DISABLED env var.
    FR-038: Structured error attribution on init failure.
    """
    global _provider, _tracer, _otel_disabled

    # T037: Kill switch — operable without rebuild (FR-108)
    if os.environ.get("OTEL_SDK_DISABLED") == "true":
        _otel_disabled = True
        logger.info("OTel SDK disabled via OTEL_SDK_DISABLED=true")
        return

    # T038: Structured error attribution around TracerProvider init (FR-106)
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.extension.aws.resource import (
            AwsLambdaResourceDetector,
        )
        from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # FR-071, Amendment 1.15: fail-fast on missing service name
        service_name = os.environ["OTEL_SERVICE_NAME"]

        resource = Resource.create({"service.name": service_name}).merge(
            AwsLambdaResourceDetector().detect()  # FR-072
        )

        _provider = TracerProvider(
            resource=resource,
            id_generator=AwsXRayIdGenerator(),  # FR-053
            # FR-056: parentbased_always_on (OTel SDK default)
            shutdown_on_exit=False,  # FR-077: prevent atexit race
        )

        exporter = OTLPSpanExporter(
            endpoint="http://localhost:4318/v1/traces",  # FR-054
            timeout=2,  # FR-114
        )

        bsp = BatchSpanProcessor(
            exporter,
            schedule_delay_millis=1000,  # FR-073: Lambda-tuned
            max_queue_size=1500,  # FR-086: 225 spans + margin
            max_export_batch_size=64,  # FR-073: Lambda-tuned
        )

        _provider.add_span_processor(bsp)
        trace.set_tracer_provider(_provider)
        _tracer = trace.get_tracer(__name__)

        logger.info(
            "OTel TracerProvider initialized",
            extra={"service_name": service_name},
        )

    except KeyError as e:
        logger.error(
            "OTel init failed: missing required env var",
            extra={"missing_var": str(e)},
        )
        _otel_disabled = True

    except Exception as e:
        logger.error(
            "OTel init failed: TracerProvider creation error",
            extra={"error_type": type(e).__name__, "error": str(e)},
        )
        _otel_disabled = True


def extract_trace_context():
    """Extract trace context from Lambda runtime environment.

    CRITICAL: Must be called per-invocation. Module-level extraction
    uses stale trace ID on warm invocations (FR-059, FR-092).

    Returns:
        OpenTelemetry Context with current trace ID, or None if disabled.
    """
    if _otel_disabled:
        return None

    try:
        from opentelemetry.propagators.aws import AwsXRayPropagator

        trace_id = os.environ.get("_X_AMZN_TRACE_ID", "")
        propagator = AwsXRayPropagator()
        ctx = propagator.extract(carrier={"X-Amzn-Trace-Id": trace_id})
        return ctx
    except Exception as e:
        logger.warning(
            "Failed to extract trace context",
            extra={"error": str(e)},
        )
        return None


def get_tracer():
    """Get the OTel tracer instance.

    Returns:
        OTel Tracer, or None if disabled/not initialized.
    """
    return _tracer


def get_provider():
    """Get the TracerProvider instance.

    Returns:
        TracerProvider, or None if disabled/not initialized.
    """
    return _provider


def is_enabled() -> bool:
    """Check if OTel tracing is enabled and initialized."""
    return not _otel_disabled and _provider is not None


def safe_force_flush(timeout_ms: int = 2500) -> bool:
    """Force flush with hard timeout enforcement.

    FR-139: OTel SDK timeout parameter is NOT enforced.
    Thread wrapper provides hard kill on hung Extension.

    Args:
        timeout_ms: Maximum time to wait for flush in milliseconds.

    Returns:
        True if flush completed within timeout, False otherwise.
    """
    if _provider is None or _otel_disabled:
        return True  # Nothing to flush

    success = False

    def _flush():
        nonlocal success
        _provider.force_flush(timeout_millis=timeout_ms)
        success = True

    thread = threading.Thread(target=_flush, daemon=True)
    thread.start()
    thread.join(timeout=timeout_ms / 1000)

    if not success:
        # FR-165: Diagnostic differentiation
        # ECONNREFUSED = Extension crashed (fast fail)
        # TCP accept + timeout = Extension hung
        logger.warning(
            "force_flush timeout",
            extra={
                "flush_timeout_ms": timeout_ms,
                "diagnostic": "extension_hang",
            },
        )

    return success


# Module-level init — singleton TracerProvider (FR-065)
_init_tracer_provider()
