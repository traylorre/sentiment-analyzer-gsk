"""Tests for collision alerting thresholds.

Feature 1010 Phase 6: User Story 4 - Collision Metrics & Monitoring

Tests for collision rate alerting based on SC-008:
- Alert if collision_rate > 0.40 (too high, possible duplicate data)
- Alert if collision_rate < 0.05 (too low, possible source mismatch)
"""

from unittest.mock import MagicMock, patch


class TestCollisionAlerts:
    """Tests for collision rate alerting."""

    def test_high_collision_rate_triggers_alert(self) -> None:
        """Collision rate > 40% should trigger anomaly alert."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)

        # 45 collisions = 45% rate
        for _ in range(45):
            metrics.record_collision()

        assert metrics.collision_rate > 0.40
        assert metrics.is_anomalous()
        assert metrics.anomaly_type == "high_collision_rate"

    def test_low_collision_rate_triggers_alert(self) -> None:
        """Collision rate < 5% should trigger anomaly alert."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # Only 3 collisions = 1.5% rate
        for _ in range(3):
            metrics.record_collision()

        assert metrics.collision_rate < 0.05
        assert metrics.is_anomalous()
        assert metrics.anomaly_type == "low_collision_rate"

    def test_normal_collision_rate_no_alert(self) -> None:
        """Collision rate between 5-40% should not trigger alert."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # 25 collisions = 12.5% rate (normal)
        for _ in range(25):
            metrics.record_collision()

        assert 0.05 <= metrics.collision_rate <= 0.40
        assert not metrics.is_anomalous()
        assert metrics.anomaly_type is None

    def test_exactly_five_percent_boundary(self) -> None:
        """Collision rate exactly 5% should NOT trigger alert (inclusive)."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # Exactly 10 collisions = 5% rate
        for _ in range(10):
            metrics.record_collision()

        assert metrics.collision_rate == 0.05
        assert not metrics.is_anomalous()

    def test_exactly_forty_percent_boundary(self) -> None:
        """Collision rate exactly 40% should NOT trigger alert (inclusive)."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # Exactly 80 collisions = 40% rate
        for _ in range(80):
            metrics.record_collision()

        assert metrics.collision_rate == 0.40
        assert not metrics.is_anomalous()

    def test_zero_fetches_no_alert(self) -> None:
        """Zero fetches should not trigger alert."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        # No fetches recorded

        assert metrics.collision_rate == 0.0
        assert not metrics.is_anomalous()  # Zero is expected for empty ingestion

    def test_single_source_zero_collision_no_alert(self) -> None:
        """Single source with zero collisions is expected, not anomalous."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        # No Finnhub source

        assert metrics.collision_rate == 0.0
        assert not metrics.is_anomalous()  # Expected for single source

    @patch("boto3.client")
    def test_cloudwatch_alarm_published_on_high_rate(
        self, mock_boto: MagicMock
    ) -> None:
        """Should publish alarm when collision rate exceeds threshold."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        mock_cw = MagicMock()
        mock_boto.return_value = mock_cw

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)
        for _ in range(50):
            metrics.record_collision()

        metrics.publish_to_cloudwatch(namespace="Sentiment/Ingestion")

        # Verify alarm state was set if anomalous
        call_args = mock_cw.put_metric_data.call_args
        metric_data = call_args.kwargs["MetricData"]

        # Check that anomaly metric exists
        anomaly_metrics = [
            m for m in metric_data if m["MetricName"] == "AnomalousCollisionRate"
        ]
        assert len(anomaly_metrics) == 1
        assert anomaly_metrics[0]["Value"] == 1  # 1 = anomaly detected


class TestCollisionAlertMessages:
    """Tests for alert message generation."""

    def test_high_rate_alert_message(self) -> None:
        """Should generate descriptive message for high collision rate."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)
        for _ in range(50):
            metrics.record_collision()

        message = metrics.get_anomaly_message()

        assert "high" in message.lower()
        assert "50" in message  # Match "50.0%" or "50%"

    def test_low_rate_alert_message(self) -> None:
        """Should generate descriptive message for low collision rate."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)
        metrics.record_collision()

        message = metrics.get_anomaly_message()

        assert "low" in message.lower()

    def test_normal_rate_no_message(self) -> None:
        """Should return None when rate is normal."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)
        for _ in range(20):
            metrics.record_collision()

        message = metrics.get_anomaly_message()
        assert message is None
