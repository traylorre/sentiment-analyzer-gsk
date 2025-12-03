"""Unit tests for SSE CloudWatch metrics emitter.

Tests MetricsEmitter for emitting connection and event metrics per FR-017.
"""

from unittest.mock import MagicMock, patch

from src.lambdas.sse_streaming.metrics import MetricsEmitter


class TestMetricsEmitter:
    """Tests for MetricsEmitter class."""

    def test_default_environment(self):
        """Should use default environment if not specified."""
        with patch.dict("os.environ", {}, clear=True):
            emitter = MetricsEmitter()
            assert emitter._environment == "dev"

    def test_custom_environment(self):
        """Should use custom environment if provided."""
        emitter = MetricsEmitter(environment="prod")
        assert emitter._environment == "prod"

    def test_environment_from_env_var(self):
        """Should use ENVIRONMENT env var if not specified."""
        with patch.dict("os.environ", {"ENVIRONMENT": "preprod"}):
            emitter = MetricsEmitter()
            assert emitter._environment == "preprod"

    def test_emit_connection_count(self):
        """Should emit connection count metric."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        emitter.emit_connection_count(5)

        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["Namespace"] == "SentimentAnalyzer/SSE"
        assert call_kwargs["MetricData"][0]["MetricName"] == "ConnectionCount"
        assert call_kwargs["MetricData"][0]["Value"] == 5.0

    def test_emit_events_sent(self):
        """Should emit events sent metric with event type."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        emitter.emit_events_sent(10, event_type="heartbeat")

        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["MetricData"][0]["MetricName"] == "EventsSent"
        assert call_kwargs["MetricData"][0]["Value"] == 10.0

    def test_emit_event_latency(self):
        """Should emit event latency metric."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        emitter.emit_event_latency(15.5)

        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["MetricData"][0]["MetricName"] == "EventLatencyMs"
        assert call_kwargs["MetricData"][0]["Value"] == 15.5
        assert call_kwargs["MetricData"][0]["Unit"] == "Milliseconds"

    def test_emit_connection_acquire_failure(self):
        """Should emit connection acquire failure metric."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        emitter.emit_connection_acquire_failure()

        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["MetricData"][0]["MetricName"] == "ConnectionAcquireFailures"
        assert call_kwargs["MetricData"][0]["Value"] == 1.0

    def test_emit_poll_duration(self):
        """Should emit poll duration metric."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        emitter.emit_poll_duration(25.0)

        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["MetricData"][0]["MetricName"] == "PollDurationMs"
        assert call_kwargs["MetricData"][0]["Value"] == 25.0
        assert call_kwargs["MetricData"][0]["Unit"] == "Milliseconds"

    def test_measure_latency_context_manager(self):
        """Should measure and emit latency using context manager."""
        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()

        with emitter.measure_latency():
            pass  # Simulated work

        # Should have called put_metric_data with latency
        emitter._cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["MetricData"][0]["MetricName"] == "EventLatencyMs"
        # Latency should be small but > 0
        assert call_kwargs["MetricData"][0]["Value"] >= 0


class TestMetricsEmitterErrorHandling:
    """Tests for error handling in metrics emitter."""

    def test_put_metric_handles_client_error(self):
        """Should handle CloudWatch client errors gracefully."""
        from botocore.exceptions import ClientError

        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()
        emitter._cloudwatch.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test error"}},
            "PutMetricData",
        )

        # Should not raise
        emitter.emit_connection_count(5)

    def test_put_metric_handles_no_region_error(self):
        """Should handle NoRegionError gracefully."""
        from botocore.exceptions import NoRegionError

        emitter = MetricsEmitter(environment="test")
        emitter._cloudwatch = MagicMock()
        emitter._cloudwatch.put_metric_data.side_effect = NoRegionError()

        # Should not raise
        emitter.emit_connection_count(5)

    def test_cloudwatch_lazy_loaded(self):
        """Should lazy-load CloudWatch client."""
        emitter = MetricsEmitter(environment="test")

        # Initially None
        assert emitter._cloudwatch is None

        # Access property should create client
        with patch("src.lambdas.sse_streaming.metrics.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            client = emitter.cloudwatch

            assert client is not None
            mock_boto3.client.assert_called_once_with("cloudwatch")

    def test_dimensions_include_environment(self):
        """Should include Environment dimension in all metrics."""
        emitter = MetricsEmitter(environment="custom-env")
        emitter._cloudwatch = MagicMock()

        emitter.emit_connection_count(1)

        call_kwargs = emitter._cloudwatch.put_metric_data.call_args[1]
        dimensions = call_kwargs["MetricData"][0]["Dimensions"]
        env_dim = next(d for d in dimensions if d["Name"] == "Environment")
        assert env_dim["Value"] == "custom-env"
