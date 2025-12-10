"""Unit tests for latency alerting (T048).

Tests the latency monitoring per US4 requirements:
- Alert when collection latency exceeds 30 seconds (3x normal 10s timeout)
- Latency metric publishing
- Alert suppression for expected delays
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.ingestion.alerting import (
    AlertPublisher,
    AlertType,
    LatencyAlert,
)
from src.lambdas.ingestion.metrics import (
    CollectionMetrics,
    create_metrics_publisher,
)


class TestLatencyAlert:
    """Tests for LatencyAlert data structure."""

    def test_latency_alert_creation(self) -> None:
        """Latency alert can be created with required fields."""
        alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        assert alert.latency_ms == 35000
        assert alert.threshold_ms == 30000
        assert alert.source == "tiingo"

    def test_latency_alert_message_format(self) -> None:
        """Latency alert message should be human-readable."""
        alert = LatencyAlert(
            latency_ms=45000,
            threshold_ms=30000,
            source="finnhub",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        message = alert.to_sns_message()

        assert "45" in message or "45000" in message  # Latency value
        assert "30" in message or "30000" in message  # Threshold
        assert "finnhub" in message.lower()

    def test_latency_alert_subject(self) -> None:
        """Latency alert subject should indicate type."""
        alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        subject = alert.to_sns_subject()

        assert "latency" in subject.lower() or "slow" in subject.lower()

    def test_latency_percentage_over_threshold(self) -> None:
        """Should calculate how much over threshold."""
        alert = LatencyAlert(
            latency_ms=45000,  # 50% over threshold
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        percentage_over = alert.percentage_over_threshold()

        assert percentage_over == 50.0


class TestLatencyThresholds:
    """Tests for latency threshold detection."""

    def test_alert_triggered_above_30_seconds(self) -> None:
        """Should alert when latency > 30 seconds."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        # 35 seconds > 30 second threshold
        result = publisher.should_alert_latency(latency_ms=35000, threshold_ms=30000)
        assert result is True

    def test_no_alert_at_exactly_30_seconds(self) -> None:
        """Should not alert at exactly 30 seconds (boundary)."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        result = publisher.should_alert_latency(latency_ms=30000, threshold_ms=30000)
        assert result is False

    def test_no_alert_below_threshold(self) -> None:
        """Should not alert when latency is below threshold."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        result = publisher.should_alert_latency(latency_ms=25000, threshold_ms=30000)
        assert result is False

    def test_threshold_is_3x_normal_timeout(self) -> None:
        """30s threshold is 3x the 10s normal timeout per spec."""
        normal_timeout_ms = 10000  # 10 seconds
        alert_threshold_ms = normal_timeout_ms * 3  # 30 seconds

        assert alert_threshold_ms == 30000


class TestLatencyAlertPublishing:
    """Tests for publishing latency alerts."""

    def test_publish_latency_alert_to_sns(self) -> None:
        """Should publish latency alert to SNS."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish_latency_alert(alert)

        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:alerts"

    def test_latency_alert_includes_type_attribute(self) -> None:
        """Latency alert should have AlertType for filtering."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
        )

        alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish_latency_alert(alert)

        call_kwargs = mock_sns.publish.call_args[1]
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["AlertType"]["StringValue"] == AlertType.HIGH_LATENCY.value


class TestLatencyMetrics:
    """Tests for latency metric publishing."""

    def test_collection_metrics_includes_latency(self) -> None:
        """CollectionMetrics should track latency."""
        metrics = CollectionMetrics(
            source="tiingo",
            success=True,
            latency_ms=5000,
            items_collected=50,
        )

        assert metrics.latency_ms == 5000

    def test_high_latency_recorded_in_cloudwatch(self) -> None:
        """High latency should be recorded in CloudWatch."""
        mock_cw = MagicMock()
        publisher = create_metrics_publisher(cloudwatch_client=mock_cw)

        metrics = CollectionMetrics(
            source="tiingo",
            success=True,
            latency_ms=35000,  # High latency
            items_collected=50,
        )

        publisher.record_collection(metrics)

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metric_data = call_kwargs["MetricData"]

        # Find latency metric
        latency_metric = next(
            (m for m in metric_data if m["MetricName"] == "CollectionLatencyMs"),
            None,
        )
        assert latency_metric is not None
        assert latency_metric["Value"] == 35000


class TestLatencyAlertSuppression:
    """Tests for latency alert suppression."""

    def test_no_duplicate_latency_alerts_within_cooldown(self) -> None:
        """Should not send duplicate latency alerts within cooldown."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            alert_cooldown_minutes=5,
        )

        alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        # First alert
        publisher.publish_latency_alert(alert)
        assert mock_sns.publish.call_count == 1

        # Second alert within cooldown
        publisher.publish_latency_alert(alert)
        assert mock_sns.publish.call_count == 1  # Still 1

    def test_different_sources_alert_independently(self) -> None:
        """Different sources should alert independently."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            alert_cooldown_minutes=5,
        )

        tiingo_alert = LatencyAlert(
            latency_ms=35000,
            threshold_ms=30000,
            source="tiingo",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        finnhub_alert = LatencyAlert(
            latency_ms=40000,
            threshold_ms=30000,
            source="finnhub",
            timestamp=datetime(2025, 12, 9, 14, 0, 0, tzinfo=UTC),
        )

        publisher.publish_latency_alert(tiingo_alert)
        publisher.publish_latency_alert(finnhub_alert)

        # Both should alert (different sources)
        assert mock_sns.publish.call_count == 2


class TestLatencyThresholdConfiguration:
    """Tests for configurable latency thresholds."""

    def test_default_threshold_is_30_seconds(self) -> None:
        """Default latency threshold should be 30 seconds."""
        from src.lambdas.ingestion.alerting import DEFAULT_LATENCY_THRESHOLD_MS

        assert DEFAULT_LATENCY_THRESHOLD_MS == 30000

    def test_custom_threshold_can_be_configured(self) -> None:
        """Custom threshold can be set."""
        mock_sns = MagicMock()
        publisher = AlertPublisher(
            topic_arn="arn:aws:sns:us-east-1:123456789012:alerts",
            sns_client=mock_sns,
            latency_threshold_ms=45000,  # Custom threshold
        )

        # 40 seconds - below custom threshold
        result = publisher.should_alert_latency(latency_ms=40000, threshold_ms=45000)
        assert result is False

        # 50 seconds - above custom threshold
        result = publisher.should_alert_latency(latency_ms=50000, threshold_ms=45000)
        assert result is True
