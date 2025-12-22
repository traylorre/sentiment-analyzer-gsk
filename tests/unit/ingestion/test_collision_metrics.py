"""Tests for collision metrics tracking.

Feature 1010 Phase 6: User Story 4 - Collision Metrics & Monitoring

Tests that collision rates and ingestion metrics are properly tracked
and published to CloudWatch.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestIngestionMetrics:
    """Tests for IngestionMetrics class."""

    def test_metrics_track_articles_fetched_per_source(self) -> None:
        """Should track articles fetched from each source separately."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()

        # Record fetches from both sources
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 45)

        assert metrics.articles_fetched["tiingo"] == 50
        assert metrics.articles_fetched["finnhub"] == 45
        assert metrics.total_fetched == 95

    def test_metrics_track_collisions_detected(self) -> None:
        """Should track number of duplicate articles detected."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)

        # Record 20 articles that were duplicates
        for _ in range(20):
            metrics.record_collision()

        assert metrics.collisions_detected == 20

    def test_metrics_track_articles_stored(self) -> None:
        """Should track number of unique articles stored."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()

        # Record new articles stored
        metrics.record_stored()
        metrics.record_stored()
        metrics.record_stored()

        assert metrics.articles_stored == 3

    def test_collision_rate_calculation(self) -> None:
        """Should calculate collision rate correctly."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)

        # 20 collisions out of 100 total fetched = 20% collision rate
        for _ in range(20):
            metrics.record_collision()

        # Collision rate = collisions / total_fetched
        assert metrics.collision_rate == pytest.approx(0.20, abs=0.01)

    def test_collision_rate_zero_when_no_fetches(self) -> None:
        """Should return 0 collision rate when no articles fetched."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        assert metrics.collision_rate == 0.0

    def test_collision_rate_zero_when_no_collisions(self) -> None:
        """Should return 0 collision rate when no duplicates found."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)

        # No collisions recorded
        assert metrics.collision_rate == 0.0

    @patch("boto3.client")
    def test_metrics_published_to_cloudwatch(self, mock_boto_client: MagicMock) -> None:
        """Should publish metrics to CloudWatch."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)
        metrics.record_stored()
        metrics.record_collision()

        metrics.publish_to_cloudwatch(namespace="Sentiment/Ingestion")

        # Verify CloudWatch client was created
        mock_boto_client.assert_called_with("cloudwatch")

        # Verify put_metric_data was called
        mock_cw.put_metric_data.assert_called_once()

        # Verify metric data structure
        call_args = mock_cw.put_metric_data.call_args
        assert call_args.kwargs["Namespace"] == "Sentiment/Ingestion"

        # Should have metrics for: TiingoFetched, FinnhubFetched, ArticlesStored, CollisionsDetected, CollisionRate
        metric_data = call_args.kwargs["MetricData"]
        metric_names = [m["MetricName"] for m in metric_data]

        assert "TiingoArticlesFetched" in metric_names
        assert "FinnhubArticlesFetched" in metric_names
        assert "ArticlesStored" in metric_names
        assert "CollisionsDetected" in metric_names
        assert "CollisionRate" in metric_names

    def test_metrics_reset(self) -> None:
        """Should reset all counters."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_stored()
        metrics.record_collision()

        metrics.reset()

        assert metrics.total_fetched == 0
        assert metrics.articles_stored == 0
        assert metrics.collisions_detected == 0

    def test_metrics_to_dict(self) -> None:
        """Should export metrics as dictionary for logging."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 45)
        metrics.record_stored()
        metrics.record_stored()
        metrics.record_collision()

        data = metrics.to_dict()

        assert data["articles_fetched"]["tiingo"] == 50
        assert data["articles_fetched"]["finnhub"] == 45
        assert data["total_fetched"] == 95
        assert data["articles_stored"] == 2
        assert data["collisions_detected"] == 1
        assert data["collision_rate"] == pytest.approx(0.0105, abs=0.001)


class TestCollisionMetricsBoundary:
    """Boundary and edge case tests for collision metrics."""

    def test_high_collision_rate(self) -> None:
        """Should handle very high collision rates (>40%)."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 50)
        metrics.record_fetch("finnhub", 50)

        # 50 collisions out of 100 = 50% collision rate
        for _ in range(50):
            metrics.record_collision()

        assert metrics.collision_rate == 0.50
        assert metrics.is_anomalous()  # > 40% threshold

    def test_low_collision_rate(self) -> None:
        """Should handle very low collision rates (<5%)."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # Only 2 collisions out of 200 = 1% collision rate
        metrics.record_collision()
        metrics.record_collision()

        assert metrics.collision_rate == 0.01
        assert metrics.is_anomalous()  # < 5% threshold

    def test_normal_collision_rate(self) -> None:
        """Should mark normal collision rates as not anomalous."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        metrics.record_fetch("finnhub", 100)

        # 30 collisions out of 200 = 15% collision rate (normal range)
        for _ in range(30):
            metrics.record_collision()

        assert 0.05 <= metrics.collision_rate <= 0.40
        assert not metrics.is_anomalous()

    def test_single_source_no_collisions(self) -> None:
        """Single source ingestion should have zero collisions."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.record_fetch("tiingo", 100)
        # No Finnhub fetch

        assert metrics.articles_fetched.get("finnhub", 0) == 0
        assert metrics.collision_rate == 0.0
        assert not metrics.is_anomalous()  # Zero is not anomalous for single source

    def test_duration_tracking(self) -> None:
        """Should track processing duration."""
        from src.lambdas.ingestion.metrics import IngestionMetrics

        metrics = IngestionMetrics()
        metrics.start_timing()

        # Simulate some work
        import time

        time.sleep(0.01)

        metrics.stop_timing()

        assert metrics.duration_ms >= 10
