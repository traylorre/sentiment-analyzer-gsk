"""Unit tests for VolatilityMetric model."""

from datetime import UTC, datetime

from src.lambdas.shared.models.volatility_metric import VolatilityMetric


def _make_metric(**overrides):
    defaults = {
        "ticker": "AAPL",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "period": 14,
        "atr_value": 3.45,
        "atr_percent": 1.8,
        "trend": "increasing",
        "candle_count": 14,
        "includes_extended_hours": False,
    }
    defaults.update(overrides)
    return VolatilityMetric(**defaults)


class TestVolatilityMetricProperties:
    def test_trend_arrow_increasing(self):
        assert _make_metric(trend="increasing").trend_arrow == "↑"

    def test_trend_arrow_decreasing(self):
        assert _make_metric(trend="decreasing").trend_arrow == "↓"

    def test_trend_arrow_stable(self):
        assert _make_metric(trend="stable").trend_arrow == "→"

    def test_pk(self):
        assert _make_metric().pk == "TICKER#AAPL"

    def test_sk(self):
        m = _make_metric()
        assert m.sk.startswith("ATR#")


class TestVolatilityMetricDynamoDB:
    def test_to_dynamodb_item(self):
        m = _make_metric(previous_atr=3.2)
        item = m.to_dynamodb_item()
        assert item["PK"] == "TICKER#AAPL"
        assert item["entity_type"] == "VOLATILITY_METRIC"
        assert item["previous_atr"] == "3.2"

    def test_to_dynamodb_item_no_previous_atr(self):
        item = _make_metric().to_dynamodb_item()
        assert "previous_atr" not in item

    def test_from_dynamodb_item_roundtrip(self):
        original = _make_metric(previous_atr=3.2)
        item = original.to_dynamodb_item()
        restored = VolatilityMetric.from_dynamodb_item(item)
        assert restored.ticker == "AAPL"
        assert restored.atr_value == 3.45
        assert restored.previous_atr == 3.2

    def test_from_dynamodb_item_no_previous_atr(self):
        item = _make_metric().to_dynamodb_item()
        restored = VolatilityMetric.from_dynamodb_item(item)
        assert restored.previous_atr is None
