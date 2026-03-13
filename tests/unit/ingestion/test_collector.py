"""Unit tests for news article collector with failover."""

from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.ingestion.collector import (
    FetchResult,
    create_collection_event,
    create_orchestrator,
    fetch_news,
)


@pytest.fixture
def mock_orchestrator():
    return MagicMock()


@pytest.fixture
def mock_adapters():
    return MagicMock(), MagicMock()


class TestFetchNews:
    def test_successful_primary_fetch(self, mock_orchestrator):
        mock_orchestrator.get_news_with_failover.return_value = MagicMock(
            data=["article1", "article2"],
            source_used="tiingo",
            is_failover=False,
            duration_ms=150,
        )
        result = fetch_news(mock_orchestrator, ["AAPL"])
        assert len(result.articles) == 2
        assert result.source_used == "tiingo"
        assert result.is_failover is False
        assert result.error is None

    def test_failover_fetch(self, mock_orchestrator):
        mock_orchestrator.get_news_with_failover.return_value = MagicMock(
            data=["article1"],
            source_used="finnhub",
            is_failover=True,
            duration_ms=300,
        )
        result = fetch_news(mock_orchestrator, ["TSLA"])
        assert result.source_used == "finnhub"
        assert result.is_failover is True

    def test_both_sources_fail(self, mock_orchestrator):
        mock_orchestrator.get_news_with_failover.side_effect = RuntimeError("all down")
        result = fetch_news(mock_orchestrator, ["AAPL"])
        assert result.articles == []
        assert result.source_used is None
        assert result.error == "all down"

    def test_custom_lookback_and_limit(self, mock_orchestrator):
        mock_orchestrator.get_news_with_failover.return_value = MagicMock(
            data=[], source_used="tiingo", is_failover=False, duration_ms=50
        )
        fetch_news(mock_orchestrator, ["AAPL"], lookback_days=14, limit=100)
        call_kwargs = mock_orchestrator.get_news_with_failover.call_args.kwargs
        assert call_kwargs["limit"] == 100


class TestCreateOrchestrator:
    def test_returns_orchestrator(self, mock_adapters):
        primary, secondary = mock_adapters
        cb = MagicMock()
        with patch("src.lambdas.ingestion.collector.FailoverOrchestrator") as mock_fo:
            create_orchestrator(primary, secondary, cb, timeout_seconds=5.0)
            mock_fo.assert_called_once_with(
                primary=primary,
                secondary=secondary,
                circuit_breaker=cb,
                timeout_seconds=5.0,
            )


class TestCreateCollectionEvent:
    def test_creates_event_with_source(self):
        event = create_collection_event("evt-1", "finnhub", True)
        assert event.event_id == "evt-1"
        assert event.source_used == "finnhub"
        assert event.is_failover is True
        assert event.status == "partial"

    def test_defaults_to_tiingo_when_none(self):
        event = create_collection_event("evt-2", None, False)
        assert event.source_used == "tiingo"


class TestFetchResult:
    def test_dataclass_defaults(self):
        result = FetchResult(
            articles=[], source_used=None, is_failover=False, duration_ms=0
        )
        assert result.error is None
