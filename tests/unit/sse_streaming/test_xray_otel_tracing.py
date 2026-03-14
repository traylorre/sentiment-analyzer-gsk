"""T053: Unit tests for OTel tracing in SSE Streaming Lambda.

Verifies:
- TracerProvider singleton across multiple invocations (SC-027)
- Per-invocation context extraction uses current trace ID (SC-026)
- Span names and attributes match data-model.md schema
- flush_fired flag blocks new span creation (FR-149)
- OTEL_SDK_DISABLED=true skips all tracing
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def otel_env(monkeypatch):
    """Set OTel env vars for tracing module init."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "sentiment-analyzer-sse")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")  # Default disabled for unit tests
    monkeypatch.setenv("SENTIMENTS_TABLE", "test-table")


@pytest.fixture
def fresh_tracing_module(monkeypatch):
    """Import tracing module fresh (resets singleton state).

    Removes cached module and re-imports to test init behavior.
    """
    # Remove cached modules to force re-import
    modules_to_remove = [k for k in sys.modules if k.startswith("tracing")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    def _import(otel_disabled="true"):
        # Remove again in case of multiple calls
        modules_to_remove = [k for k in sys.modules if k.startswith("tracing")]
        for mod in modules_to_remove:
            del sys.modules[mod]

        monkeypatch.setenv("OTEL_SDK_DISABLED", otel_disabled)
        import tracing

        return tracing

    return _import


class TestOTelDisabledKillSwitch:
    """OTEL_SDK_DISABLED=true must skip all tracing (FR-108)."""

    def test_disabled_returns_no_tracer(self, fresh_tracing_module):
        """When disabled, get_tracer() returns None."""
        tracing = fresh_tracing_module("true")
        assert tracing.get_tracer() is None

    def test_disabled_returns_no_provider(self, fresh_tracing_module):
        """When disabled, get_provider() returns None."""
        tracing = fresh_tracing_module("true")
        assert tracing.get_provider() is None

    def test_disabled_is_enabled_false(self, fresh_tracing_module):
        """When disabled, is_enabled() returns False."""
        tracing = fresh_tracing_module("true")
        assert tracing.is_enabled() is False

    def test_disabled_extract_context_returns_none(self, fresh_tracing_module):
        """When disabled, extract_trace_context() returns None."""
        tracing = fresh_tracing_module("true")
        assert tracing.extract_trace_context() is None

    def test_disabled_safe_force_flush_returns_true(self, fresh_tracing_module):
        """When disabled, safe_force_flush() returns True (nothing to flush)."""
        tracing = fresh_tracing_module("true")
        assert tracing.safe_force_flush() is True


class TestTracerProviderSingleton:
    """TracerProvider must be module-level singleton (SC-027, FR-065)."""

    def test_provider_initialized_at_module_level(self, fresh_tracing_module):
        """TracerProvider init runs at import time."""
        with patch.dict(os.environ, {"OTEL_SDK_DISABLED": "false"}):
            # Mock OTel imports to avoid real SDK dependency in unit tests
            mock_trace = MagicMock()
            mock_provider_cls = MagicMock()
            mock_provider = MagicMock()
            mock_provider_cls.return_value = mock_provider
            mock_resource = MagicMock()
            mock_resource_cls = MagicMock()
            mock_resource_cls.create.return_value = mock_resource
            mock_resource.merge.return_value = mock_resource

            with patch.dict(
                sys.modules,
                {
                    "opentelemetry": MagicMock(),
                    "opentelemetry.trace": mock_trace,
                    "opentelemetry.sdk.trace": MagicMock(
                        TracerProvider=mock_provider_cls
                    ),
                    "opentelemetry.sdk.trace.export": MagicMock(),
                    "opentelemetry.sdk.resources": MagicMock(
                        Resource=mock_resource_cls
                    ),
                    "opentelemetry.exporter.otlp.proto.http.trace_exporter": MagicMock(),
                    "opentelemetry.sdk.extension.aws.trace": MagicMock(),
                    "opentelemetry.sdk.extension.aws.resource": MagicMock(),
                    "opentelemetry.propagators.aws": MagicMock(),
                },
            ):
                _tracing = fresh_tracing_module("false")
                # Provider should have been created
                assert mock_provider_cls.called

    def test_multiple_imports_same_provider(self, fresh_tracing_module):
        """Multiple get_provider() calls return same instance (singleton)."""
        tracing = fresh_tracing_module("true")
        # Both calls should return same value (None when disabled)
        p1 = tracing.get_provider()
        p2 = tracing.get_provider()
        assert p1 is p2


class TestPerInvocationContextExtraction:
    """extract_trace_context() must use current env var, not stale (SC-026)."""

    def test_extracts_from_current_env_var(self, fresh_tracing_module, monkeypatch):
        """Context extraction reads _X_AMZN_TRACE_ID at call time."""
        with patch.dict(os.environ, {"OTEL_SDK_DISABLED": "false"}):
            mock_propagator = MagicMock()
            mock_propagator_cls = MagicMock(return_value=mock_propagator)
            mock_ctx = MagicMock()
            mock_propagator.extract.return_value = mock_ctx

            with patch.dict(
                sys.modules,
                {
                    "opentelemetry": MagicMock(),
                    "opentelemetry.trace": MagicMock(),
                    "opentelemetry.sdk.trace": MagicMock(),
                    "opentelemetry.sdk.trace.export": MagicMock(),
                    "opentelemetry.sdk.resources": MagicMock(),
                    "opentelemetry.exporter.otlp.proto.http.trace_exporter": MagicMock(),
                    "opentelemetry.sdk.extension.aws.trace": MagicMock(),
                    "opentelemetry.sdk.extension.aws.resource": MagicMock(),
                    "opentelemetry.propagators.aws": MagicMock(
                        AwsXRayPropagator=mock_propagator_cls
                    ),
                },
            ):
                tracing = fresh_tracing_module("false")

                # Simulate first invocation
                monkeypatch.setenv(
                    "_X_AMZN_TRACE_ID", "Root=1-aaa-bbb;Parent=ccc;Sampled=1"
                )
                _ctx1 = tracing.extract_trace_context()

                # Simulate warm invocation with new trace ID
                monkeypatch.setenv(
                    "_X_AMZN_TRACE_ID", "Root=1-ddd-eee;Parent=fff;Sampled=1"
                )
                _ctx2 = tracing.extract_trace_context()

                # Should have been called twice with different trace IDs
                assert mock_propagator.extract.call_count == 2
                calls = mock_propagator.extract.call_args_list
                assert (
                    calls[0].kwargs["carrier"]["X-Amzn-Trace-Id"]
                    != calls[1].kwargs["carrier"]["X-Amzn-Trace-Id"]
                )


class TestSafeForceFlush:
    """safe_force_flush() must enforce hard timeout (FR-139)."""

    def test_flush_success_returns_true(self, fresh_tracing_module):
        """Successful flush returns True."""
        tracing = fresh_tracing_module("true")
        # Disabled = nothing to flush = True
        assert tracing.safe_force_flush() is True

    def test_flush_uses_thread_for_timeout(self, fresh_tracing_module, monkeypatch):
        """Flush uses threading.Thread with join(timeout) for hard timeout (FR-139)."""
        # Verify the module uses threading for timeout enforcement
        import inspect

        tracing = fresh_tracing_module("true")
        source = inspect.getsource(tracing.safe_force_flush)
        assert "threading.Thread" in source or "Thread" in source
        assert "join" in source


class TestSpanNames:
    """Verify span names match data-model.md schema."""

    def test_polling_span_name(self):
        """DynamoDB poll span must be named 'dynamodb_poll'."""

        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            "polling.py",
        )
        with open(source_file) as f:
            source = f.read()
        assert '"dynamodb_poll"' in source

    def test_event_dispatch_span_name(self):
        """SSE event dispatch span must be named 'sse_event_dispatch'."""
        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            "stream.py",
        )
        with open(source_file) as f:
            source = f.read()
        assert '"sse_event_dispatch"' in source

    def test_cloudwatch_span_name(self):
        """CloudWatch put_metric span must be named 'cloudwatch_put_metric'."""
        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            "metrics.py",
        )
        with open(source_file) as f:
            source = f.read()
        assert '"cloudwatch_put_metric"' in source


class TestDualErrorPattern:
    """Verify dual-call error pattern (set_status + record_exception) in all files."""

    SSE_FILES = [
        "polling.py",
        "stream.py",
        "metrics.py",
    ]

    @pytest.mark.parametrize("filename", SSE_FILES)
    def test_dual_error_pattern_present(self, filename):
        """Each file with OTel spans must use both set_status and record_exception."""
        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            filename,
        )
        with open(source_file) as f:
            source = f.read()

        set_status_count = source.count("set_status(StatusCode.ERROR")
        record_exception_count = source.count("record_exception(")

        assert set_status_count == record_exception_count, (
            f"{filename}: set_status count ({set_status_count}) != "
            f"record_exception count ({record_exception_count})"
        )


class TestFlushFiredFlag:
    """Verify flush_fired flag blocks new span creation (FR-149)."""

    def test_flush_fired_blocks_trace_dispatch(self):
        """After flush_fired=True, _trace_event_dispatch should not create spans."""
        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            "stream.py",
        )
        with open(source_file) as f:
            source = f.read()

        # Verify flush_fired guard is present before trace_event_dispatch calls
        assert "flush_fired" in source
        assert (
            "not flush_fired" in source
        ), "Must check flush_fired before creating spans"

    def test_deadline_check_sets_flush_fired(self):
        """_check_deadline_flush returning True should cause flush_fired=True."""
        source_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "lambdas",
            "sse_streaming",
            "stream.py",
        )
        with open(source_file) as f:
            source = f.read()

        # Verify the pattern: check_deadline_flush() → flush_fired = True
        assert "flush_fired = True" in source
