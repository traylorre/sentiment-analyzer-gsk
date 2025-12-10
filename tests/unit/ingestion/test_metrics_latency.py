"""Unit tests for latency monitoring and success rate in MetricsPublisher (T051, T053).

Tests the latency threshold monitoring per US4 requirements:
- Alert when collection latency exceeds 30 seconds (3x normal 10s timeout)
- CloudWatch metric recording for high latency
- Threshold configuration
- Collection success rate metrics
"""

from unittest.mock import MagicMock

from src.lambdas.ingestion.metrics import (
    DEFAULT_LATENCY_THRESHOLD_MS,
    DEFAULT_NOTIFICATION_SLA_MS,
    METRIC_COLLECTION_LATENCY,
    METRIC_COLLECTION_SUCCESS_RATE,
    METRIC_HIGH_LATENCY_ALERT,
    METRIC_NOTIFICATION_LATENCY,
    create_metrics_publisher,
)


class TestLatencyThresholdCheck:
    """Tests for check_latency_threshold method."""

    def test_returns_true_when_latency_exceeds_threshold(self) -> None:
        """Should return True when latency > threshold."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.check_latency_threshold(
            latency_ms=35000,  # 35s > 30s threshold
            source="tiingo",
        )

        assert result is True

    def test_returns_false_when_latency_below_threshold(self) -> None:
        """Should return False when latency < threshold."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.check_latency_threshold(
            latency_ms=25000,  # 25s < 30s threshold
            source="tiingo",
        )

        assert result is False

    def test_returns_false_at_exactly_threshold(self) -> None:
        """Should return False at exactly threshold (boundary)."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.check_latency_threshold(
            latency_ms=30000,  # exactly 30s
            source="tiingo",
        )

        assert result is False

    def test_default_threshold_is_30_seconds(self) -> None:
        """Default threshold should be 30s (30000ms)."""
        assert DEFAULT_LATENCY_THRESHOLD_MS == 30000


class TestLatencyMetricRecording:
    """Tests for CloudWatch metric recording on high latency."""

    def test_records_high_latency_alert_metric(self) -> None:
        """Should record HighLatencyAlert metric when threshold exceeded."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.check_latency_threshold(
            latency_ms=35000,
            source="tiingo",
        )

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        # Find high latency alert metric
        alert_metric = next(
            (m for m in metric_data if m["MetricName"] == METRIC_HIGH_LATENCY_ALERT),
            None,
        )
        assert alert_metric is not None
        assert alert_metric["Value"] == 1
        assert alert_metric["Unit"] == "Count"

    def test_records_latency_value_with_threshold_dimension(self) -> None:
        """Should record actual latency with ThresholdExceeded dimension."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.check_latency_threshold(
            latency_ms=45000,
            source="finnhub",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        # Find latency metric with threshold dimension
        latency_metric = next(
            (
                m
                for m in metric_data
                if m["MetricName"] == METRIC_COLLECTION_LATENCY
                and any(
                    d.get("Name") == "ThresholdExceeded"
                    for d in m.get("Dimensions", [])
                )
            ),
            None,
        )
        assert latency_metric is not None
        assert latency_metric["Value"] == 45000
        assert latency_metric["Unit"] == "Milliseconds"

    def test_includes_source_dimension(self) -> None:
        """Should include Source dimension in metrics."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.check_latency_threshold(
            latency_ms=35000,
            source="tiingo",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        alert_metric = next(
            (m for m in metric_data if m["MetricName"] == METRIC_HIGH_LATENCY_ALERT),
            None,
        )
        source_dim = next(
            (d for d in alert_metric["Dimensions"] if d["Name"] == "Source"),
            None,
        )
        assert source_dim is not None
        assert source_dim["Value"] == "tiingo"

    def test_no_metric_recorded_when_below_threshold(self) -> None:
        """Should not record metrics when latency is below threshold."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.check_latency_threshold(
            latency_ms=25000,
            source="tiingo",
        )

        mock_cw.put_metric_data.assert_not_called()


class TestCustomThreshold:
    """Tests for custom latency threshold configuration."""

    def test_custom_threshold_can_be_specified(self) -> None:
        """Should use custom threshold when specified."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        # 40s latency, custom 45s threshold - should NOT alert
        result = publisher.check_latency_threshold(
            latency_ms=40000,
            source="tiingo",
            threshold_ms=45000,
        )

        assert result is False
        mock_cw.put_metric_data.assert_not_called()

    def test_custom_threshold_triggers_when_exceeded(self) -> None:
        """Should alert when custom threshold is exceeded."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        # 50s latency, custom 45s threshold - should alert
        result = publisher.check_latency_threshold(
            latency_ms=50000,
            source="finnhub",
            threshold_ms=45000,
        )

        assert result is True
        mock_cw.put_metric_data.assert_called_once()


class TestLatencyThresholdRationale:
    """Tests documenting the 30s threshold rationale."""

    def test_threshold_is_3x_normal_timeout(self) -> None:
        """30s threshold is 3x the 10s normal collection timeout per spec."""
        normal_timeout_ms = 10000  # 10 seconds (standard collection timeout)
        expected_alert_threshold = normal_timeout_ms * 3  # 30 seconds

        assert DEFAULT_LATENCY_THRESHOLD_MS == expected_alert_threshold

    def test_threshold_in_seconds_is_30(self) -> None:
        """Threshold in human-readable seconds is 30."""
        threshold_seconds = DEFAULT_LATENCY_THRESHOLD_MS / 1000
        assert threshold_seconds == 30.0


class TestCollectionSuccessRate:
    """Tests for record_success_rate method (T053)."""

    def test_records_success_rate_metric(self) -> None:
        """Should record success rate to CloudWatch."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(success_count=99, failure_count=1)

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        rate_metric = next(
            (
                m
                for m in metric_data
                if m["MetricName"] == METRIC_COLLECTION_SUCCESS_RATE
            ),
            None,
        )
        assert rate_metric is not None
        assert rate_metric["Value"] == 0.99  # 99%

    def test_success_rate_calculation_100_percent(self) -> None:
        """Should calculate 1.0 for 100% success."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(success_count=100, failure_count=0)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        rate_metric = metric_data[0]
        assert rate_metric["Value"] == 1.0

    def test_success_rate_calculation_0_percent(self) -> None:
        """Should calculate 0.0 for 0% success."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(success_count=0, failure_count=10)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        rate_metric = metric_data[0]
        assert rate_metric["Value"] == 0.0

    def test_no_metric_recorded_when_zero_total(self) -> None:
        """Should not record metric when no operations occurred."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(success_count=0, failure_count=0)

        mock_cw.put_metric_data.assert_not_called()

    def test_includes_source_dimension_when_provided(self) -> None:
        """Should include Source dimension when source is specified."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(
            success_count=95,
            failure_count=5,
            source="tiingo",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        rate_metric = metric_data[0]
        source_dim = next(
            (d for d in rate_metric["Dimensions"] if d["Name"] == "Source"),
            None,
        )
        assert source_dim is not None
        assert source_dim["Value"] == "tiingo"

    def test_no_source_dimension_when_not_provided(self) -> None:
        """Should not include Source dimension when source is None."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_success_rate(success_count=99, failure_count=1)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        rate_metric = metric_data[0]
        assert rate_metric["Dimensions"] == []

    def test_success_rate_target_is_99_5_percent(self) -> None:
        """Document spec requirement: 99.5% collection success rate target."""
        target_rate = 0.995  # Per spec requirement

        # Example meeting target
        success_count = 995
        failure_count = 5
        actual_rate = success_count / (success_count + failure_count)

        assert actual_rate == target_rate


class TestNotificationLatencyMetric:
    """Tests for record_notification_latency method (T061)."""

    def test_records_notification_latency_metric(self) -> None:
        """Should record notification latency to CloudWatch."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_notification_latency(latency_ms=500, source="tiingo")

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        latency_metric = next(
            (m for m in metric_data if m["MetricName"] == METRIC_NOTIFICATION_LATENCY),
            None,
        )
        assert latency_metric is not None
        assert latency_metric["Value"] == 500
        assert latency_metric["Unit"] == "Milliseconds"

    def test_returns_true_when_sla_met(self) -> None:
        """Should return True when latency is within SLA."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.record_notification_latency(
            latency_ms=25000,  # 25s < 30s SLA
            source="tiingo",
        )

        assert result is True

    def test_returns_false_when_sla_exceeded(self) -> None:
        """Should return False when latency exceeds SLA."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.record_notification_latency(
            latency_ms=35000,  # 35s > 30s SLA
            source="tiingo",
        )

        assert result is False

    def test_returns_true_at_exactly_sla(self) -> None:
        """Should return True at exactly SLA threshold (boundary)."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        result = publisher.record_notification_latency(
            latency_ms=30000,  # exactly 30s
            source="tiingo",
        )

        assert result is True

    def test_includes_sla_met_dimension(self) -> None:
        """Should include SLAMet dimension in metric."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_notification_latency(
            latency_ms=500,  # well within SLA
            source="tiingo",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        latency_metric = metric_data[0]

        sla_dim = next(
            (d for d in latency_metric["Dimensions"] if d["Name"] == "SLAMet"),
            None,
        )
        assert sla_dim is not None
        assert sla_dim["Value"] == "true"

    def test_sla_met_dimension_is_false_when_exceeded(self) -> None:
        """SLAMet dimension should be 'false' when SLA exceeded."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_notification_latency(
            latency_ms=35000,  # exceeds 30s SLA
            source="tiingo",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        latency_metric = metric_data[0]

        sla_dim = next(
            (d for d in latency_metric["Dimensions"] if d["Name"] == "SLAMet"),
            None,
        )
        assert sla_dim is not None
        assert sla_dim["Value"] == "false"

    def test_includes_source_dimension_when_provided(self) -> None:
        """Should include Source dimension when source is specified."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_notification_latency(
            latency_ms=500,
            source="finnhub",
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        latency_metric = metric_data[0]

        source_dim = next(
            (d for d in latency_metric["Dimensions"] if d["Name"] == "Source"),
            None,
        )
        assert source_dim is not None
        assert source_dim["Value"] == "finnhub"

    def test_no_source_dimension_when_not_provided(self) -> None:
        """Should not include Source dimension when source is None."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        publisher.record_notification_latency(latency_ms=500)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]
        latency_metric = metric_data[0]

        source_dim = next(
            (d for d in latency_metric["Dimensions"] if d["Name"] == "Source"),
            None,
        )
        assert source_dim is None

    def test_default_sla_is_30_seconds(self) -> None:
        """Default notification SLA should be 30s (30000ms)."""
        assert DEFAULT_NOTIFICATION_SLA_MS == 30000

    def test_custom_sla_can_be_specified(self) -> None:
        """Should use custom SLA when specified."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        # 20s latency with 15s custom SLA - should NOT meet SLA
        result = publisher.record_notification_latency(
            latency_ms=20000,
            source="tiingo",
            sla_ms=15000,
        )

        assert result is False
