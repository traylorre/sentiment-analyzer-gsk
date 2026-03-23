"""Unit tests for SSE sentiment event aggregation and change detection.

Tests per-ticker aggregation (T008), TickerAggregate/PollResult construction (T007),
by_tag population in _aggregate_metrics (T006), and ticker change detection (T009).
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.sse_streaming.polling import (
    PollingService,
    PollResult,
    TickerAggregate,
    detect_ticker_changes,
)


@pytest.fixture
def polling_service():
    """Create a PollingService with a mocked DynamoDB table."""
    with patch.object(PollingService, "_get_table", return_value=MagicMock()):
        service = PollingService(table_name="test-sentiments")
    return service


class TestAggregateMetricsByTag:
    """T006: Test _aggregate_metrics correctly populates by_tag from matched_tickers."""

    def test_single_ticker_articles(self, polling_service):
        """Articles with a single ticker should each contribute one count to by_tag."""
        items = [
            {
                "pk": "SENTIMENT#1",
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": Decimal("0.90"),
            },
            {
                "pk": "SENTIMENT#2",
                "matched_tickers": ["AAPL"],
                "sentiment": "negative",
                "score": Decimal("0.30"),
            },
            {
                "pk": "SENTIMENT#3",
                "matched_tickers": ["MSFT"],
                "sentiment": "neutral",
                "score": Decimal("0.50"),
            },
        ]

        metrics = polling_service._aggregate_metrics(items)

        assert metrics.by_tag == {"AAPL": 2, "MSFT": 1}

    def test_multi_ticker_article(self, polling_service):
        """An article matching multiple tickers should increment each ticker's count."""
        items = [
            {
                "pk": "SENTIMENT#1",
                "matched_tickers": ["AAPL", "MSFT", "GOOGL"],
                "sentiment": "positive",
                "score": Decimal("0.85"),
            },
        ]

        metrics = polling_service._aggregate_metrics(items)

        assert metrics.by_tag == {"AAPL": 1, "MSFT": 1, "GOOGL": 1}

    def test_mixed_single_and_multi_ticker(self, polling_service):
        """Mix of single-ticker and multi-ticker articles should accumulate correctly."""
        items = [
            {
                "pk": "SENTIMENT#1",
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": Decimal("0.80"),
            },
            {
                "pk": "SENTIMENT#2",
                "matched_tickers": ["AAPL", "MSFT"],
                "sentiment": "negative",
                "score": Decimal("0.40"),
            },
            {
                "pk": "SENTIMENT#3",
                "matched_tickers": ["MSFT"],
                "sentiment": "neutral",
                "score": Decimal("0.55"),
            },
        ]

        metrics = polling_service._aggregate_metrics(items)

        assert metrics.by_tag == {"AAPL": 2, "MSFT": 2}

    def test_empty_matched_tickers(self, polling_service):
        """Items with empty matched_tickers should not contribute to by_tag."""
        items = [
            {
                "pk": "SENTIMENT#1",
                "matched_tickers": [],
                "sentiment": "positive",
                "score": Decimal("0.70"),
            },
        ]

        metrics = polling_service._aggregate_metrics(items)

        assert metrics.by_tag == {}
        assert metrics.total == 1

    def test_missing_matched_tickers_key(self, polling_service):
        """Items without matched_tickers key should not contribute to by_tag."""
        items = [
            {
                "pk": "SENTIMENT#1",
                "sentiment": "positive",
                "score": Decimal("0.70"),
            },
        ]

        metrics = polling_service._aggregate_metrics(items)

        assert metrics.by_tag == {}
        assert metrics.total == 1


class TestTickerAggregateAndPollResult:
    """T007: Test TickerAggregate dataclass and PollResult named tuple."""

    def test_ticker_aggregate_construction(self):
        """TickerAggregate should store all fields correctly."""
        agg = TickerAggregate(
            ticker="AAPL",
            score=0.85,
            label="positive",
            confidence=0.85,
            count=10,
        )

        assert agg.ticker == "AAPL"
        assert agg.score == 0.85
        assert agg.label == "positive"
        assert agg.confidence == 0.85
        assert agg.count == 10

    def test_ticker_aggregate_equality(self):
        """Two TickerAggregate instances with same values should be equal (dataclass)."""
        agg1 = TickerAggregate(
            ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=5
        )
        agg2 = TickerAggregate(
            ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=5
        )

        assert agg1 == agg2

    def test_ticker_aggregate_inequality(self):
        """TickerAggregate instances with different values should not be equal."""
        agg1 = TickerAggregate(
            ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=5
        )
        agg2 = TickerAggregate(
            ticker="MSFT", score=0.70, label="positive", confidence=0.70, count=6
        )

        assert agg1 != agg2

    def test_poll_result_field_access(self):
        """PollResult named tuple fields should be accessible by name and index."""
        from src.lambdas.sse_streaming.models import MetricsEventData

        metrics = MetricsEventData(total=10, positive=5, neutral=3, negative=2)
        per_ticker = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.8, label="positive", confidence=0.8, count=5
            )
        }
        result = PollResult(
            metrics=metrics,
            metrics_changed=True,
            per_ticker=per_ticker,
            timeseries_buckets={},
        )

        # Named access
        assert result.metrics.total == 10
        assert result.metrics_changed is True
        assert "AAPL" in result.per_ticker
        assert result.per_ticker["AAPL"].count == 5
        assert result.timeseries_buckets == {}

        # Index access (NamedTuple)
        assert result[0] == metrics
        assert result[1] is True
        assert result[2] == per_ticker
        assert result[3] == {}

    def test_poll_result_unpacking(self):
        """PollResult should support tuple unpacking."""
        from src.lambdas.sse_streaming.models import MetricsEventData

        metrics = MetricsEventData(total=3, positive=1, neutral=1, negative=1)
        result = PollResult(
            metrics=metrics,
            metrics_changed=False,
            per_ticker={},
            timeseries_buckets={},
        )

        m, changed, pt, ts = result

        assert m.total == 3
        assert changed is False
        assert pt == {}
        assert ts == {}


class TestComputePerTickerAggregates:
    """T008: Test _compute_per_ticker_aggregates for correct aggregation."""

    def test_single_ticker_items(self, polling_service):
        """Items each matching one ticker should produce correct aggregates."""
        items = [
            {
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": Decimal("0.90"),
            },
            {
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": Decimal("0.80"),
            },
            {
                "matched_tickers": ["AAPL"],
                "sentiment": "negative",
                "score": Decimal("0.30"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        assert "AAPL" in result
        agg = result["AAPL"]
        assert agg.ticker == "AAPL"
        assert agg.count == 3
        # Weighted average: (0.90 + 0.80 + 0.30) / 3 = 2.00 / 3 ~= 0.6667
        expected_score = float(
            (Decimal("0.90") + Decimal("0.80") + Decimal("0.30")) / 3
        )
        assert abs(agg.score - expected_score) < 1e-10
        # Majority label: 2 positive vs 1 negative
        assert agg.label == "positive"
        # Confidence equals score (no separate confidence field)
        assert agg.confidence == agg.score

    def test_multi_ticker_items(self, polling_service):
        """An article matching AAPL and MSFT should contribute to both aggregates."""
        items = [
            {
                "matched_tickers": ["AAPL", "MSFT"],
                "sentiment": "positive",
                "score": Decimal("0.85"),
            },
            {
                "matched_tickers": ["AAPL"],
                "sentiment": "negative",
                "score": Decimal("0.20"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        # AAPL: 2 items (0.85 + 0.20) / 2 = 0.525
        assert result["AAPL"].count == 2
        expected_aapl = float((Decimal("0.85") + Decimal("0.20")) / 2)
        assert abs(result["AAPL"].score - expected_aapl) < 1e-10
        # AAPL: 1 positive, 1 negative -> tie broken by Counter.most_common (first seen)
        assert result["AAPL"].label in ("positive", "negative")

        # MSFT: 1 item, score 0.85
        assert result["MSFT"].count == 1
        assert abs(result["MSFT"].score - 0.85) < 1e-10
        assert result["MSFT"].label == "positive"

    def test_empty_matched_tickers(self, polling_service):
        """Items with empty matched_tickers should not produce any ticker aggregates."""
        items = [
            {
                "matched_tickers": [],
                "sentiment": "positive",
                "score": Decimal("0.90"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        assert result == {}

    def test_missing_matched_tickers_key(self, polling_service):
        """Items without matched_tickers key should not produce any ticker aggregates."""
        items = [
            {
                "sentiment": "positive",
                "score": Decimal("0.90"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        assert result == {}

    def test_all_same_sentiment(self, polling_service):
        """When all items have the same sentiment, majority label should be that sentiment."""
        items = [
            {
                "matched_tickers": ["TSLA"],
                "sentiment": "negative",
                "score": Decimal("0.10"),
            },
            {
                "matched_tickers": ["TSLA"],
                "sentiment": "negative",
                "score": Decimal("0.25"),
            },
            {
                "matched_tickers": ["TSLA"],
                "sentiment": "negative",
                "score": Decimal("0.15"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        assert result["TSLA"].label == "negative"
        assert result["TSLA"].count == 3
        expected_score = float(
            (Decimal("0.10") + Decimal("0.25") + Decimal("0.15")) / 3
        )
        assert abs(result["TSLA"].score - expected_score) < 1e-10

    def test_multiple_tickers_independent(self, polling_service):
        """Different tickers should have independent aggregates."""
        items = [
            {
                "matched_tickers": ["AAPL"],
                "sentiment": "positive",
                "score": Decimal("0.90"),
            },
            {
                "matched_tickers": ["MSFT"],
                "sentiment": "negative",
                "score": Decimal("0.20"),
            },
            {
                "matched_tickers": ["GOOGL"],
                "sentiment": "neutral",
                "score": Decimal("0.50"),
            },
        ]

        result = polling_service._compute_per_ticker_aggregates(items)

        assert len(result) == 3
        assert result["AAPL"].label == "positive"
        assert result["AAPL"].count == 1
        assert abs(result["AAPL"].score - 0.90) < 1e-10

        assert result["MSFT"].label == "negative"
        assert result["MSFT"].count == 1
        assert abs(result["MSFT"].score - 0.20) < 1e-10

        assert result["GOOGL"].label == "neutral"
        assert result["GOOGL"].count == 1
        assert abs(result["GOOGL"].score - 0.50) < 1e-10

    def test_empty_items_list(self, polling_service):
        """Empty items list should return empty dict."""
        result = polling_service._compute_per_ticker_aggregates([])

        assert result == {}


class TestDetectTickerChanges:
    """T009: Test per-ticker change detection between polling snapshots."""

    def test_score_changed(self):
        """Should detect when a ticker's score changes."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.75, label="positive", confidence=0.75, count=5
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert "AAPL" in changes

    def test_new_ticker_appeared(self):
        """Should detect when a new ticker appears in current snapshot."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert "MSFT" in changes
        assert "AAPL" not in changes

    def test_ticker_disappeared(self):
        """Should detect when a ticker disappears (no articles this cycle)."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert "MSFT" in changes
        assert "AAPL" not in changes

    def test_no_changes(self):
        """Should return empty set when aggregates are identical."""
        snapshot = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
        }
        # Create identical but separate instances
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
        }

        changes = detect_ticker_changes(current, snapshot)

        assert changes == set()

    def test_label_changed(self):
        """Should detect when a ticker's majority label changes."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="neutral", confidence=0.80, count=5
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert "AAPL" in changes

    def test_count_changed(self):
        """Should detect when a ticker's article count changes."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=6
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert "AAPL" in changes

    def test_both_empty(self):
        """Empty previous and current should return no changes."""
        changes = detect_ticker_changes({}, {})

        assert changes == set()

    def test_multiple_changes_simultaneously(self):
        """Should detect all changed tickers at once."""
        previous = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.80, label="positive", confidence=0.80, count=5
            ),
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
            "GOOGL": TickerAggregate(
                ticker="GOOGL", score=0.70, label="positive", confidence=0.70, count=4
            ),
        }
        current = {
            "AAPL": TickerAggregate(
                ticker="AAPL", score=0.85, label="positive", confidence=0.85, count=6
            ),
            # MSFT unchanged
            "MSFT": TickerAggregate(
                ticker="MSFT", score=0.60, label="neutral", confidence=0.60, count=3
            ),
            # GOOGL removed, TSLA added
            "TSLA": TickerAggregate(
                ticker="TSLA", score=0.40, label="negative", confidence=0.40, count=2
            ),
        }

        changes = detect_ticker_changes(current, previous)

        assert changes == {"AAPL", "GOOGL", "TSLA"}
        assert "MSFT" not in changes
